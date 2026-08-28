@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo    AIRAg - Generate Overview
echo    (progress and results are printed by Python)
echo ============================================
echo(

where python >nul 2>&1
if errorlevel 1 goto :nopython

if not exist "update_index.py" goto :noscript

python update_index.py
if errorlevel 1 goto :failed

echo(
echo --------------------------------------------
echo [DONE] Overview generated.
echo        Output file path is shown above.
echo        It is auto-generated - do not edit by hand.
echo --------------------------------------------
goto :end

:nopython
echo [ERROR] Python command not found in PATH.
echo(
echo   How to fix:
echo     1. Install Python from python.org
echo     2. During setup, tick "Add Python to PATH"
echo     3. Open a NEW window and run:  where python
echo(
echo   If Python is installed but not in PATH, replace the line
echo     python update_index.py
echo   near the top of this file with the full path, for example:
echo     "C:\Users\YourName\AppData\Local\Programs\Python\Python313\python.exe" update_index.py
goto :end

:noscript
echo [ERROR] update_index.py not found.
echo(
echo   This .bat must sit in the same folder as update_index.py.
echo   Current folder: %~dp0
goto :end

:failed
echo(
echo [ERROR] Generation failed - see the message above.
echo         No file was written. The previous one is untouched.

:end
echo(
echo Press any key to close...
pause >nul
