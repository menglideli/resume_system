# AGENTS.md

This file provides guidance to Qoder (qoder.com) when working with code in this repository.

## Repository layout

Monorepo with two independent apps for an AI-powered resume application system (Kimi API):

- `backend/` — FastAPI + SQLAlchemy 2.0 (async MySQL) + Redis. Two business flows: (1) paste JD → AI parse → generate tailored resume → export PDF; (2) upload application form (PDF/Word/Excel) → AI field mapping against user profile → auto-fill → download.
- `frontend/` — React 19 + Vite + TypeScript + Tailwind + shadcn/ui (Radix primitives in `src/components/ui/`).

Backend docs worth reading before deeper work: `backend/docs/01_architecture.md` (data flows) and `backend/docs/10_api_documentation.md`.

## Commands

All commands assume CWD `backend/` or `frontend/` respectively. PowerShell: use `;` not `&&`.

### Backend (Python, venv in `backend/venv`)

```bash
uvicorn app.main:app                          # dev server → http://localhost:8000 (/health, /docs)
                                              # 不要加 --reload：Windows 下会永久卡死，见「Windows reload」章节
pytest tests/ -v                              # all tests (no DB/external deps needed)
pytest tests/test_smoke.py::test_health -v    # single test

# Docker full stack (app + MySQL 8 + Redis + Nginx frontend)
docker compose up -d --build

# Alembic migrations (async engine; env.py reads DATABASE_URL from app.config.settings)
alembic revision --autogenerate -m "description"
alembic upgrade head
```

First Docker startup runs `sql/init.sql` for initial DDL. Requires `.env` (copy `.env.example`) with at least `KIMI_API_KEY`, `JWT_SECRET_KEY`, `DATABASE_URL`. PDF export needs `playwright install chromium`.

**Tests are DB-free and network-free by design** (`tests/`, 24 cases). Two conventions that came out of real regressions:
- Structural assertions use `tests/helpers.py::accessed_names(func)` (attribute/global names) and `string_consts(func)` (string literals, including dict keys). Both walk nested code objects. Do not assert on `inspect.getsource()` text — comments and docstrings contain the same keywords and cause false positives. Two bytecode quirks on Python 3.11: comprehensions live in a separate code object the outer function's `co_names` never sees, and dict literals with all-constant keys are packed into a **tuple** constant by `BUILD_CONST_KEY_MAP`, so `string_consts` must flatten tuples or it won't find the key you're asserting on.
- A pure-function test does **not** prove the call site calls it. Verify with a mutation that matches the layer: removing `if is_profile_empty(...)` left `test_empty_profile_is_detected` green because that test exercises the helper directly, not the caller — the missing guard needed its own `accessed_names` assertion on `_run_generation_impl`.
- A module-level `def` written at the wrong indent silently truncates the preceding class body: syntax stays valid, `import` succeeds, and an AST walk passes, while every later method becomes a nested function of the wrong callable. An import check proves nothing here — assert with `getattr(Service, "method", None)`. Verify a new test actually fails by injecting the defect (mutation test) before trusting it.

### One-click launcher (Windows)

`start.bat` at the repo root opens two windows: backend (venv activate → `alembic upgrade head` → `uvicorn app.main:app`, **deliberately without `--reload`** — see the Windows reload section, falls back to system Python) and frontend (`npm install` if needed, then `npm run dev`). `stop.bat` kills both via window title (`Resume-Backend*`/`Resume-Frontend*`) with a port-based fallback (netstat PIDs on 8000/5173). The scripts do NOT start MySQL — local MySQL on 3306 must already be running with `backend/.env` `DATABASE_URL` pointing at it. Keep `alembic.ini` ASCII-only: alembic reads it with the locale encoding (GBK on Chinese Windows) and crashes on UTF-8 Chinese comments.

**A long-lived backend started as an ad-hoc background process can get killed as collateral.** A uvicorn instance on 8000 died with **no traceback and no shutdown log** — the last entry was a `GET /health 200`, then the process was simply gone — right after unrelated short-lived processes (a stub server, a second Vite instance) started the same way were stopped by PID. Nothing matched the uvicorn PID in any kill command; the processes are evidently grouped, so terminating one batch takes the others with it. Prefer `start.bat` for anything the user should keep running, and treat an unexplained `health` failure as "check whether it was collateral damage" before hunting for a bug in the app. Symptom to recognise: port 8000 with **nothing** listening and a log that just stops.

