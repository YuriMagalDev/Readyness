@echo off
cd /d "%USERPROFILE%\Documents\Antigravity\Garmin"
call .venv\Scripts\activate 2>nul || echo Sem venv, usando Python do sistema
streamlit run dashboard/app.py
pause
