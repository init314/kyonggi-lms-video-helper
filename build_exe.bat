@echo off
setlocal

cd /d "%~dp0"

echo Building StudySsalmeok...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\build_exe.ps1"
set BUILD_EXIT_CODE=%ERRORLEVEL%

echo.
if not "%BUILD_EXIT_CODE%"=="0" (
    echo Build failed with exit code %BUILD_EXIT_CODE%.
    echo.
    pause
    exit /b %BUILD_EXIT_CODE%
)

echo Build completed successfully.
echo Output: dist\StudySsalmeok\StudySsalmeok.exe
echo.
pause
