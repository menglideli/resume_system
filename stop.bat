@echo off
chcp 65001 >nul
title 智能简历投递系统 · 停止
cd /d "%~dp0"

echo ============================================
echo   智能简历投递系统 · 停止服务
echo   关闭后端 (8000) 与前端 (5173)
echo ============================================
echo.

REM ---------- 按窗口标题关闭（start.bat 启动的两个窗口） ----------
taskkill /FI "WINDOWTITLE eq Resume-Backend*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq Resume-Frontend*" /T /F >nul 2>&1

REM ---------- 按端口兜底关闭（防止窗口标题不匹配） ----------
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /T /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /T /F >nul 2>&1
)

echo 已停止。若仍有残留进程，请手动检查 8000 / 5173 端口占用。
echo.
pause
