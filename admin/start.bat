@echo off
setlocal
cd /d "%~dp0"
title PMHub Admin Server

echo ==========================================================
echo   PM-Hub Admin Server Starter
echo ==========================================================

REM 1. Stop any existing process listening on port 8000
for /f "tokens=5" %%a in ('netstat -a -n -o ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo Stopping existing process on port 8000 (PID %%a)
    taskkill /F /PID %%a >nul 2>&1
)

REM 2. Detect python command
set PYCMD=
where py >nul 2>&1 && set PYCMD=py
if not defined PYCMD where python >nul 2>&1 && set PYCMD=python
if not defined PYCMD where python3 >nul 2>&1 && set PYCMD=python3

if not defined PYCMD (
    echo [ERROR] Python not found. Please install Python.
    pause
    exit /b 1
)

REM 3. Launch server in a separate background window
echo Starting Python Admin Server on port 8000
start "PMHub Admin Server" %PYCMD% server.py

REM 4. Wait for server to become ready
echo Waiting for server to initialize
timeout /t 2 /nobreak >nul

REM 5. Open Admin Dashboard in default browser
echo Opening Admin Dashboard: http://localhost:8000/admin/admin_dashboard.html
start http://localhost:8000/admin/admin_dashboard.html

echo ==========================================================
echo   Server is running in background.
echo   You can close this window now.
echo ==========================================================
timeout /t 3 /nobreak >nul
