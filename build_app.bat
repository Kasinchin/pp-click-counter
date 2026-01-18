@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo Building Application...
python -m PyInstaller --noconsole --onefile --name="ClickCounter" --hidden-import=win32gui --hidden-import=win32process src/main.py

echo Done! File is in dist folder.
pause