Confirmed reproduction and a working workaround: stopping the old backend by PID and immediately relaunching it the usual way produced a process that logged `Application startup complete` / `Uvicorn running on http://127.0.0.1:8000` and then died within ~19 s with no shutdown log. Relaunching detached from the process group survived:

```bash
(nohup venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 >> /c/Users/<user>/AppData/Local/Temp/uvicorn_backend.log 2>&1 &)
```

Note the log tail is what distinguishes the two cases — a killed process still shows a clean `startup complete`, which is exactly what a crash does not look like. Confirm the reload actually took effect by comparing the process creation time against the source file's mtime (`wmic process where ProcessId=<pid> get CreationDate` vs `stat -c '%y' app/services/ai_service.py`); a healthy `/health` alone only proves *something* is listening.

### Frontend

```bash
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc -b && vite build
npm run lint       # eslint .
npm run preview
```

No test runner is configured. API base configured via `VITE_API_BASE_URL` (defaults to `http://localhost:8000/api/v1`).

## Backend architecture

**Layered**: Routers → Services → Repositories → Models, Pydantic schemas for I/O. Routers only validate and dispatch; all AI calls live in `app/services/ai_service.py`; DB access only via `repositories/` (extend `BaseRepository[ModelT]` in `repositories/base.py`).

**Unified response**: every *JSON* endpoint returns `{code: int, message: str, data: T}` via `success(data, message)` from `app/schemas/common.py`. Three global handlers in `main.py` convert `AppException`, `RequestValidationError`, and bare `Exception` into this envelope. **Never raise `HTTPException`** — raise the subclasses in `app/utils/exceptions.py` (all inherit `AppException(code, http_status)`).
- **Exception: file-download endpoints return a raw `FileResponse`, not the envelope** — `POST /resumes/{id}/export` (PDF), `GET /photos/{id}/file`, `GET /forms/{id}/download`. They need the auth header, which an `<img src>` or plain link can't send, so the client fetches the blob with `apiBlobUrl()` / `apiDownload()` and builds an object URL. Don't "fix" these to return the envelope — the frontend depends on the raw bytes.

**Transaction discipline** (critical convention): repositories call `await self.db.flush()` after mutations but **never commit**; services call `await self.db.commit()` to finalize. No `autoflush`. Only exception: `get_or_create_profile` commits internally.

**Async everywhere**: `AsyncSession` (asyncmy driver) injected via `get_db()`; `await` all DB/AI calls; use `aiofiles`/`asyncio.to_thread` for file I/O.

**Auth**: JWT HS256 via `python-jose`. Endpoints take `user: User = Depends(get_current_user)` (`app/utils/dependencies.py`); admin-only routers use `Depends(require_admin)` which checks `user.is_admin`. Password hashing + token create/decode in `app/utils/security.py`.

**Admin & runtime config**: `app/routers/admin.py` (prefix `/admin`, all `require_admin`) manages users (create/update/delete/reset-password, last-admin delete protection in `admin_service.py`) and Kimi config. Runtime config lives in the `system_config` table via `ConfigService` (`services/config_service.py`): per-key precedence DB value → `.env` fallback (`get_effective_kimi_config`), API key masked as `******`+last 4 on read, masked placeholder on PUT means "keep unchanged". `AIService.__init__(config=...)` accepts the effective config dict; because service constructors are sync, `jd_service`/`resume_service`/`form_service` fetch DB config through a lazy `async def _ai()` helper. Startup lifespan calls `seed_initial_data()`: creates `admin` user (password `ADMIN_DEFAULT_PASSWORD` env, default `admin123`) if none exists and imports non-empty `KIMI_*` from `.env` into `system_config` (wrapped in try/except so DB unavailability never blocks startup).

