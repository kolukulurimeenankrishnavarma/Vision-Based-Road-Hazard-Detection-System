@echo off
echo Starting RoadGuard Backend (serving both API and Frontend)...
start cmd /k "cd ..\backend && uvicorn main:app --port 8000"

echo.
echo Waiting for local server to start...
timeout /t 5 /nobreak >nul

echo.
echo Starting Instant Public Tunnel (pyngrok)...
python start_public.py
pause
