@echo off
chcp 65001 >nul
title 智能简历投递系统 · 一键启动
cd /d "%~dp0"

echo ============================================
echo   智能简历投递系统 · 一键启动
echo   后端  http://localhost:8000  (API /docs)
echo   前端  http://localhost:5173
echo   前提：本机 MySQL 已启动（默认 .env 指向本地 3306）
echo ============================================
echo.

REM ---------- 后端（先自动执行数据库迁移，再启动服务） ----------
REM 不要加 --reload：Windows 下 uvicorn 热重启会永久卡死（实测确认）。
REM 原因：BaseReload.restart() 用 os.kill(pid, CTRL_C_EVENT) 停止子进程，而该信号只能投递给
REM 「进程组」，multiprocessing 起的子进程不是组 leader，信号送不到，随后无超时的 join() 永久阻塞。
REM 表现：日志停在 "WatchFiles detected changes in 'x.py'. Reloading..." 再无下文，
REM 旧进程继续跑旧代码，之后所有改动都不再生效（服务看起来是健康的，极难察觉）。
REM 另外 --reload-dir app 是无效的：uvicorn 会丢弃 cwd 的子目录并改为监视整个 backend/，
REM 所以任何 .py（含 tests/、alembic/versions/）都会触发重启。（storage 下的 PDF/图片不会触发，
REM 只有 *.py 才会，这点不用担心。）
REM 需要热更新时请手动重启本窗口，或单独跑 uvicorn 不带 --reload。
if exist "backend\venv\Scripts\activate.bat" (
    start "Resume-Backend" cmd /k "cd /d "%~dp0backend" && venv\Scripts\activate.bat && alembic upgrade head && uvicorn app.main:app --host 127.0.0.1 --port 8000"
) else (
    echo [提示] 未找到 backend\venv，使用系统 Python 启动后端（如缺依赖请先 pip install -r requirements.txt）
    start "Resume-Backend" cmd /k "cd /d "%~dp0backend" && alembic upgrade head && uvicorn app.main:app --host 127.0.0.1 --port 8000"
)

REM ---------- 前端 ----------
if not exist "frontend\node_modules" (
    echo [提示] 前端依赖未安装，将在新窗口先执行 npm install
    start "Resume-Frontend" cmd /k "cd /d "%~dp0frontend" && npm install && npm run dev"
) else (
    start "Resume-Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
)

echo.
echo 已在两个新窗口分别启动后端与前端。
echo 首次启动会自动创建管理员账号 admin（密码见 backend/.env 的 ADMIN_DEFAULT_PASSWORD，默认 admin123）。
echo.
pause
