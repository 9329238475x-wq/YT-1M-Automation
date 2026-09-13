@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Creating Python virtual environment...
  py -m venv .venv
)
call ".venv\Scripts\activate.bat"
echo Installing/updating backend dependencies...
python -m pip install -r backend\requirements.txt
start "YT-1M Browser" cmd /c "timeout /t 3 >nul & start http://127.0.0.1:8000/"
echo Starting YT-1M Automation backend...
python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
pause
