@echo off
REM Registers this project's MCP server with Claude Desktop.
REM Quit Claude Desktop first - it rewrites its config file when it exits.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install-desktop-mcp.ps1"

echo.
pause
