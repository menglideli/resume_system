# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Local dev server (hot-reload)
uvicorn app.main:app --reload
pytest tests/ -v                          # Run all tests

# Docker
docker compose up -d --build              # Full stack (app + MySQL + Redis + Nginx)
docker compose exec app alembic revision --autogenerate -m "description"  # Generate migration
docker compose exec app alembic upgrade head                                 # Apply migrations
```

## Architecture

**Layered**: Routers → Services → Repositories → Models, with Pydantic schemas for request/response validation. All API responses use `{code: int, message: str, data: T}`.

**Database**: SQLAlchemy 2.0 async with `asyncmy` driver for MySQL. `AsyncSession` is injected via `get_db()` dependency. Repositories call `await self.db.flush()` after mutations; services call `await self.db.commit()` to finalize transactions. No `autoflush`.

**Auth**: JWT (HS256) via `python-jose`. `get_current_user` dependency resolves `User` from Bearer token and raises `UnauthorizedException` (custom exception, not HTTPException). Endpoints receive `user: User = Depends(get_current_user)`.

**Error handling**: All business exceptions inherit `AppException(code, http_status)`. Three global handlers in `main.py` catch `AppException`, `RequestValidationError`, and bare `Exception`, converting all to the unified `{code, message, data}` format. Never raise `HTTPException` directly — use the subclasses in `app/utils/exceptions.py`.

**AI integration**: `AIService` wraps Kimi API via OpenAI-compatible SDK (`AsyncOpenAI`). `_chat_json` is the core method — tenacity retry (3x exponential backoff) on network errors, `response_format={"type": "json_object"}`, with a markdown-wrapped JSON fallback parser. Five AI methods: `resume_diagnosis`, `parse_jd`, `generate_resume`, `map_form_fields`, `generate_interview_qa`.

**Profile entity model**: `Profile` is a "header" table with six sub-entity tables (Education, WorkExperience, Project, Skill, Certification, FamilyMember) linked via `profile_id` FK. All sub-entities share a dynamic CRUD pattern — `ProfileRepository` uses generic `add_sub_entity(model, profile_id, data)` / `update_sub_entity(...)` / `delete_sub_entity(...)` accepting the ORM class. The router (`profile.py`) auto-registers POST/PUT/DELETE for all six sub-resources via `_register_sub_routes()`.

**PDF rendering**: `ResumeRenderer` uses Jinja2 templates (three variants: `resume_technical.html`, `resume_management.html`, `resume_default.html`) to render `resume_data` JSON to HTML. Playwright Chromium prints to A4 PDF; falls back to WeasyPrint on failure. Set `CHROMIUM_EXECUTABLE_PATH` env var for custom browser.

**Form processing pipeline**: Upload → parse (`FormParser`: pypdf/pdplumber for PDF, python-docx for Word, openpyxl for Excel; OCR for scanned PDFs via paddleocr) → AI field mapping (`map_form_fields`) → fill (`FormFiller`: writes back to PDF AcroForm / Word table cells / Excel cells) → download.

## Key files

| File | Role |
|------|------|
| `app/config.py` | All settings via `pydantic-settings`, from `.env` / env vars |
| `app/database.py` | `AsyncSessionLocal` factory, `get_db` dependency, `Base` |
| `app/main.py` | App factory: CORS, exception handlers, route registration |
| `app/utils/exceptions.py` | Custom exception classes — always raise these, never `HTTPException` |
| `app/utils/dependencies.py` | `get_current_user` / `get_current_user_id` JWT dependencies |
| `app/utils/security.py` | `hash_password`, `verify_password`, JWT create/decode |
| `app/repositories/base.py` | `BaseRepository[ModelT]` — generic CRUD to extend |
| `app/services/ai_service.py` | Kimi API client (single instance per service call) |
| `app/services/resume_renderer.py` | Jinja2 → Playwright/WeasyPrint PDF pipeline |
| `app/services/form_parser.py` | PDF/Word/Excel → `FormStructure` |
| `app/services/form_filler.py` | Mapping data → filled PDF/Word/Excel |
| `alembic/env.py` | Reads `DATABASE_URL` from `app.config.settings` |
| `sql/init.sql` | Initial table DDL for first Docker startup |

## Patterns to follow

- Router endpoints call `success(data, message)` from `app/schemas/common.py` for consistent responses
- Repository methods take explicit kwargs/filters — do NOT pass raw user input or `**kwargs` from routes
- Service methods receive `user_id` (UUID, not the User object) except AI methods
- `_dump(obj)` in profile router converts ORM → dict generically via `__table__.columns` (used for sub-entity responses)
- Repos never commit; services always commit. Exception: `get_or_create_profile` commits internally because it may create.
- Async everywhere — `await` all DB calls, AI calls, and file I/O (use `aiofiles` or `asyncio.to_thread`)