**Custom profile blocks**: two-level user-defined structures — `ProfileBlock` (name + `fields` JSON `[{name,label,type}]`) → `ProfileBlockEntry` (`data` JSON validated against the block's field defs; unknown keys rejected, missing keys filled with None). Routes under `/profile/blocks` in `routers/profile.py` (including `PUT /blocks/{id}` for rename / field-list adjustment; dropped fields' old values stay in entry JSON); blocks/entries are included in `profile_to_dict` (used by AI flows) keyed by field labels.

**Custom fields per section**: besides blocks, every profile section (basic + six sub-entities) accepts user-defined extra fields. Definitions live in `custom_field_defs` (`CustomFieldDef`: profile_id FK, section key matching sub-resource routes, name/label/type; UNIQUE(profile_id, section, name)); values live in a `custom_fields` JSON column on each of the seven tables. `ProfileService.create_field_def` validates section membership (`SECTIONS` in `schemas/custom_field_def.py`) and name clashes against the `FIXED_FIELDS` map in `profile_service.py`. Field values are merged into `profile_to_dict` rows, so AI resume generation and form mapping see them automatically. Routes: `GET/POST /profile/field-defs`, `PUT/DELETE /profile/field-defs/{id}` (PUT changes label/type only — name is the storage key and immutable); deleting a definition keeps stored values (hidden, not purged).

