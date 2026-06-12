@echo off
cd /d "%USERPROFILE%\Documents\Antigravity\Garmin"
if not exist "web\dist" (
  echo Building frontend...
  cd web && call npm install && call npm run build && cd ..
)
start "" http://localhost:8000
uvicorn api.main:app --port 8000 --reload
pause
