@echo off
REM Starts the ServiceNow REST API backend on http://127.0.0.1:8095
REM Double-click this file, or run it from a terminal. Keep the window open.
REM snow.py, the web UI and the Claude Desktop MCP server all talk to this server.

cd /d "%~dp0servicenow-mcp"

REM Pick a virtual environment that actually has an interpreter in it: an empty
REM .venv folder is left over on some machines, so test for python.exe itself.
set "PY="
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"
if not defined PY if exist ".venv314\Scripts\python.exe" set "PY=.venv314\Scripts\python.exe"
if not defined PY (
    echo Could not find a virtual environment with python.exe in servicenow-mcp.
    echo Looked in .venv\Scripts and .venv314\Scripts.
    echo Create one, then install the project with:  pip install -e .
    pause
    exit /b 1
)

REM Run from the source tree whether or not the package is pip-installed into
REM this environment. An editable install that points at a folder which has
REM since moved would otherwise fail with "No module named servicenow_mcp".
set "PYTHONPATH=%~dp0servicenow-mcp\src;%PYTHONPATH%"

echo Starting the ServiceNow REST API on http://127.0.0.1:8095
echo Using %PY%
echo Leave this window open. Press Ctrl+C to stop.
echo.

"%PY%" scripts\rest_api.py %*

echo.
echo The backend stopped.
pause
