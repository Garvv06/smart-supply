@echo off
REM Starts the backend on http://localhost:8000 - keep this window open
cd /d "%~dp0member3_backend"
python -m uvicorn app:app --port 8000
pause
