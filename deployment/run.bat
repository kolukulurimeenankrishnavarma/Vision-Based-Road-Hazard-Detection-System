@echo off
echo Starting RoadGuard Backend API...
start cmd /k "cd ..\backend && uvicorn main:app --reload"

echo.
echo Starting RoadGuard Frontend Server...
start cmd /k "cd ..\frontend && python -m http.server 8080"

echo.
echo NOTE: Make sure you have python installed and added to PATH.
echo.
timeout /t 3 /nobreak >nul
start http://localhost:8080
