@echo off
REM Run this only the first time, it installs the Python packages
cd /d "%~dp0"
python -m pip install -r requirements.txt
pause
