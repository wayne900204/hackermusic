@echo off
echo ============================================================
echo   Windows Audio Streaming Server
echo ============================================================
echo.
echo Installing dependencies...
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
echo.
echo Starting server...
python hacker_music.py
pause
