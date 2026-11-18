@echo off
title Apartment Gatepass - Start
cd /d "%~dp0"
echo ================================================
echo APARTMENT VISITOR & DELIVERY GATEPASS
echo ================================================
where python >nul 2>nul || (echo Install Python 3.10+ first.& pause& exit /b 1)
where node >nul 2>nul || (echo Install Node.js 18+ first.& pause& exit /b 1)
if not exist "backend\.venv" (cd backend & python -m venv .venv & cd ..)
echo Installing backend dependencies...
call backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
if errorlevel 1 (echo Backend setup failed.& pause& exit /b 1)
if not exist "frontend\node_modules" (cd frontend & call npm install & cd ..)
if errorlevel 1 (echo Frontend setup failed.& pause& exit /b 1)
start "Gatepass API" cmd /k "cd /d ""%~dp0backend"" && .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
timeout /t 3 /nobreak >nul
start "Gatepass Website" cmd /k "cd /d ""%~dp0frontend"" && npm run dev -- --host 127.0.0.1"
timeout /t 4 /nobreak >nul
start "" "http://localhost:5173"
echo Website: http://localhost:5173
echo API docs: http://127.0.0.1:8000/docs
echo Keep both server windows open.
pause
