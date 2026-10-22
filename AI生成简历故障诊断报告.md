# AI 生成简历故障诊断报告

> 诊断时间：2026-09-01 · 项目：kimi_resume_system
> 初始症状：「报错导致热重启，然后生成简历就卡住了」
> 结论：**三个独立缺陷叠加**，各自有实测证据，非猜测。

---

## 一、故障因果链

```
AI 输出触顶 (7336/8192 tokens)
        │
        ├─→ 抛出 "Connection error."  →  日志落到业务 logger
        │                                  │
        │                                  ↓
        │                          uvicorn 只给 uvicorn.* 配 handler
        │                          业务 logger 走 lastResort 被丢弃
        │                                  │
        │                                  ↓
        │                        Windows 无控制台 → CTRL_C_EVENT 送不到子进程
        │                        --reload 父进程卡在 join()，热重启僵死
        │                                  │
        │                                  ↓
        │                        后台 asyncio.Task 是纯内存态，随进程消失
        │                        DB 里 resumes.status 永远停在 pending
        │                                  │
        └──────────────────────────────────┴→ 前端永远显示「生成中」
```

三个环节缺一不可，所以修任何一个都不够。

---

## 二、根因与实测证据

### 缺陷 1：输出 token 预算不足

推理模型（kimi-k / k2 / k3 / thinking）的 **thinking tokens 同样计入 `max_tokens`**。
原配置 8192，实测生成一份简历实打实用了 **7336（90%）**，稍有波动即触顶。

| | 修复前 | 修复后 |
|---|---|---|
| completion_tokens | 7336 / 8192 | 7169 / 16384 |
| finish_reason | `length`（截断） | `stop`（正常结束） |

修复：`REASONING_OUTPUT_BUDGET = 16384`；并对 `finish_reason == "length"` 抛出可读的截断错误，
不再静默返回半截 JSON。

### 缺陷 2：AsyncOpenAI 连接池泄漏

每次调用都 `new AsyncOpenAI()` 且从不 `close()`，句柄持续累积直至耗尽。
日志中 14:13 与 14:25 两条 `Connection error.` 即为此。

修复：按 `(api_key, base_url, timeout)` 三元组缓存客户端实例复用。
同时把重试谓词 `RETRYABLE_ERRORS` 收窄 —— **401/400 不再重试**（配置错误重试多少次都没用）。

### 缺陷 3：进程重启后孤儿任务无人收敛（这是「卡住」的直接原因）

生成走的是 `asyncio.create_task` 后台任务，**纯内存态**。`--reload` 杀掉进程的瞬间任务即凭空消失，
而数据库里的 `status` 还停在 `pending`，前端轮询永远等不到终态。

修复：常驻 watchdog 协程，60 秒一轮巡检，把超过 600 秒仍在 `pending` 的任务置为 `failed` 并写入原因。
**实测：孤儿任务 44 秒后自动置 failed**，前端随即显示失败卡片 + 一键重试按钮。

---

## 三、补充：热重启本身在 Windows 上是坏的（本轮查实）

watchdog 只是"善后"。病根是 **`uvicorn --reload` 在 Windows 上会永久卡死**。

`uvicorn/supervisors/basereload.py:87-97`（0.32.1）：

```python
def restart(self):
    if sys.platform == "win32":
        os.kill(self.process.pid, signal.CTRL_C_EVENT)   # 只能投递给「进程组」
    self.process.join()                                   # 无超时，永久阻塞
```

`CTRL_C_EVENT` 只能投递给**进程组**，而 multiprocessing spawn 的子进程不是组 leader，
`GenerateConsoleCtrlEvent` 直接失败，子进程收不到信号，`join()` 就一直等下去。

**实测证据（三层）**

1. 探针实例：改 `.py` 后日志停在 `WatchFiles detected changes in 'x.py'. Reloading...`，
   之后 40 秒以上再无 `Waiting for application startup`，进程列表不变（没有新子进程）。
2. **带真实控制台窗口**同样卡死 —— 排除"没有控制台导致"的猜测。
   旧进程继续响应请求（`/health` 返回 200），所以**服务看起来完全正常，实际永久跑旧代码**，
   之后所有改动都静默失效。这个故障极难察觉。
3. 运行时给 `WatchFilesReload.__init__` 打桩，打印真实监听范围。

**`--reload-dir app` 是无效的**（`start.bat` 原注释以为它能缩小范围）：

```
config.reload_dirs   = [backend/app]   ← 启动日志打印的是这个，具有误导性
实际监听 reload_dirs  = [backend]      ← 真正监听整个 backend/
```

`WatchFilesReload.__init__` 会丢弃 cwd 的子目录，然后无条件追加 cwd。
独立验证：在 `storage/` 和 `backend/` 根目录放 `.py` 探针，**都触发了重启**。

