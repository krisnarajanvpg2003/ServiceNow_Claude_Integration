# Using this ServiceNow integration from Claude Desktop

Claude Desktop can only reach outside tools over the Model Context Protocol, so
`mcp_server.py` in this folder is an MCP adapter. Every tool it exposes runs the
same `snow.py` command the CLI and the web chat use, so all three clients share
one code path, one dataset cache and one set of export writers.

    Claude Desktop  ──MCP (stdio)──>  mcp_server.py
                                          │ runs
                                          v
                                      snow.py  ──HTTP──>  rest_api.py  ──HTTPS──>  ServiceNow
                                                          (holds the credentials)

## Setup

**1. Start the backend.** Double-click `start-backend.cmd` and leave the window
open. Everything below fails without it — the MCP server has no ServiceNow
credentials of its own; the backend holds them.

**2. Point Claude Desktop at the server.** Quit Claude Desktop completely (right
click the tray icon > Quit — closing the window is not enough; it rewrites its
config file on exit and would discard the change), then double-click
`install-desktop-mcp.cmd`.

That script matters more than it looks, because **where the config lives depends
on how Claude Desktop was installed**:

| Install | claude_desktop_config.json |
| --- | --- |
| Microsoft Store / MSIX | `%LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\` |
| Downloaded installer | `%APPDATA%\Claude\` |

A packaged app's writes to `%APPDATA%` are redirected into its own container, so
putting the file in the plain location does nothing for a Store install — the
app never sees it. The script finds the folder the installed app actually reads,
merges the `servicenow` entry into whatever settings are already there, and
writes a `.bak` first. The machine this was set up on has the **Store** build.

The entry it adds:

```json
{
  "mcpServers": {
    "servicenow": {
      "command": "C:\\Mcp_Demo 1\\ServiceNow_Claude_Integration\\servicenow-mcp\\.venv314\\Scripts\\python.exe",
      "args": ["C:\\Mcp_Demo 1\\ServiceNow_Claude_Integration\\mcp_server.py"],
      "env": { "SNOW_API": "http://127.0.0.1:8095" }
    }
  }
}
```

If you move the project, re-run the script — it rebuilds those paths from its own
location. The interpreter must be one that has the `mcp` package installed;
`.venv314` does.

**3. Open Claude Desktop.** "servicenow" appears in the tools menu with 14
tools. If it does not, the app most likely overwrote the config on its way out:
quit it again, re-run `install-desktop-mcp.cmd`, and reopen.

## What you can ask for

- "How many active incidents are there, by priority?" → `snow_stats`
- "Show me INC0015548" → `snow_incident`
- "List the users in IT" → `snow_query`
- "Give me all 636 users as an Excel file" → `snow_export`
- "Same list as a PDF" → `snow_export`

`snow_export` writes a real `.xlsx`, `.pdf` or `.csv` into `exports/` and returns
both the folder path and a `http://127.0.0.1:8095/exports/...` link, which works
in a browser while the backend is running.

## Writing

Read-only by default. To let Claude Desktop create and update records, add
`SNOW_ALLOW_WRITE` to the `env` block and restart:

```json
"env": { "SNOW_API": "http://127.0.0.1:8095", "SNOW_ALLOW_WRITE": "1" }
```

The ServiceNow account in `servicenow-mcp/.env` also needs the matching role
(usually `itil` for incidents), otherwise ServiceNow answers 403 / "ACL
Exception" and no setting here will change that.

## If "servicenow" does not appear, or its tools fail

- Is the backend running? Ask Claude to run `snow_health`, or open
  <http://127.0.0.1:8095/health> in a browser.
- Did the config survive? Open the file the table above points at and check that
  `mcpServers.servicenow` is still in it.
- Check Claude Desktop's MCP log, in the `logs` folder next to that config file:
  `mcp-server-servicenow.log`.
- Run the server by hand to see startup errors:
  `servicenow-mcp\.venv314\Scripts\python.exe mcp_server.py`
  It should sit silently waiting for input — that means it started cleanly.
