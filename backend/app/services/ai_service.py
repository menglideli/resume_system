"""Kimi API 封装层（指令 4 交付物）。

实现七大 AI 能力：
  1. resume_diagnosis      简历诊断
  2. parse_jd              JD 深度解析
  3. generate_resume       简历定制生成
  4. map_form_fields       报名表字段映射
  5. generate_interview_qa 面试 Q&A 生成
  6. job_research          岗位调研（基于 JD 与简历推断）
  7. interview_outline     面试提纲

统一约定：
  - OpenAI 兼容 SDK（AsyncOpenAI），base_url=https://api.moonshot.cn/v1
  - response_format={"type": "json_object"} 强制 JSON 输出
  - tenacity 重试：最多 3 次，指数退避
  - 每次调用记录 token 使用量（logger + self.last_usage）
"""
import json
import logging
import re
import time
from typing import Any

import httpx
from openai import (
    APIConnectionError, APIError, APITimeoutError, AsyncOpenAI,
    InternalServerError, RateLimitError,
)
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.exceptions import AIServiceException

logger = logging.getLogger("ai_service")

# 推理模型（kimi-k* / k2 / k3 / thinking）：思考过程 token 也计入 max_tokens，
# 生成整份简历时极易被截断，因此输出预算要给足。
REASONING_MODEL_TAGS = ("kimi-k", "k2", "k3", "thinking")
REASONING_TIMEOUT_FLOOR = 600      # 秒：推理模型首 token 慢，单次调用上限
REASONING_OUTPUT_BUDGET = 16384    # 长输出（生成简历 / 面试题库）的 token 预算

# 思考强度：kimi-k3 默认 max，实测生成整份简历时思考 token 数千、单次调用超过
# 500 秒仍不返回，最终被服务端/代理掐断（RemoteProtocolError: Server disconnected）。
# 同一任务实测 max 130s(reasoning 2224) / high 78s(131) / low 60s(5)，high 的正文
# 反而比 low 更充实，所以默认 high。非推理模型不能传这个参数，会 400。
REASONING_EFFORTS = ("low", "high", "max")
DEFAULT_REASONING_EFFORT = "high"

# 客户端缓存：AsyncOpenAI 内部持有 httpx.AsyncClient（含连接池），
# 之前每次调用都 new 一个且从不关闭，长时间运行会耗尽句柄/端口，表现为
# "Connection error."。这里按 (key, base_url, timeout) 复用同一个客户端。
_CLIENT_CACHE: dict[tuple[str, str, float], AsyncOpenAI] = {}


def _dumps(obj: Any) -> str:
    """提示词序列化：date/datetime/UUID 等非原生类型统一转字符串，避免序列化崩溃。"""
    return json.dumps(obj, ensure_ascii=False, default=str)


def _fmt_error(exc: Exception) -> str:
    """把 SDK 异常压成一行可读信息：带上 HTTP 状态码与服务端返回的 message。"""
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None)
    detail = ""
    if isinstance(body, dict):
        detail = (body.get("error") or {}).get("message") or body.get("message") or ""
    text = getattr(exc, "message", None) or str(exc)
    if status is not None:
        return f"HTTP {status} {detail or text}"
    return detail or text


# 只有这类错误重试才有意义；401/400 等 4xx 属于配置或请求错误，重试纯属浪费时间。
RETRYABLE_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)
MAX_ATTEMPTS = 3  # tenacity 重试次数，报错文案里要如实告诉用户重试过几次


