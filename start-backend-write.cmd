@echo off
REM Starts the backend with WRITING ENABLED for the web chat at localhost:5174.
REM
REM Same server as start-backend.cmd, plus --allow-write, which lets the Claude
REM chat in the browser create, update and delete ServiceNow records instead of
REM only reading them. Whether a write actually succeeds still depends on the
REM roles of the account in servicenow-mcp\.env.
REM
REM Use start-backend.cmd instead if you want the browser chat to stay read-only
REM - for example before sharing the UI with share.ps1.

echo.
echo  *** WRITING IS ENABLED ***
echo  The chat at localhost:5174 can create, update and DELETE records.
echo  Anyone who can reach this UI can change your ServiceNow instance.
echo.

call "%~dp0start-backend.cmd" --allow-write
