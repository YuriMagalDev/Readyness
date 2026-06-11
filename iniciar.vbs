Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d ""%USERPROFILE%\Documents\Antigravity\Garmin"" && (if not exist web\dist (cd web && npm install && npm run build && cd ..)) && start """" http://localhost:8000 && uvicorn api.main:app --port 8000", 0, False