class AIService:
    """Kimi API 调用封装，所有方法均为 async。

    config 为运行时配置（来自 system_config 表，经 ConfigService 合并），
    缺省回退 .env / app.config.settings。
    """

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.model = cfg.get("KIMI_MODEL") or settings.KIMI_MODEL
        # 推理模型（kimi-k2/k3 等）仅允许 temperature=1，直接不传，避免 400 报错；
        # 且首 token 延迟高，客户端超时下限 600 秒，避免长耗时调用被客户端超时打断后
        # 又走 3 次重试，把整个后台任务拖到外层超时上限。
        model_lower = str(self.model).lower()
        is_reasoning = any(tag in model_lower for tag in REASONING_MODEL_TAGS)
        self._supports_temperature = not is_reasoning
        self._is_reasoning = is_reasoning
        # 思考强度只对推理模型有意义；值非法时静默回退默认档，不阻断业务。
        self._reasoning_effort: str | None = None
        if is_reasoning:
            raw = str(
                cfg.get("KIMI_REASONING_EFFORT") or settings.KIMI_REASONING_EFFORT or ""
            ).strip().lower()
            self._reasoning_effort = raw if raw in REASONING_EFFORTS else DEFAULT_REASONING_EFFORT
        timeout = int(cfg.get("KIMI_TIMEOUT") or settings.KIMI_TIMEOUT)
        if is_reasoning:
            timeout = max(timeout, REASONING_TIMEOUT_FLOOR)
        self._timeout = timeout

        api_key = cfg.get("KIMI_API_KEY") or settings.KIMI_API_KEY or "sk-placeholder"
        base_url = cfg.get("KIMI_BASE_URL") or settings.KIMI_BASE_URL
        cache_key = (api_key, base_url, float(timeout))
        client = _CLIENT_CACHE.get(cache_key)
        if client is None:
            client = AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=timeout)
            _CLIENT_CACHE[cache_key] = client
        self.client = client
        self._max_tokens = int(cfg.get("KIMI_MAX_TOKENS") or settings.KIMI_MAX_TOKENS)
        self.last_usage: dict[str, int] = {}

    # ==================================================================
    # 底层：带重试的 JSON 对话
    # ==================================================================
    @retry(
        stop=stop_after_attempt(MAX_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RETRYABLE_ERRORS),
        reraise=True,
    )
    async def _chat_json(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> dict[str, Any]:
        """调用 Kimi 并解析 JSON 响应；网络/限流/5xx 自动重试（3 次指数退避）。"""
        kwargs: dict[str, Any] = {}
        if self._supports_temperature:
            kwargs["temperature"] = 0.3
        elif self._reasoning_effort:
            # 非推理模型传 reasoning_effort 会被 API 拒绝（400），所以只在
            # 上面 temperature 分支的 else 里传，两者互斥。
            kwargs["reasoning_effort"] = self._reasoning_effort
        budget = max_tokens or self._max_tokens
        t0 = time.time()
        content, finish_reason, usage = await self._stream_collect(
            system_prompt, user_prompt, budget, kwargs
        )
        elapsed = time.time() - t0
        # ---- 记录 token 使用量 ----
        self.last_usage = {
            "prompt_tokens": usage.prompt_tokens if usage else 0,
            "completion_tokens": usage.completion_tokens if usage else 0,
            "total_tokens": usage.total_tokens if usage else 0,
        }
        logger.info(
            "Kimi API 响应：model=%s 耗时 %.1f 秒 tokens=%s finish=%s",
            self.model, elapsed, self.last_usage, finish_reason,
        )

        # 流没有正常收尾 = 连接在中途被掐断，内容是半截 JSON。
        # 必须抛「可重试」的异常交给 tenacity 重来；如果放任它走到 _parse_json，
        # 报出来的是 AIServiceException —— 不在重试名单里，用户就直接看到失败了。
        if finish_reason is None:
            logger.warning(
                "Kimi API 流式响应未正常结束（%.1f 秒，已收 %d 字符），判定为连接中断并重试",
                elapsed, len(content),
            )
            raise APIConnectionError(
                message="流式响应未正常结束（连接被中断），内容不完整",
                request=httpx.Request("POST", str(self.client.base_url)),
            )

        # 输出被 max_tokens 截断 → JSON 必然不完整，直接给可读原因，别等到解析失败
        if finish_reason == "length":
            raise AIServiceException(
                f"AI 输出被 max_tokens={budget} 截断（未生成完整 JSON）。"
                f"请后台调高 KIMI_MAX_TOKENS，或精简档案/降低页数限制。"
            )
        return self._parse_json(content)

    async def _stream_collect(
        self,
        system_prompt: str,
        user_prompt: str,
        budget: int,
        kwargs: dict[str, Any],
    ) -> tuple[str, str | None, Any]:
        """流式取回完整输出，返回 (正文, finish_reason, usage)。

        为什么必须流式：推理模型思考期间服务端一个字节都不发，非流式请求就是一条
        长时间完全静默的连接 —— 中间链路会把它当成空闲连接掐断，表现为
        `RemoteProtocolError: Server disconnected without sending a response`，
        再经 tenacity 重试 3 次，把后台任务拖到几分钟后以「Connection error.」失败。
        实测同一份真实档案：非流式 564.7 秒失败，流式 71.6 秒成功（1756 个 chunk，
        最大间隔 13 秒 —— 也就是等首 chunk 的时间，之后数据持续流动）。
        """
        pieces: list[str] = []
        finish_reason: str | None = None
        usage: Any = None
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=budget,
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in stream:
            # 开了 include_usage 后，最后一个 chunk 只有 usage、没有 choices
            if getattr(chunk, "usage", None) is not None:
                usage = chunk.usage
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                pieces.append(delta.content)
            if chunk.choices[0].finish_reason:
                finish_reason = chunk.choices[0].finish_reason
        return "".join(pieces), finish_reason, usage

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        """解析 JSON；模型偶发包裹 markdown 时做兜底提取。"""
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
        raise AIServiceException(f"AI 响应 JSON 解析失败: {content[:200]}")

    async def _safe_chat_json(self, system_prompt: str, user_prompt: str, max_tokens: int | None = None) -> dict[str, Any]:
        """对 _chat_json 的统一错误包装：把 SDK 异常转成可读的业务异常。"""
        try:
            return await self._chat_json(system_prompt, user_prompt, max_tokens)
        except AIServiceException:
            raise
        except (APIConnectionError, APITimeoutError) as exc:
            # 「Connection error.」这种原文对用户毫无用处 —— 排查时只能从头试错。
            # 这里把结论直接写进报错：已重试几次、大概率是什么、什么做法是无效的。
            # SDK 原文自带句点（"Connection error."），拼接前去掉，避免出现「error.。」
            detail = _fmt_error(exc).rstrip("。. ")
            raise AIServiceException(
                f"Kimi API 连接中断（已自动重试 {MAX_ATTEMPTS} 次仍未成功）：{detail}。"
                f"请求已发出，是长连接被网络链路（代理 / NAT 空闲超时）掐断，"
                f"不是 API Key 或参数错误，调大超时也无效。"
            ) from exc
        except Exception as exc:
            raise AIServiceException(f"Kimi API 调用失败: {_fmt_error(exc)}") from exc

    # ==================================================================
    # 1. 简历诊断
    # ==================================================================
    async def resume_diagnosis(self, resume_text: str, keywords_hint: list[str] | None = None) -> dict[str, Any]:
        """输入简历纯文本，输出结构化诊断报告。"""
        system_prompt = """你是一位资深简历顾问与 HR 筛选专家，熟悉 ATS（简历筛选系统）规则。
请诊断用户简历，并严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "overall_score": 75,                       // 综合评分 0-100
  "issues": [                                // 问题列表，按严重度排序
    {"category": "结构", "severity": "high", "description": "缺少项目经历模块"}
  ],
  "suggestions": ["建议补充 2-3 个项目经历"],  // 可执行的改进建议
  "keywords_missing": ["微服务", "Docker"]     // 行业常见但简历缺失的关键词
}
severity 只能是 high / medium / low。issues 最多 10 条，suggestions 最多 8 条。"""
        user_prompt = f"【简历原文】\n{resume_text}"
        if keywords_hint:
            user_prompt += f"\n\n【重点检查关键词】\n{', '.join(keywords_hint)}"
        return await self._safe_chat_json(system_prompt, user_prompt)

    # ==================================================================
    # 2. JD 深度解析
    # ==================================================================
    async def parse_jd(self, raw_text: str) -> dict[str, Any]:
        """输入岗位描述原文，输出结构化解析结果。"""
        system_prompt = """你是一位资深招聘分析师。请深度解析岗位描述（JD），严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "company": "公司名称（无法识别则为 null）",
  "position": "岗位名称",
  "hard_requirements": ["3年以上经验", "精通 Go/Java"],   // 硬性要求（学历/年限/技能）
  "soft_requirements": ["良好的沟通能力"],                 // 软性要求
  "core_responsibilities": ["负责后端服务设计与开发"],      // 核心职责
  "bonus_items": ["有开源项目贡献"],                        // 加分项
  "keywords": ["Go", "gRPC", "Redis"],                     // 中文技术关键词
  "ats_keywords": ["backend", "distributed systems"],      // 英文 ATS 关键词
  "education_requirement": "本科及以上",
  "experience_years": "3-5年",
  "salary_range": "25k-40k（未提及则为 null）"
}
每个数组最多 10 项，无法识别的字段填 null 或空数组。"""
        return await self._safe_chat_json(system_prompt, f"【岗位描述】\n{raw_text}")

    # ==================================================================
    # 3. 简历定制生成
    # ==================================================================
    async def generate_resume(
        self,
        user_profile: dict[str, Any],
        jd_parsed: dict[str, Any],
        preferences: dict[str, Any],
        jd_raw_text: str = "",
    ) -> dict[str, Any]:
        """档案 × JD 解析 × 用户偏好 → 定制简历 JSON + 匹配分析。"""
        system_prompt = """你是一位资深简历撰写专家。基于【用户档案】【JD 解析结果】【用户偏好】，生成定制化简历。
规则：
1. 诚实原则：不得编造用户档案中不存在的公司、学校、项目、技能、职责、日期、证书或数字；只可重组、改写和突出。档案没有数字时不得自行量化。
2. 先逐条分析 JD 的核心职责、硬性要求和关键词，再从档案中寻找直接证据和邻近证据。正式简历只使用找到证据的内容，不能为了覆盖关键词硬塞内容。
3. 这不是档案复印：个人总结只保留 2-4 个与当前岗位最相关的事实；技能、工作和项目都按 JD 相关性排序；低相关、重复内容应删减。
4. bullet 使用“动作 + 场景/方法 + 可验证结果”的写法；只有档案原文已有数字时才保留量化结果。措辞可自然包含真实匹配的 JD 关键词，但不能关键词堆砌。
5. 工作、项目、教育和技能 item 必须输出 source_ref，值为对应档案数组位置，例如 work_experiences[0]、projects[1]、educations[0]、skills[2]。找不到来源的 item 不得输出。
6. relevance 为 0-10，表示该条内容对当前 JD 的相关度；同一模块按 relevance 降序。
7. 用户偏好必须落实：language=zh/en 决定全文语言；target_level 决定表达层级但不得夸大职责；highlight_direction 决定优先强调方向；page_limit 决定内容预算。
8. 严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "version_name": "公司_岗位_YYYYMMDD",
  "match_score": 82,
  "highlights": ["3年 Go 开发经验"],
  "gaps": ["缺少 Kubernetes 经验"],
  "suggestions": ["建议在项目经历中补充容器化部署内容"],
  "match_details": [
    {"requirement": "熟悉 Kubernetes", "priority": "must", "status": "direct",
     "evidence_refs": ["projects[0]"], "resume_usage": "项目经历第 1 项重点呈现"}
  ],
  "resume": {
    "header": {"name": "张三", "title": "后端开发工程师", "avatar_url": null,
               "contact": {"phone": "138****", "email": "a@b.com", "location": "北京"}},
    "sections": [
      {"type": "summary", "title": "个人总结", "content": "..."},
      {"type": "skills", "title": "专业技能",
       "items": [{"name": "Go", "category": "编程语言", "level": "精通", "relevance": 10, "source_ref": "skills[0]"}]},
      {"type": "experience", "title": "工作经历",
       "items": [{"company": "XX科技", "position": "后端开发", "period": "2023.06 - 至今", "relevance": 9,
                  "source_ref": "work_experiences[0]", "bullets": ["设计并实现高并发订单系统，QPS 从 1k 提升到 5k"]}]},
      {"type": "projects", "title": "项目经历",
       "items": [{"name": "订单系统", "role": "核心开发", "tech_stack": ["Go", "Redis"], "relevance": 10,
                  "source_ref": "projects[0]", "period": "2023.06 - 2024.01", "bullets": ["..."]}]},
      {"type": "education", "title": "教育经历",
       "items": [{"school": "北京大学", "major": "计算机科学", "degree": "本科", "period": "2019.09 - 2023.06", "source_ref": "educations[0]"}]},
      {"type": "certifications", "title": "证书与奖项",
       "items": [{"name": "AWS SAA", "issuer": "Amazon", "date": "2024.03"}]}
    ]
  },
  "enhancements": [
    {
      "gap": "JD 要求容器编排经验，档案中未体现",
      "basis": "档案中该公司已有系统部署与运维职责，可向用户核实是否还使用过容器编排",
      "risk": "medium",
      "target_source_ref": "work_experiences[0]",
      "suggested_bullets": ["负责容器化服务的部署编排、运行监控与故障处理，保障业务稳定交付"]
    }
  ]
}
match_details 必须逐条覆盖 JD 的硬性要求、核心职责和主要加分项：priority 只能是 must/core/bonus，status 只能是 direct/adjacent/missing；direct/adjacent 必须给出真实 evidence_refs，missing 不得写进正式简历。
sections 只保留有内容的模块。内容不是越短越好：档案事实充足时，page_limit=1 的个人总结目标 140-220 个中文字符（英文 80-130 words），工作与项目合计目标 3-4 个 item、高相关 item 目标 2-3 条完整 bullet、总 bullet 目标 7-12 条，技能 6-10 项；page_limit=2 时工作与项目 4-8 个、总 bullet 12-24 条。优先从档案已有 description、achievements、highlights 展开真实上下文；事实不足时宁可少写，也不得编造。始终优先保留高 relevance 内容。

【关于 enhancements —— 这部分规则最重要，务必与 resume 严格区分】
- resume 里的一切必须真实来自【用户档案】，上面的"诚实原则"不可违反、没有例外。
- enhancements 只用于向用户核实“是否在某段已有公司经历中确实做过、但档案漏写”的职责或技术；它们是待确认的表达建议，不是事实。
- 每条必须提供 target_source_ref，且只能指向现有 work_experiences[n]；无法合理指向已有工作经历时不要生成。
- 只输出 suggested_bullets，不得生成新项目名、项目周期、公司、职位、角色、证书或数字。
- basis 必须说明为什么建议挂到这段工作；risk 只能是 high/medium/low。
- 最多 4 条，宁缺毋滥。档案与 JD 已经匹配得很好时返回空数组 []。
- 严禁把 enhancements 自动写进 resume；是否确实做过、融入哪家公司由用户最终确认。"""
        user_prompt = (
            f"【用户档案】\n{_dumps(user_profile)}\n\n"
            f"【JD 原文】\n{jd_raw_text}\n\n"
            f"【JD 解析结果】\n{_dumps(jd_parsed)}\n\n"
            f"【用户偏好】\n{_dumps(preferences)}"
        )
        # 整份简历 JSON 很长；推理模型的思考 token 也要占用同一份 max_tokens 预算，
        # 用配置值（默认 4096/8192）必然被截断 → 这里给足长输出预算。
        budget = max(self._max_tokens, REASONING_OUTPUT_BUDGET if self._is_reasoning else 6000)
        return await self._safe_chat_json(system_prompt, user_prompt, max_tokens=budget)

    # ==================================================================
    # 4. 报名表字段映射
    # ==================================================================
    async def map_form_fields(
        self,
        form_fields: list[dict[str, Any]],
        profile_data: dict[str, Any],
    ) -> dict[str, Any]:
        """表单字段 × 用户档案 → 映射关系 + 填充值 + 置信度。"""
        system_prompt = """你是一位表单智能填写助手。给定【报名表字段列表】和【用户档案】，为每个表单字段找到档案中的对应字段并给出填充值。
规则：
1. profile_field 使用点路径表示档案位置，如 profiles.name、educations[0].school、work_experiences[0].company、family_members[0].name。
2. confidence 为 0-1 的置信度；低于 0.7 的放入 needs_review。
3. 档案中完全无对应信息的字段放入 unmapped。
4. value 必须来自档案原文，日期统一 YYYY-MM-DD 或 YYYY.MM 格式，不得编造。
5. 严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "mappings": [
    {"form_field": "姓名", "profile_field": "profiles.name", "confidence": 0.99, "value": "张三"}
  ],
  "unmapped": ["特长爱好"],
  "needs_review": ["政治面貌"]
}"""
        user_prompt = (
            f"【报名表字段列表】\n{_dumps(form_fields)}\n\n"
            f"【用户档案】\n{_dumps(profile_data)}"
        )
        return await self._safe_chat_json(system_prompt, user_prompt)

    # ==================================================================
    # 5. 面试 Q&A 生成
    # ==================================================================
    async def generate_interview_qa(
        self,
        resume_json: dict[str, Any],
        jd_parsed: dict[str, Any],
        question_count: int = 8,
    ) -> dict[str, Any]:
        """基于简历与 JD 生成面试问题与参考答案。"""
        system_prompt = f"""你是一位资深技术面试官。基于【候选人简历】和【JD 解析结果】，生成 {question_count} 个最可能被问到的面试问题及参考回答。
要求：覆盖 technical（技术深挖）/ project（项目细节）/ behavior（行为面）三类；技术问题要追问简历中的量化成果。
严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{{
  "questions": [
    {{
      "type": "technical",
      "question": "你提到将 QPS 从 1k 提升到 5k，具体是怎么做的？",
      "reference_answer": "首先通过压测定位瓶颈在数据库查询...",
      "key_points": ["缓存策略", "数据库优化", "并发模型"]
    }}
  ]
}}"""
        user_prompt = (
            f"【候选人简历】\n{_dumps(resume_json)}\n\n"
            f"【JD 解析结果】\n{_dumps(jd_parsed)}"
        )
        # 多道题 + 参考答案同样属于长输出，预算与简历生成保持一致
        budget = max(self._max_tokens, REASONING_OUTPUT_BUDGET if self._is_reasoning else 6000)
        return await self._safe_chat_json(system_prompt, user_prompt, max_tokens=budget)

    # ==================================================================
    # 6. 岗位调研（无联网，基于 JD 与简历推断）
    # ==================================================================
    async def job_research(self, resume_json: dict[str, Any], jd_parsed: dict[str, Any]) -> dict[str, Any]:
        """基于 JD 与简历推断岗位背景、考察重点与准备建议。"""
        system_prompt = """你是一位资深求职顾问。基于【候选人简历】与【JD 解析结果】做岗位调研分析（无联网，基于信息与行业经验推断）。
严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "position_analysis": "岗位定位与核心职责分析（3-5 句）",
  "company_points": ["公司业务/团队/技术栈可能的关注点"],
  "hot_topics": ["该岗位当前行业热点/高频考察方向"],
  "interviewer_focus": ["结合简历推断面试官会重点深挖的点"],
  "advice": ["面试前的准备建议"]
}
每个数组 3-6 条，简洁具体，不编造公司未披露的事实（推断需标注语气）。"""
        user_prompt = (
            f"【候选人简历】\n{_dumps(resume_json)}\n\n"
            f"【JD 解析结果】\n{_dumps(jd_parsed)}"
        )
        return await self._safe_chat_json(system_prompt, user_prompt)

    # ==================================================================
    # 7. 面试提纲
    # ==================================================================
    async def interview_outline(self, resume_json: dict[str, Any], jd_parsed: dict[str, Any]) -> dict[str, Any]:
        """生成按轮次组织的面试提纲 + 自我介绍要点 + 反问清单。"""
        system_prompt = """你是一位资深面试教练。基于【候选人简历】与【JD 解析结果】制定面试提纲。
严格以 JSON 输出，不要输出任何其他文字。JSON 结构：
{
  "rounds": [
    {"stage": "一面（技术基础）", "duration": "45min", "focus": ["考察方向"], "likely_questions": ["可能的问题"]}
  ],
  "self_intro_points": ["自我介绍应突出的要点"],
  "questions_to_ask": ["建议反问面试官的问题"]
}
rounds 2-4 轮（按该岗位常见流程推断），每轮 focus/likely_questions 各 3-5 条；self_intro_points 3-5 条；questions_to_ask 3-5 条。"""
        user_prompt = (
            f"【候选人简历】\n{_dumps(resume_json)}\n\n"
            f"【JD 解析结果】\n{_dumps(jd_parsed)}"
        )
        return await self._safe_chat_json(system_prompt, user_prompt)
