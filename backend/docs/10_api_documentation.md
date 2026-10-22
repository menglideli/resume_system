# 10 · 智能简历投递系统 — API 接口文档（Hermes Skill 封装用）

> 版本 v1.0 · 2026-07-16 · Base URL：`{HOST}/api/v1`
> 完整 OpenAPI JSON 由 FastAPI 自动生成：`GET {HOST}/openapi.json`（Swagger UI：`{HOST}/docs`）

## 0. 通用约定

| 项 | 说明 |
| --- | --- |
| 认证方式 | `Authorization: Bearer <access_token>`（登录接口签发，默认有效期 24h） |
| 统一响应 | `{"code": 0, "message": "success", "data": {...}}`；`code != 0` 即业务失败 |
| Content-Type | JSON 接口 `application/json`；文件上传 `multipart/form-data` |
| 错误码 | 40000 参数错误 · 40010 文件处理失败 · 40100 未认证 · 40300 无权 · 40400 不存在 · 40900 冲突 · 42200 校验失败 · 50000 服务器错误 · 50200 AI 服务异常 |

---

## 1. 认证

### POST /auth/register — 用户注册
- Body：`{"username": "zhangsan", "email": "a@b.com", "password": "至少6位"}`
- Response data：用户对象 `{id, username, email, created_at}`

### POST /auth/login — 登录取 token
- Body：`{"username": "用户名或邮箱", "password": "..."}`
- Response data：`{"access_token": "eyJ...", "token_type": "bearer"}`

## 2. 用户档案 /profile

### GET /profile — 完整档案（含六类子记录）
- Response data：`{id, user_id, name, gender, birth_date, phone, email, location, political_status, avatar_url, summary, completeness_score, educations[], work_experiences[], projects[], skills[], certifications[], family_members[]}`

### PUT /profile — 更新基础信息
- Body：上述基础字段的任意子集

### 子资源 CRUD（六类，模式一致）
| 资源 | 路径 |
| --- | --- |
| 教育经历 | POST/PUT/DELETE `/profile/educations[/{id}]` |
| 工作经历 | POST/PUT/DELETE `/profile/work-experiences[/{id}]` |
| 项目经历 | POST/PUT/DELETE `/profile/projects[/{id}]` |
| 技能 | POST/PUT/DELETE `/profile/skills[/{id}]` |
| 证书 | POST/PUT/DELETE `/profile/certifications[/{id}]` |
| 家庭成员 | POST/PUT/DELETE `/profile/family-members[/{id}]` |

- 工作经历 Body 示例：`{"company": "XX科技", "position": "后端开发", "start_date": "2023-06-01", "description": ["负责订单系统"], "achievements": ["QPS 1k→5k"], "is_current": true, "priority": 8}`
- 技能：`{"name": "Go", "category": "编程语言", "proficiency": 5}`

## 3. JD 解析 /jd

### POST /jd/parse — 解析 JD（★Hermes 核心接口）
- Body：`{"raw_text": "JD 全文", "company_name": null, "position_title": null}`
- Response data：
```json
{"id": "jd-uuid", "parsed_data": {"company": "...", "position": "...", "hard_requirements": [], "soft_requirements": [], "core_responsibilities": [], "bonus_items": [], "keywords": [], "ats_keywords": [], "education_requirement": "...", "experience_years": "...", "salary_range": "..."},
 "match_preview": {"profile_completeness": 85, "estimated_match": 72}}
```

### GET /jd/list · GET /jd/{jd_id} · DELETE /jd/{jd_id}

## 4. 简历 /resumes

### POST /resumes/generate — 生成定制简历（★Hermes 核心接口）
- Body：`{"jd_id": "jd-uuid", "preferences": {"target_level": "senior", "highlight_direction": ["技术深度"], "page_limit": 1, "language": "zh", "template": "technical"}}`
- Response data：`{id, version_name, match_score, highlights[], gaps[], suggestions[], resume_data{...}, status}`

### POST /resumes/{resume_id}/export — 导出 PDF（★Hermes 核心接口）
- Body：`{"format": "pdf", "template": "technical"}`（template 可省略用简历默认值）
- Response：**PDF 文件下载流**（application/pdf），文件名 `{version_name}.pdf`

### POST /resumes/diagnosis — 简历诊断
- Body：`{"resume_text": "简历纯文本", "keywords_hint": ["微服务"]}`

### POST /resumes/{resume_id}/interview-qa — 面试 Q&A
- Body：`{"question_count": 8}`

### GET /resumes · GET /resumes/{resume_id} · DELETE /resumes/{resume_id}

