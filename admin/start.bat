@echo off
setlocal
cd /d "%~dp0"
title PMHub Admin Server Starter

echo ==========================================================
echo   PM-Hub Admin Server Starter
echo ==========================================================

REM 1. Detect python command
set PYCMD=
where py >nul 2>&1 && set PYCMD=py
if not defined PYCMD where python >nul 2>&1 && set PYCMD=python
if not defined PYCMD where python3 >nul 2>&1 && set PYCMD=python3

if not defined PYCMD (
    echo [ERROR] Python not found. Please install Python.
    pause
    exit /b 1
)

REM 2. Remove stale port file from previous run
if exist ".server_port" del /f /q ".server_port" >nul 2>&1

REM 3. Launch server in a separate background window (with auto port fallback)
echo Starting Python Admin Server (with automatic port conflict fallback)...
start "PMHub Admin Server" %PYCMD% server.py

REM 4. Wait for server to initialize and detect bound port
echo Waiting for server to initialize and detect active port...
%PYCMD% -c "import urllib.request, time, sys, os; pf = '.server_port'; t0 = time.time(); p = None;\nwhile time.time() - t0 < 10:\n    if os.path.exists(pf):\n        try:\n            c = open(pf, 'r', encoding='utf-8').read().strip()\n            if c.isdigit():\n                p = c; break\n        except Exception:\n            pass\n    time.sleep(0.2)\nif not p:\n    print('[WARN] Port detection timed out. Falling back to port 8000.')\n    sys.exit(0)\nt1 = time.time()\nwhile time.time() - t1 < 10:\n    try:\n        with urllib.request.urlopen(f'http://localhost:{p}/admin/admin_dashboard.html', timeout=1) as res:\n            if res.status == 200:\n                print(f'Server is ready on port {p} (HTTP 200 OK)')\n                sys.exit(0)\n    except Exception:\n        pass\n    time.sleep(0.2)\nprint(f'[WARN] Readiness check timed out on port {p}.')"

REM 5. Open Admin Dashboard in default browser using the bound port
set ACTUAL_PORT=8000
if exist ".server_port" (
    set /p ACTUAL_PORT=<.server_port
)

echo Opening Admin Dashboard: http://localhost:%ACTUAL_PORT%/admin/admin_dashboard.html
start http://localhost:%ACTUAL_PORT%/admin/admin_dashboard.html

echo ==========================================================
echo   Server is running in background on port %ACTUAL_PORT%.
echo   You can close this window now.
echo ==========================================================
timeout /t 2 /nobreak >nul
