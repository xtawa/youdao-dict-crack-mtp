@echo off
setlocal
python "%~dp0unlock_x7pro.py" --unlock
set "UNLOCK_EXIT=%ERRORLEVEL%"
echo.
if "%UNLOCK_EXIT%"=="0" echo ADB is ready. Run: adb -d shell
if not "%UNLOCK_EXIT%"=="0" echo Unlock failed. Keep the complete error output for diagnosis.
pause
exit /b %UNLOCK_EXIT%