## 5. 报名表 /forms（状态机 uploaded→analyzed→mapped→filled）

| 接口 | 说明 |
| --- | --- |
| POST /forms/upload | multipart 上传（字段名 `file`），支持 pdf/doc/docx/xls/xlsx |
| GET /forms/{id}/analysis | 解析表单结构 → `FormStructure{fields[], field_count, ...}` |
| POST /forms/{id}/mapping | 空 Body 走 AI 映射；传 `{"mappings": [...]}` 人工确认/覆盖 |
| POST /forms/{id}/fill | 按映射执行填充，返回 `filled_path` 与 `filled_data` |
| GET /forms/{id}/download | 下载填充后文件（PDF/DOCX/XLSX 或填写指南 txt） |

## 6. 投递管理 /applications

### POST /applications — 创建
- Body：`{"resume_id": "...", "jd_id": "...", "company_name": "...", "position_title": "...", "channel": "email|website|official", "notes": "...", "follow_up_date": "2026-08-01"}`

### GET /applications — 列表（筛选）
- Query：`status, channel, date_from, date_to, offset, limit`
- Response data：`{total, items[]}`（items 附带 `resume_version_name / jd_company / jd_position`）

### PUT /applications/{id} — 更新状态
- Body：`{"status": "applied|viewed|interview|offer|rejected", "notes": "...", "follow_up_date": "..."}`

### GET /applications/stats — 统计
- Response data：`{total, by_status{}, by_channel{}, conversion_rate, recent_7_days}`

### GET /applications/follow-ups — 待跟进（follow_up_date≤今天 且未终结）

### GET /applications/{id} · DELETE /applications/{id}

---

## 7. Hermes Skill 接入建议

### 7.1 需要暴露给 Hermes 的接口（按场景分组）

| 场景 | 接口 | Hermes 动作名建议 |
| --- | --- | --- |
| 粘贴 JD 生成简历 | POST /jd/parse → POST /resumes/generate → POST /resumes/{id}/export | `parse_jd` / `generate_resume` / `export_resume_pdf` |
| 报名表填写 | POST /forms/upload → analysis → mapping → fill → download | `upload_form` / `analyze_form` / `fill_form` / `download_form` |
| 投递追踪 | POST /applications、PUT /applications/{id}、GET /applications/stats、GET /applications/follow-ups | `track_application` / `update_application` / `application_stats` |
| 增值服务 | POST /resumes/diagnosis、POST /resumes/{id}/interview-qa | `diagnose_resume` / `interview_qa` |

档案维护（/profile 系列）建议由 Web 前端完成，Hermes 侧只读 `GET /profile` 用于映射与生成。

### 7.2 推荐数据流转方式
1. **编排收敛在 Hermes Skill**：Skill 内部顺序调用 parse → generate → export，对用户只暴露「粘贴 JD，返回 PDF」一个动作；中间产物（jd_id、resume_id）由 Skill 上下文保存，避免用户感知 UUID。
2. **文件传输**：PDF/报名表等二进制走「下载流 + 临时 URL」；Skill 拿到 FileResponse 后转存到会话附件。
3. **大文本**：JD/简历文本直接放请求体（<100KB 无压力）；避免引用传递。
4. **幂等**：同一 jd_id 重复 generate 生成新版本简历（version_name 带时间戳），天然支持「不满意再生成一版」。

### 7.3 认证 token 传递方式
- Skill 配置项中保存 `service_account` 的 access_token（或 refresh 机制），所有请求注入 `Authorization: Bearer {token}` 头。
- 多用户场景：Hermes 为每个终端用户托管各自 token（建议后续加 `POST /auth/refresh` 长会话机制）。
- token 有效期默认 24h（`ACCESS_TOKEN_EXPIRE_MINUTES` 可调）；401 时引导用户重新登录。

### 7.4 CORS 配置建议（允许 Hermes 域名访问）
`.env` 中设置（逗号分隔，勿用 `*` 配 credentials）：
```
CORS_ORIGINS=https://hermes.example.com,https://*.hermes.example.com,http://localhost:3000
```
FastAPI 侧已实现于 `app/main.py`（allow_origins 来自 `settings.cors_origin_list`，allow_credentials=True，methods/headers 全放开）。生产环境建议收敛 `allow_headers` 到 `Authorization, Content-Type`。

### 7.5 错误处理建议
Skill 统一判断 `code != 0` 即失败并透传 `message`；`50200`（AI 异常）建议自动重试一次再报错；`40400` 通常意味着 jd_id/resume_id 上下文过期，引导用户重新发起流程。
