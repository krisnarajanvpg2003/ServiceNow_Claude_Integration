<#
    Registers this project's MCP server with Claude Desktop.

    Claude Desktop keeps claude_desktop_config.json in one of two places, and
    which one depends on how it was installed:

      Store / MSIX build   %LOCALAPPDATA%\Packages\Claude_*\LocalCache\Roaming\Claude\
      Installer build      %APPDATA%\Claude\

    A packaged app's writes to %APPDATA% are redirected into its container, so
    dropping the file in the plain location has no effect on a Store install.
    This script finds the one the installed app actually reads, merges the
    "servicenow" entry into whatever is already there, and leaves every other
    setting untouched. A .bak copy is written first.

    Quit Claude Desktop before running this: it rewrites the same file when it
    exits, which would discard the change.

    Usage:  right-click > Run with PowerShell, or double-click install-desktop-mcp.cmd
#>

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$server = Join-Path $root 'mcp_server.py'

# The interpreter must be one that has the `mcp` package: the project venv.
$python = Join-Path $root 'servicenow-mcp\.venv314\Scripts\python.exe'
if (-not (Test-Path $python)) {
    $alt = Join-Path $root 'servicenow-mcp\.venv\Scripts\python.exe'
    if (Test-Path $alt) { $python = $alt }
}

if (-not (Test-Path $server)) { throw "mcp_server.py not found at $server" }
if (-not (Test-Path $python)) { throw "No Python found at $python" }

# --- find the config Claude Desktop actually reads -----------------------

$candidates = @()
$packages = Join-Path $env:LOCALAPPDATA 'Packages'
if (Test-Path $packages) {
    Get-ChildItem $packages -Filter 'Claude_*' -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $candidates += (Join-Path $_.FullName 'LocalCache\Roaming\Claude\claude_desktop_config.json')
    }
}
$candidates += (Join-Path $env:APPDATA 'Claude\claude_desktop_config.json')

# Prefer a folder that already exists - that is the install in use.
$target = $candidates | Where-Object { Test-Path (Split-Path -Parent $_) } | Select-Object -First 1
if (-not $target) { $target = $candidates[-1] }

$folder = Split-Path -Parent $target
if (-not (Test-Path $folder)) { New-Item -ItemType Directory -Path $folder | Out-Null }

Write-Host "Config: $target"

# --- merge, keeping everything already in the file -----------------------

if (Test-Path $target) {
    Copy-Item $target "$target.bak" -Force
    Write-Host "Backup: $target.bak"
    $raw = Get-Content $target -Raw
    if ([string]::IsNullOrWhiteSpace($raw)) { $config = [pscustomobject]@{} }
    else { $config = $raw | ConvertFrom-Json }
} else {
    $config = [pscustomobject]@{}
}

$entry = [pscustomobject]@{
    command = $python
    args    = @($server)
    env     = [pscustomobject]@{ SNOW_API = 'http://127.0.0.1:8095' }
}

if ($null -eq $config.mcpServers) {
    $config | Add-Member -NotePropertyName 'mcpServers' -NotePropertyValue ([pscustomobject]@{}) -Force
}
$config.mcpServers | Add-Member -NotePropertyName 'servicenow' -NotePropertyValue $entry -Force

# Depth matters: the default of 2 would flatten the nested server entry.
$json = $config | ConvertTo-Json -Depth 20

# Write UTF-8 *without* a BOM. Windows PowerShell's -Encoding utf8 adds one, and
# the app's JSON parser rejects a file that starts with it - which would break
# every setting in here, not just this entry.
[System.IO.File]::WriteAllText($target, $json, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "Registered 'servicenow' with Claude Desktop." -ForegroundColor Green
Write-Host "  python : $python"
Write-Host "  server : $server"
Write-Host ""
Write-Host "Next: start the backend (start-backend.cmd), then open Claude Desktop."
Write-Host "It will not work while the backend is stopped."
