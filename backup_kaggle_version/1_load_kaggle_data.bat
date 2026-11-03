@echo off
REM Uses the REAL Kaggle data (put the Kaggle files or zip in data\kaggle first)
cd /d "%~dp0"

echo ===== Step 1: Loading Kaggle data =====
python data\load_kaggle_data.py
if errorlevel 1 goto error

echo.
echo ===== Step 2: Training forecasting models =====
python member1_forecasting\forecast.py
if errorlevel 1 goto error

echo.
echo ===== Step 3: Creating database =====
python member3_backend\database.py
if errorlevel 1 goto error

echo.
echo DONE. Real Kaggle data is loaded.
echo Now double-click 2_start_backend.bat and then 3_start_frontend.bat
pause
exit /b

:error
echo.
echo Something went wrong. Read the message above.
pause
