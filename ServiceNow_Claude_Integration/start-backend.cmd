@echo off
REM Starts the ServiceNow REST API backend on http://127.0.0.1:8095
REM Double-click this file, or run it from a terminal. Keep the window open.
REM snow.py and the web UI both talk to this server.

cd /d "%~dp0servicenow-mcp"

if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
) else if exist ".venv314\Scripts\python.exe" (
    set "PY=.venv314\Scripts\python.exe"
) else (
    echo Could not find a virtual environment in servicenow-mcp\.venv
    echo Create one, then install the project with:  pip install -e .
    pause
    exit /b 1
)

echo Starting the ServiceNow REST API on http://127.0.0.1:8095
echo Leave this window open. Press Ctrl+C to stop.
echo.

"%PY%" scripts\rest_api.py

echo.
echo The backend stopped.
pause