**只有 `*.py` 会触发**（`FileFilter.default_includes = ["*.py"]`），
所以 `storage/` 下的导出 PDF、照片、上传文件**不会**杀掉后台任务——这点不用担心。

**已修**：`start.bat` 去掉 `--reload --reload-dir app`；`AGENTS.md` 记录完整结论。

---

## 三、顺带修掉的三个衍生缺陷

排查过程中暴露，一并处理：

| 缺陷 | 现象 | 修复后实测 |
|---|---|---|
| 面试准备必然 504 | `POST /interview/prepare` 同步跑三段 AI，耗时 5–10 分钟，撞上 Nginx `proxy_read_timeout` 默认 60 秒 | 改为后台任务，**提交响应 0.07 秒**；三段 AI 实测 35.0s / 68.2s / 103.4s 全部 `finish=stop` |
| 重试会清空已成功内容 | `retry()` 无条件重置 `resume_data` | 加状态守卫，对已 `generated` 的记录返回 HTTP 400；实测内容长度 172 → 172 未清空 |
| 空档案「假成功」 | 档案为空也照样烧 4 分钟，最后返回空简历 | 加两道守卫（入参空档案 / 返回空 sections），**实测 5 秒失败**并给出可操作提示 |

另：`resumes` 表新增 `preferences` 列保存生成时的模板/页数/语言等参数 —— 原先重试会用默认设置重跑，
用户拿到的简历和当初选的完全不是一回事。

---

## 四、验证结果（全部真实服务，非 mock）

- 端到端生成：**233 秒 → generated**；retry：**224 秒 → generated**，sections=5，匹配度 68
- 面试准备：230 秒 → generated（调研 5 字段 / 提纲 3 字段 / 题库 8 题）
- 全 API 面冒烟 **14/14 通过**（认证/档案/JD/简历/面试准备/照片/报名表/投递/管理端）
- PDF 导出链路：真实数据 → HTML 7394 字符 → **PDF 283KB**，`%PDF-` 魔数合法，端点 HTTP 200
- 变异测试 **4/4 全部被抓到**（注入缺陷后测试必须失败，否则测试是假的）
- 测试数：4 → 10 → 17 → 24 → 27 → **30 全绿**
- 前端 `npm run build` 通过；lint 基线 87 不变，改动零新增

---

## 五、需要你拍板的三件事

1. **6 条 failed 简历的处置**（均属 lixingliang）
   - `80c552de` / `5281a8a5` 两条是我排查时 `_fmt_error` 事故的残留 → **建议删除**
   - 其余 4 条是你遇到的原始故障证据（2 条 Connection error + 2 条重启中断）→ 现在可直接点「重试」恢复

2. **`.env` 里的 `KIMI_API_KEY` 是坏 key**（返回 401 Invalid Authentication）
   目前全靠 `system_config` 表里的 key 撑着。`.env` 那份应更新或删除，
   否则换个环境部署会直接 401 —— 而且这个失败点很隐蔽，因为代码会静默回退到 DB 配置。

3. **存量 failed 简历没有 `preferences` 快照**
   重试会用默认设置（technical / 1 页 / 中文）。如需按原参数恢复，需要回填 JSON。

---

## 六、过程中的两个坑（已写入 AGENTS.md）

- **MySQL UUID 格式**：`id` 是 `char(32)` **无横线**，而 API 返回**带横线**的 UUID。
  原生 SQL 传带横线的形式**静默匹配不到任何行** —— 本次因此得出过两次错误结论。
  更隐蔽的是随后的 `DELETE` 也会静默失败，留下脏数据。用 `uuid.UUID(hex=...)` 或 `CAST(id AS CHAR) LIKE 'abc12345%'`。

- **变异测试要按层次配对**：拆掉 `if is_profile_empty(...)` 后，测纯函数的那个用例照样全绿 ——
  它验的是函数本身，不是调用点。必须另外断言调用方的 `co_names`。

- **Python 3.11 字节码陷阱**：`BUILD_CONST_KEY_MAP` 会把全常量键的字典打包成**元组**入池，
  只扫字符串常量会漏检 dict key（测试因此误报过一次）。已递归展开元组。

---

## 七、第二轮：你提出的五个问题

### 1. 简历导出 405

**根因**：`apiDownload()` 用 `fetch(path, { headers })`，**没有指定 method → 默认 GET**，
而后端是 `POST /resumes/{resume_id}/export`。

**实测**：`GET` → **405** `{"detail":"Method Not Allowed"}`；
`POST` + `{"format":"pdf"}` → **200**，10 510 字节，`%PDF-1.4` 合法。

