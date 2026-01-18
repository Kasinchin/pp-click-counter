@echo off
echo ==========================================
echo      ClickCounter App Builder Tool
echo ==========================================

REM 1. ติดตั้ง Library ให้ครบก่อน (กันลืม)
echo [1/3] Checking and installing dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing dependencies!
    pause
    exit /b %errorlevel%
)

REM 2. ล้างไฟล์ขยะเก่าๆ (ถ้ามี)
echo [2/3] Cleaning up old build files...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist ClickCounter.spec del ClickCounter.spec

REM 3. สั่ง Build (พร้อมฝัง config.json, รองรับ win32 และใส่ Icon)
echo [3/3] Building EXE...
echo       Target: src/main.py
echo       Config: config.json
echo       Icon:   icon.ico

python -m PyInstaller --noconsole --onefile ^
    --name="ClickCounter" ^
    --icon="icon.ico" ^
    --hidden-import=win32gui ^
    --hidden-import=win32process ^
    --add-data "config.json;." ^
    src/main.py

if %errorlevel% neq 0 (
    echo.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    echo    BUILD FAILED! Check errors above.
    echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
    pause
    exit /b %errorlevel%
)

echo.
echo ==========================================
echo    BUILD SUCCESSFUL!
echo    File is located in: dist/ClickCounter.exe
echo ==========================================
pause