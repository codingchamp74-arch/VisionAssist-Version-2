@echo off
title VisionAssist
cd /d "%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Installing packages...
  py -3 -m pip install -r requirements.txt
  echo.
  echo Starting VisionAssist...
  py -3 main.py
  goto :end
)

where python >nul 2>&1
if %ERRORLEVEL%==0 (
  echo Installing packages...
  python -m pip install -r requirements.txt
  echo.
  echo Starting VisionAssist...
  python main.py
  goto :end
)

echo.
echo Python was not found.
echo Install it from https://www.python.org/downloads/
echo Tick "Add python.exe to PATH" during setup, then run this file again.
echo.
pause
exit /b 1

:end
if errorlevel 1 (
  echo.
  echo VisionAssist exited with an error. Read the message above.
  pause
)