为什么一直没被发现：演示模式走的是**另一条分支**（前端本地生成 HTML），
根本不碰这个接口，所以 demo 下点导出永远正常。

**修复**：`apiDownload` 增加 `options` 参数并显式传 `method: "POST"`；
`template` 不传 —— 后端有 `template or resume.html_template or "technical"` 的回退，前端无需猜测。

### 2. 输入 localhost 就能直接进主页，没有校验 token

**根因**：`App.tsx` 的守卫是 `authed = !!getToken()` —— 只检查 `localStorage` 里**有没有**这个字符串，
从不问后端它是否有效。手写一个 `resume_token: "x"` 就能进后台。

顺带还有个隐蔽问题：token 过期后前端仍认为已登录，于是卡在「每个接口都 401」却不知道该重新登录的状态。

**修复**：新增 `GET /auth/me`，`App.tsx` 启动时调用，回答前显示 splash（三态
`checking / authed / anon`）。401 就清掉本地凭据并跳登录页。
**实测**：两种伪造 token 均返回 **401**；有效 token 返回真实用户名。
演示模式没有后端可问，仍保留「有令牌即已登录」的既有行为（否则 demo 模式会整个不可用）。

### 3. 登录后的名字和头像像是写死的

确实写死了 —— `AppLayout.tsx` 第 101 行硬编码 `文`、第 105 行硬编码 `张文路`。

**修复**：改为从 `/auth/me` 取真实用户名与邮箱；头像首字动态取（中文取首字、英文取首字母大写）；
配色由用户名 hash 出稳定色相 —— 同一个人永远是同一配色，不同人自动错开。
用户信息在 `db.ts` 里做了模块级缓存（`getMe` / `cachedMe` / `clearMe`），
启动校验和顶栏渲染共用一次请求。

### 4. 失败的任务能否删除

**后端 `DELETE /resumes/{id}` 一直都有**，是前端没接 —— `db.ts` 里没有对应函数，页面上也没有按钮。

**修复**：补 `deleteResume()`，详情页加「删除」按钮（带 AlertDialog 二次确认，
删除中状态禁用，pending 状态额外提示「正在跑的任务会被丢弃」），
列表里的失败项也加了快捷删除 chip。**实测**：自建探针记录 → `DELETE` → 200 → 列表条数 4→3，记录消失。

### 5. AI 编造缺失项目 + 让你二次选择是否补强

按你选的方案实现：**生成时顺带产出 / 局部插入 / 只补项目经历**。

**安全边界（这是该功能的核心，不是装饰）**：
- 生成 prompt 里明确区分：`resume` 内一切必须来自档案（诚实原则不变），
  `enhancements` 是**推测草稿**，每条都带 `basis`（推测依据）和 `risk`（三档风险）。
- 候选只存进 `resumes.enhancements` 列（迁移 `0008`），**绝不自动进 `resume_data`**。
- 前端「补强建议」页顶部有醒目警示：写进简历即代表对外声称做过，请只勾选确实做过的。
- 应用时局部插入到项目模块（秒回），不重跑整份简历 —— 重跑要 2–5 分钟，还可能改掉你已满意的部分。
- 用过的候选项从列表移除，防止同一条被反复插入。
- 硬校验：非 `generated` 拒绝、空勾选拒绝、下标越界拒绝。

**实测**：塞入 2 条候选 → 只勾第 2 条 → `apply [1]` 返回 200，
简历里只多了「监控告警体系搭建」，另一条仍在候选；空勾选与越界均被拦（422）；数据已完整还原。
变异测试 **4/4** 全部被抓到。

---

## 八、这一轮我自己引入、又被实测逮到的两个回归

两个都是**加新 JSON 列给存量表**时踩的 pydantic 坑，也都已写进 AGENTS.md：

1. **`Field(default_factory=list)` 救不了 `None`** —— 它只在字段**缺失**时生效。
   `from_attributes` 模式下属性存在、值为 `NULL` 时会原样传进去，pydantic 直接报 `list_type`。
   后果是 **`GET /resumes` 整个接口 500，整页简历都打不开**，不只是新功能不可用。
   修法：`@field_validator("enhancements", mode="before")` 把 `None` 归一成 `[]`。
   **pytest 全绿却没抓到** —— 因为测试不覆盖序列化层，是靠端到端实测发现的。

2. **`ge`/`le` 不能直接加在 `list[int]` 上** —— pydantic 会拿整个列表去比大小，
   报 `Unable to apply constraint 'ge' to supplied value`。
   修法：约束加到元素类型 `list[Annotated[int, Field(ge=0, le=7)]]`。

教训：给已有表加可空 JSON 列，**必须**用存量 `NULL` 数据实测一遍序列化，
单测覆盖不到这一层。
