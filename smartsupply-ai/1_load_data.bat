@echo off
REM Downloads the public datasets (AdventureWorks + CUAD), trains the models and makes the database
cd /d "%~dp0"

echo ===== Step 1: Downloading the datasets (skipped if already downloaded) =====
python data\download_data.py
if errorlevel 1 goto error

echo.
echo ===== Step 2: Loading the data and writing the documents =====
python data\load_data.py
if errorlevel 1 goto error

echo.
echo ===== Step 3: Training forecasting models =====
python member1_forecasting\forecast.py
if errorlevel 1 goto error

echo.
echo ===== Step 4: Testing the document assistant =====
python member2_rag\rag.py
if errorlevel 1 goto error

echo.
echo ===== Step 5: Creating database =====
python member3_backend\database.py
if errorlevel 1 goto error

echo.
echo DONE. The data is loaded.
echo Now double-click 2_start_backend.bat and then 3_start_frontend.bat
pause
exit /b

:error
echo.
echo Something went wrong. Read the message above.
pause
