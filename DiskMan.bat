@echo off
REM DiskMan - Disk Manager by SamSeen
REM Windows launcher script

echo Starting DiskMan...
python DiskMan.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Error running DiskMan. Please make sure Python is installed and in your PATH.
    echo You can download Python from https://www.python.org/downloads/
    echo.
    pause
)
