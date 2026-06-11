Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "cmd /c cd /d ""%USERPROFILE%\Documents\Antigravity\Garmin"" && streamlit run dashboard/app.py", 0, False
