@echo off
REM Starts the website on http://localhost:5173 - keep this window open
cd /d "%~dp0member4_frontend"
if not exist node_modules (
    echo Installing packages, first time only...
    call npm install
)
start "" http://localhost:5173
call npm run dev
pause
