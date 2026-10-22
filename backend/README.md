# 智能简历投递系统 · 后端

基于 FastAPI 的智能简历投递辅助后端，覆盖两大场景：
- **招聘网站场景**：粘贴 JD → AI 解析 → 定制简历 → 导出 PDF
- **招聘公告场景**：上传报名表（PDF/Word/Excel）→ AI 字段映射 → 自动填充 → 下载

## 技术栈
FastAPI · SQLAlchemy 2.0(asyncmy) · MySQL 8 · Redis 7 · Kimi API（OpenAI 兼容）· Jinja2 + Playwright/WeasyPrint · JWT · 前端 React 18 + TailwindCSS（前后端分离）

## 快速开始

### 方式一：Docker Compose（推荐）
```bash
cp .env.example .env          # 填入 KIMI_API_KEY、JWT_SECRET_KEY
docker compose up -d --build
```
首次启动 MySQL 自动执行 `sql/init.sql` 建表；app 启动时执行 alembic 迁移（若有）。
包含四个服务：`web`（前端 Nginx，80 端口）、`app`（FastAPI，8000）、`db`（MySQL 8，3306）、`redis`（6379）。
> web 服务构建上下文为 `../app`（前端工程目录），请保持两个目录同级。
> 前端通过 Nginx 将 `/api/` 反向代理到后端，浏览器只需访问 80 端口。

### 方式二：本地运行
```bash
pip install -r requirements.txt
playwright install chromium                # PDF 导出
mysql -uroot -p -e "CREATE DATABASE resume_system CHARACTER SET utf8mb4"
mysql -uroot -p resume_system < sql/init.sql
cp .env.example .env                       # 修改 DATABASE_URL 指向本地 MySQL
uvicorn app.main:app --reload
```

### 方式三：一键启动（Windows）
在仓库根目录双击 `start.bat`，会分别在新窗口启动后端（uvicorn，自动激活 `backend/venv`）与前端（npm run dev）。
前提：本机 MySQL 已启动，且 `backend/.env` 的 `DATABASE_URL` 指向本地数据库（该脚本不负责启动数据库）。
首次启动自动创建管理员账号 `admin`（密码取 `ADMIN_DEFAULT_PASSWORD`，默认 `admin123`），并将 `.env` 中的 KIMI 配置导入 `system_config` 表；之后可在前端「后台管理」页面增删用户、在线修改 Kimi API 配置（即时生效，无需改 .env 重启）。

### 前端（前后端分离）
```bash
cd ../app                                # 前端工程（React + Vite）
npm install
echo "VITE_API_BASE_URL=http://localhost:8000/api/v1" > .env.local
npm run dev                              # 访问 http://localhost:5173
```
未启动后端时前端自动进入「演示模式」（内置 mock 数据），可完整浏览所有页面。

## 验证节点（对应指令集）
| 节点 | 命令 |
| --- | --- |
| 服务启动 | `uvicorn app.main:app --reload` → 访问 http://localhost:8000/health |
| 管理员账号 | 首次启动自动创建 `admin` / `admin123`（`ADMIN_DEFAULT_PASSWORD`） |
| 后台管理 | 管理员登录后 `GET /api/v1/admin/users`、`GET/PUT /api/v1/admin/config` |
| Kimi API 连通 | 登录后 `POST /api/v1/resumes/diagnosis` 传简历文本 |
| 面试准备 | 简历详情→面试准备页签，或 `POST /api/v1/resumes/{id}/interview/prepare` |
| 版块自定义字段 | 档案页各版块「添加字段」，或 `GET/POST /api/v1/profile/field-defs` |
| 照片库 | 侧边栏「照片库」上传工作/生活照，或 `POST /api/v1/photos/upload` |
| PDF 导出 | `POST /api/v1/resumes/{id}/export` |
| 单元测试 | `pytest tests/ -v` |

## 文档
- 架构设计：`docs/01_architecture.md`
- 接口文档（Hermes Skill 封装用）：`docs/10_api_documentation.md`
- 交互式 API 文档：http://localhost:8000/docs

## 目录结构
```
app/
├── main.py            # 应用入口（CORS/异常处理/路由注册）
├── config.py          # Pydantic Settings 配置
├── database.py        # 异步引擎/Session/Base
├── models/            # SQLAlchemy ORM（users/profile/子实体/jd/resume/form/application/system_config/profile_blocks 等）
├── schemas/           # Pydantic 请求/响应模型
├── routers/           # auth/profile/jd/resume/form/application/admin
├── services/          # 业务层 + ai_service + 渲染 + 报名表处理 + 运行时配置/管理员
├── repositories/      # 数据访问层
├── utils/             # 异常/依赖(JWT)/安全/文件
└── templates/         # 简历 HTML 模板（technical/management/default）
```