**Photo library**: private per-user image storage (`photos` table, `PhotoService` in `services/photo_service.py`, routes `/photos` in `routers/photo.py`). `POST /photos/upload` is multipart (`file` + `category` form field: work/life/other), images only (jpg/jpeg/png/gif/webp/bmp), size capped by `MAX_UPLOAD_SIZE`; files stored UUID-named under `PHOTO_DIR` (`./storage/photos/{user_id}/`). `GET /photos/{id}/file` serves via `FileResponse` behind JWT (frontend can't put headers on `<img>`, so it fetches the blob via `apiBlobUrl` in `lib/api.ts` and renders an object URL). `DELETE` removes both DB row and physical file.

**AI integration**: `AIService` wraps Kimi (OpenAI-compatible `AsyncOpenAI`). Core method `_chat_json` — `response_format={"type": "json_object"}` plus a markdown-wrapped-JSON fallback parser, tenacity retry (3× exponential backoff) **only on retryable errors** (`APITimeoutError` / `APIConnectionError` / `RateLimitError` / `InternalServerError`); 401/400 等 4xx 直接失败，不浪费三次重试。The seven AI entry points: `resume_diagnosis`, `parse_jd`, `generate_resume`, `map_form_fields`, `generate_interview_qa`, `job_research`, `interview_outline`. Reasoning models (name containing `kimi-k`/`k2`/`k3`/`thinking`) get no `temperature` param (API rejects anything but 1) and a client timeout floored at **600s**; prompt payloads are serialized via `_dumps` (`default=str`) because profile dicts contain `date` objects. Statuses: resume `status` walks `pending → generated | failed` (`error_message` column stores the failure reason).

**Reasoning models must not be left on the default `reasoning_effort`.** `kimi-k3` reports `supports_thinking_type: "only"` with `reasoning_efforts.default_effort = "max"`. Long calls are the whole risk here: a resume generation that runs for minutes can come back as `httpcore.RemoteProtocolError: Server disconnected without sending a response`, surfaced to the user as the useless `Kimi API 调用失败: Connection error.` (one observed failure took 501 s). **Raising `KIMI_TIMEOUT` does not fix this** — the client timeout is already floored to 600 s for reasoning models, so the connection is cut elsewhere. The lever is `reasoning_effort`, configurable via `KIMI_REASONING_EFFORT` (`low`/`high`/`max`, default `high`; only sent for reasoning models — non-reasoning models reject the param with 400). Measured end-to-end on a real profile (7 093-char JSON):

| effort | 耗时 | completion tokens | 补强候选 |
|---|---|---|---|
| `low` | 60 s | 1 843 | — |
| `high` | **73.7 s** | 3 038 | 3 条 |
| `max` | 196.8 s | 7 708 | 4 条 |

**The real fix for the disconnect is streaming, not a lower `reasoning_effort`.** Lowering effort only shortens the call; it does not remove the failure mode — with `high` the *same* real profile succeeded in 73.7 s once and then failed at 564.7 s later the same day. The mechanism: while a reasoning model thinks, the server sends **zero bytes**, so a non-streaming request is a long fully-silent connection, and the middle of the network drops it as idle. Make the error message part of the fix, not an afterthought. The original failure surfaced as `Kimi API 调用失败: Connection error.` — seven words that cost a full investigation because they said nothing about what had already been tried or what to rule out. Connection-class errors now report the retry count and name the dead ends (`不是 API Key 或参数错误，调大超时也无效`). A test asserts the wording, so it cannot quietly rot back into the useless version.

`_chat_json` therefore always requests `stream=True` (`stream_options={"include_usage": True}` to still get token counts) and reassembles the content in `_stream_collect`. Measured on the same failing profile: non-streaming **564.7 s → fail**; streaming **124.5 s → success**, 1756 chunks with a 13 s max gap (that gap is just the wait for the first chunk). Never switch this back to a buffered call.

Be precise about this: **`max` is not guaranteed to fail** — it succeeded at 196.8 s in a later run. It is 2.7× slower and burns 2.5× the tokens, which is what pushes a call into the window where a disconnect is likely. `high` keeps generation well clear of that window; `max` is the option when the user wants the more detailed output and accepts a 3–5 minute wait and the occasional failure.

Two dead ends worth not re-walking:
- **Not the proxy.** `http_proxy.py` appears in every traceback (system proxy is `127.0.0.1:7890`, `ProxyEnable=1`). Probing a socket that goes idle after the TLS handshake, the proxy cut at 31.2 s and a direct connection cut at **30.1 s** — identical, so the proxy is not the discriminator.
- **Not a stale pooled connection.** The cached client was suspected of reusing a connection the server had already closed. After 45 s of idle (past the 30 s figure above), both a default client and a `retries=1` client reused the pooled connection and succeeded in 3.7 s / 4.5 s.

Three hard-won constraints in this layer — do not undo them:
- **Client reuse**: `AsyncOpenAI` instances are cached in `_CLIENT_CACHE` keyed by (api_key, base_url, timeout). Every `AIService()` used to build a fresh client with its own httpx pool and never closed it; long-running processes exhausted handles and started failing with `Connection error.`
- **Reasoning-model token budget**: thinking tokens count against `max_tokens` too. A real resume generation measured 7336 completion tokens against an 8192 cap — any richer profile gets truncated into invalid JSON. Long outputs (resume generation, interview Q&A) therefore request `REASONING_OUTPUT_BUDGET` (16384) for reasoning models, and `_chat_json` raises a readable error when `finish_reason == "length"` instead of failing later in the JSON parser.
- **Module-level helpers only**: `_dumps` and `_fmt_error` live at module level. Dropping a module-level `def` in the middle of `AIService` silently truncates the class body — the file still imports, but every method below it disappears from the class. `tests/test_ai_service.py` guards this.

**Interview prep per resume**: `interview_preps` table (one row per resume, `resume_id` UNIQUE, FK CASCADE) stores `research`/`outline`/`questions` JSON generated by `InterviewService.prepare` (调研 → 提纲 → 题库，重新生成整体覆盖). Routes `POST /resumes/{id}/interview/prepare|regenerate` and `GET /resumes/{id}/interview`; resume list/detail include `has_interview_prep` (repo loads via `selectinload(Resume.interview_prep)`).

**Profile entity model**: `Profile` is a header table with six sub-entity tables (Education, WorkExperience, Project, Skill, Certification, FamilyMember) via `profile_id` FK. `ProfileRepository` uses generic `add_sub_entity(model, profile_id, data)` / `update_sub_entity` / `delete_sub_entity` accepting the ORM class; the profile router auto-registers POST/PUT/DELETE for all six sub-resources through `_register_sub_routes()`, with `_dump(obj)` converting ORM → dict generically via `__table__.columns`. Follow this dynamic pattern when adding a new sub-entity rather than writing per-entity routes.

**Resume data flow**: `POST /jd/parse` stores raw JD + AI-parsed JSON → `POST /resumes/generate` creates a `pending` resume row and returns immediately; the AI work runs in a background task (`_run_generation_bg` in `resume_service.py`, own `AsyncSessionLocal` session, tracked in `_BG_TASKS`, **15-minute** `GEN_TIMEOUT` cap) that writes `resume_data`/match analysis and flips status to `generated`, or records `error_message` on failure. `POST /resumes/{id}/export` renders via `ResumeRenderer`. Frontend polls the list every 4s while any resume is `pending`, shows per-task elapsed time, and offers one-click retry on `failed`.

**Exporting flips `status` to `exported` — this quietly breaks repeated smoke tests.** Anything that exercises the export endpoint, then re-runs and looks for a `generated` resume, will find none and silently skip its own assertions. After a smoke run, reset with `UPDATE resumes SET status='generated' WHERE status='exported'`. Two related traps when writing such a script: the export response is **raw PDF bytes, not the JSON envelope** (unconditionally `json.loads()`-ing it throws and looks exactly like a failed export — the endpoint was returning a valid 10 510-byte `%PDF-1.4` all along), and the first export after a backend restart has to cold-start Playwright/Chromium, so allow a generous timeout (steady-state is ~3s).

**Generation must never report a false success** — two guards in `_run_generation_impl`, keep both:
- `is_profile_empty(profile_dict)` runs *before* the AI call. An empty profile produces a resume with zero `sections` and still costs a full 3–4 minute reasoning round, so fail fast with an actionable message telling the user to fill in their profile.
- After the call, a payload with no `sections` is rejected instead of being written as `generated`. Otherwise the user sees "生成成功" and opens a blank page with nothing to debug.

**Retry semantics** (`ResumeService.retry`): only `failed`/stuck-`pending` rows are re-run; calling it on a `generated` resume is rejected (400) rather than silently overwriting. It deliberately does **not** clear `resume_data` — if the retry fails, the previous content is still there. Generation preferences are persisted in `resumes.preferences` (migration `0007_resume_preferences`) so a retry re-runs with the original template/page-limit/language instead of defaults.

**MySQL UUID gotcha**: `id` columns are `Uuid` mapped to `char(32)` **without** dashes, but API responses and Pydantic give you dashed UUID strings. Raw SQL like `WHERE id = :i` silently matches nothing when you pass the dashed form (and a follow-up `DELETE` then deletes nothing, leaving test rows behind). Use `uuid.UUID(hex=...)` / `CAST(id AS CHAR) LIKE 'abc12345%'` in ad-hoc queries. This has already produced two false conclusions in one session.

**Orphaned generation tasks** (the "stuck on 生成中 forever" bug): tasks live only in process memory, so `uvicorn --reload` (or any restart / crash) kills them silently and the row stays `pending` — the frontend then spins forever. Two layers of defense, keep both:
- `sweep_stale_pending()` at startup (main.py lifespan) marks every `pending` row as `failed`.
- `watchdog()` — a coroutine started in the same lifespan and cancelled on shutdown — calls `reap_stale_pending()` every 60s, marking `pending` rows older than `STALE_AFTER` (600s) as `failed` **unless** their id is in `_RUNNING`, the dict of tasks this process is actually executing. This heals orphans without requiring a restart. `_run_generation_bg` registers/clears `_RUNNING` in try/finally.
- `POST /resumes/{id}/retry` (`ResumeService.retry`) re-runs a failed/interrupted task **in place** — it resets the existing row instead of creating a duplicate. Frontend uses it for both `failed` and for `pending` older than 12 minutes (`isStuck` in `ResumesPage.tsx`).
- Note: `_RUNNING` is per-process. Multi-worker deploys (`uvicorn --workers > 1`) would need a DB heartbeat column instead.
- Both reapers compare **`updated_at`**, never `created_at`. Retry/re-regenerate updates an existing row, so `created_at` still points at first creation — using it as the "pending since" origin would reap a task submitted seconds ago, and under multiple workers would kill a task another process is legitimately running.

**Interview prep is a background task too**: `InterviewService.prepare` runs three AI calls (job research → interview outline → Q&A bank) serially; a single one measured ~140s, so the old synchronous endpoint took 5–10 minutes and died at Nginx's default 60s `proxy_read_timeout` with a 504. It now submits and returns a `pending` row immediately (`_run_prep_bg`, `PREP_TIMEOUT` 900s, `reap_stale_preps` folded into the same watchdog). Two deliberate choices:
- On regenerate the **old content is kept** until the new result lands — a failed regeneration must not wipe what the user already has. The frontend shows a `failed` banner above the retained content.
- `prepare()` returns early if the `resume_id` is already in `_RUNNING`, so double-clicking can't spawn two tasks burning tokens and racing to write the same row.
- Schema: `interview_preps.status` (`pending`/`generated`/`failed`, migration `0006_interview_prep_bg` backfills `generated`) + `error_message`. Frontend polls `GET /resumes/{id}/interview` every 5s while `prep.status === "pending"`.
- `POST /resumes/{id}/interview-qa` is a legacy synchronous single-AI-call endpoint the frontend no longer uses — do not reuse it as a model for new work.

**Logging**: uvicorn only attaches handlers to `uvicorn.*`, so business loggers (`resume_service`, `ai_service`) used to emit nothing below WARNING — a 3-minute AI generation was completely silent in the console. `_configure_logging()` in `main.py` adds a root entry to uvicorn's `LOGGING_CONFIG` (with a plain StreamHandler fallback for non-uvicorn runners). Application loggers are the way to observe generation progress; don't remove it.

**Windows: do not use `uvicorn --reload`.** It wedges permanently — verified, not theoretical. `BaseReload.restart()` (uvicorn 0.32.1, `supervisors/basereload.py:87-97`) does `os.kill(self.process.pid, signal.CTRL_C_EVENT)` then `self.process.join()` with **no timeout**. `CTRL_C_EVENT` can only be delivered to a **process group**, but the child is a `multiprocessing` spawn that is not a group leader, so `GenerateConsoleCtrlEvent` fails, the child never exits, and `join()` blocks forever. Observed behaviour: `WARNING: WatchFiles detected changes in 'x.py'. Reloading...` and then nothing — no new process, ever. The old child keeps serving requests, so the server *looks* healthy while running stale code; every later edit is silently ignored. **This is not a console-attachment issue**: it reproduces identically with a real `cmd` console window (`Start-Process`, 40s+ wait, process list unchanged). Run `uvicorn app.main:app --host 127.0.0.1 --port 8000` with no `--reload` and restart by hand.
- `--reload-dir app` does **not** narrow the watch. `WatchFilesReload.__init__` drops any directory nested under cwd, then appends cwd, so the real watch scope is all of `backend/` — any `.py` under `backend/` (including `tests/`, `alembic/versions/`) triggers a reload. Verified two ways: (1) instrumenting the reloader at runtime prints `实际监听 reload_dirs = [backend]`; (2) a `.py` probe in `storage/` and in the `backend/` root both trigger a reload, which is impossible if only `app/` were watched.
- The startup line `Will watch for changes in these directories: [...]` prints `config.reload_dirs`, **not** the actual watch scope — it is misleading, don't trust it.
- Only `*.py` changes trigger a reload (`FileFilter.default_includes = ["*.py"]`). Writes to `storage/` (exported PDFs, uploaded photos, application forms) and `.pyc` files do **not** — so exporting a PDF while a generation runs does not kill it.
- When you must debug reloader behaviour, note the child's stdout/stderr is **block-buffered** when redirected to a file — set `PYTHONUNBUFFERED=1` or you will read a stale/empty log and draw wrong conclusions.

**PDF rendering**: `ResumeRenderer` fills one of three Jinja2 templates in `app/templates/` (`resume_technical.html`, `resume_management.html`, `resume_default.html`), prints A4 PDF with Playwright Chromium, falls back to WeasyPrint. `CHROMIUM_EXECUTABLE_PATH` env var overrides the browser.
- **The WeasyPrint fallback does not work on Windows**: importing it raises `OSError` (it needs Pango/Cairo/GTK system libraries that pip can't provide), so on a Windows dev machine a Playwright failure is a hard failure, not a graceful degradation. Playwright is the only real path there — keep `ms-playwright` Chromium installed. The Docker image installs `libpango-1.0-0 libcairo2 fonts-noto-cjk` plus `playwright install chromium`, so both paths should work in the container.
- Verified end-to-end with real profile data: 4-section resume → 283 KB PDF, valid `%PDF-` header; export endpoint returns HTTP 200 with `content-type: application/pdf` and an RFC 5987 `filename*=utf-8''...` header (Chinese filenames survive).

**Form pipeline**: upload → `FormParser` (pdfplumber for PDF, python-docx for Word, openpyxl for Excel; OCR for scanned PDFs) produces `FormStructure` → `ai_service.map_form_fields` maps fields to profile with confidence → `FormFiller` writes values back (PDF AcroForm / Word table cells / Excel cells) → download. Form status progresses uploaded → analyzed → mapped → filled in the `forms` table.

**Resume enhancements (AI 补强建议)** — `resumes.enhancements` JSON column, migration `0008`.
When generating a resume the AI also returns candidate *projects* covering gaps where the JD asks for something the profile simply doesn't contain. **These are speculative drafts, not facts, and must never be written into `resume_data` automatically.** The generation prompt states this boundary explicitly, `sanitize_enhancements()` filters malformed entries, and the result is stored in its own column. The user ticks items in the 「补强建议」 tab; `POST /resumes/{id}/enhancements/apply` then merges only the chosen ones into the projects section (local insert — never regenerates the whole resume, which would cost 2–5 min and could overwrite content the user already liked). Applied items are removed from the candidate list so the same one can't be inserted twice. Hard rules: reject unless `status == "generated"`, reject empty selection, reject out-of-range indices. The UI carries a prominent warning that this content is fabricated and must be verified — writing it into a resume is a claim the user actually did the work.

**Pydantic traps when adding a nullable JSON column to an existing table** (both hit for real on `enhancements`):
- `Field(default_factory=list)` only fires when the key is **absent**. Under `from_attributes`, an attribute that exists with value `None` is passed straight through and pydantic raises `list_type` — which took `GET /resumes` to a blanket **500**, breaking every resume page, not just the new feature. Add a `@field_validator(..., mode="before")` that maps `None → []`.
- `ge`/`le` cannot be attached to `list[int]`; pydantic tries to compare the whole list and fails with `Unable to apply constraint 'ge' to supplied value`. Put the constraint on the element type: `list[Annotated[int, Field(ge=0, le=7)]]`.

**Patterns**: service methods receive `user_id` (UUID string, not the User object) except AI methods; repository methods take explicit kwargs/filters — never pass raw user input or `**kwargs` through from routes.

## Frontend architecture

**Dual-mode API client** (`src/lib/api.ts`): on startup `detectDemo()` probes `{base}/health` (1.5s timeout). Backend reachable → real API calls; unreachable → **demo mode** driven entirely by in-memory mock data (`src/lib/mock.ts`), so the whole UI works with no backend. Auth token in `localStorage` (`resume_token`); `api()` unwraps the `{code, message, data}` envelope and throws on `code !== 0`. Note `FileResponse` endpoints (export / photo file / form download) return raw bytes, not the envelope — never read them with `api()`.

**`apiDownload(path, filename, options)` — always pass `method` explicitly.** `fetch` defaults to GET, and the export endpoint is `POST`, so every real (non-demo) PDF export returned **405 Method Not Allowed**. Demo mode hid this completely because it short-circuits to client-side HTML generation and never calls the endpoint. Verified: GET → 405 `{"detail":"Method Not Allowed"}`, POST + `{"format":"pdf"}` → 200, 10 510 bytes, valid `%PDF-1.4`.

**Data access layer** (`src/lib/db.ts`): single choke point every page uses. Each function branches `if (isDemo())` → mock, else → `api()`. **Any new backend integration must be added here with both branches**, and `src/lib/types.ts` mirrors backend response shapes for both modes.

**Routing** (`src/App.tsx`): react-router v7; all pages live under `AppLayout`. Pages: Dashboard, Profile, JD, Resumes, Forms, Applications, Admin (one file per page in `src/pages/`).

**Auth gate is two-layer, and both are required.** On mount `App.tsx` calls `GET /auth/me`; until it answers, a splash screen is shown (`checking` state) — never render routes off `localStorage` alone. A token string in `localStorage` proves nothing: hand-writing `resume_token: "x"` used to be enough to walk straight into the dashboard. `/auth/me` returning 401 clears both `resume_token` and the cached user and bounces to `/auth`. Demo mode has no backend to ask, so it keeps the old "token present ⇒ logged in" behaviour intentionally (verified: two forged tokens both rejected with 401, valid token returns the real username). User info is cached in `db.ts` (`getMe` / `cachedMe` / `clearMe`) so the header avatar and the gate share one request; `AppLayout` renders the real username, a derived initial, and a hue hashed from the username — all previously hardcoded as 「文」/「张文路」. The `/admin` route and the "后台管理" nav item are gated by `isAdmin()` (`api.ts`, backed by `localStorage resume_admin`, set from `is_admin` in the login response); demo mode is always admin.

**The splash gate must never be able to hang forever — `fetch` has no default timeout.** `api()` wraps every call in `AbortController` with `API_TIMEOUT_MS = 30_000`; the startup gate uses a short `ME_TIMEOUT_MS = 8_000` because it blocks first paint. Without this, a backend that answers `/health` but hangs on `/api/v1/auth/me` leaves the promise permanently pending, `detectDemo()` succeeds (so no demo-mode fallback kicks in), and the user stares at 「正在连接服务…」 forever with no way out. Verified in a real browser against a stub backend that deliberately sleeps on `/auth/me`: at 1.5s and 4.5s still on splash, at 12.5s released to `/auth` with `resume_token` cleared. Mutation-checked by raising the timeout to 300s — the same run then reported "still stuck at 12.5s", proving the probe actually tests the timeout rather than passing by accident.

**401 handling is global but path-scoped.** `api()` clears the token and fires `onUnauthorized` listeners on any 401 **except** paths starting with `/auth/` — `/auth/login` returns 401 for a wrong password, and treating that as "session expired" would wipe the token the user is about to set. `App.tsx` registers the listener to drop the cached user and return to `anon`.

**UI**: shadcn/ui style components (`components.json` configured, `@/` alias → `src/`), Tailwind with `tailwindcss-animate`, framer-motion, recharts, sonner for toasts, react-hook-form + zod.

## Deployment notes

`backend/docker-compose.yml` orchestrates `app` (8000), `db` (MySQL, 3306), `redis` (6379), and `web` (Nginx, 80 — proxies `/api/` to the backend). **Run it from `backend/`** — the compose file lives there, not at the repo root. The `web` service build context was `../app` (no such directory — the frontend is `frontend/`) and made `docker compose up --build` fail outright; it is now `../frontend`. Frontend Nginx config: `frontend/nginx.conf`.

**Any reverse proxy must set `client_max_body_size` to at least the backend's `MAX_UPLOAD_SIZE`.** `frontend/nginx.conf` now sets `25m` (backend allows 20MB, per `app/config.py`). Without it Nginx's 1MB default returns `413` at the proxy — the request never reaches FastAPI, so the app's own "文件大小超过限制（20MB）" check never runs and the frontend gets an Nginx HTML error page instead of the JSON envelope. Phone photos are routinely 3–8MB, so this breaks ordinary photo uploads in any Docker deploy.

**Every reverse proxy in front of this app must raise `proxy_read_timeout` above ~600s.** Nginx defaults to 60s and a single Kimi reasoning-model call alone measures ~140s, so JD parsing and resume diagnosis will 504 on a default config. Generation endpoints are background tasks now, but the timeout is still required as a floor for the remaining synchronous AI calls.

**`sql/init.sql` and Alembic coexist — do not "fix" this.** `init.sql` creates all 18 tables with `CREATE TABLE IF NOT EXISTS` and contains no `alembic_version` row, which looks like a cold-start conflict (Alembic would run 0001 against tables that already exist). It isn't one: every migration in `alembic/versions/` is written defensively, inspecting with `sa.inspect(op.get_bind())` and returning early when the table/column already exists. Verified against a scratch database — all seven migrations apply cleanly on top of an `init.sql`-populated schema (18 tables + `alembic_version` = 19 afterwards, nothing duplicated). The container entrypoint's `alembic upgrade head` is safe.
