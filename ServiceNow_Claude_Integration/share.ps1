<#
  share.ps1 - expose the ServiceNow app (frontend + backend) as ONE public link.

  Usage (from the Mcp_Demo folder):
      powershell -ExecutionPolicy Bypass -File .\share.ps1

  What it does
    1. Downloads the standalone Cloudflare tunnel client on first run (no account needed).
    2. Starts the backend (port 8095) and the frontend (port 5173) if they are not running.
    3. Opens a tunnel to the frontend and prints a https://....trycloudflare.com link.
       The frontend proxies /api/* to the backend, so that single link serves both.

  Sharing stops when you press Ctrl+C or close this window. The link changes every run.
  Anyone with the link can read from ServiceNow through the read-only account, so only
  share it with people who should see that data.
#>

$ErrorActionPreference = 'Stop'
$root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$frontend = Join-Path $root 'Frontend'
$backend  = Join-Path $root 'servicenow-mcp'
$exe      = Join-Path $env:LOCALAPPDATA 'cloudflared\cloudflared.exe'

function Test-Port($port) {
    [bool](netstat -ano | Select-String -Pattern (":$port\s+\S+\s+LISTENING") -Quiet)
}

if (-not (Test-Path $exe)) {
    New-Item -ItemType Directory -Force (Split-Path $exe) | Out-Null
    Write-Host 'Downloading cloudflared (one time)...'
    Invoke-WebRequest -UseBasicParsing -OutFile $exe `
        -Uri 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe'
}

if (-not (Test-Port 8095)) {
    Write-Host 'Starting backend on http://127.0.0.1:8095 ...'
    $py = Join-Path $backend '.venv\Scripts\python.exe'
    if (-not (Test-Path $py)) {
        $py = Join-Path $backend '.venv314\Scripts\python.exe'
    }
    Start-Process -FilePath $py `
        -ArgumentList 'scripts\rest_api.py' -WorkingDirectory $backend -WindowStyle Minimized
}
if (-not (Test-Port 5173)) {
    Write-Host 'Starting frontend on http://localhost:5173 ...'
    Start-Process -FilePath 'cmd.exe' -ArgumentList '/c npm run dev -- --port 5173 --strictPort' `
        -WorkingDirectory $frontend -WindowStyle Minimized
}

$deadline = (Get-Date).AddSeconds(40)
while ((Get-Date) -lt $deadline -and -not ((Test-Port 8095) -and (Test-Port 5173))) { Start-Sleep -Seconds 1 }
if (-not (Test-Port 8095)) { Write-Warning 'Backend is not listening on 8095. The page will load but show "API offline".' }
if (-not (Test-Port 5173)) { throw 'Frontend is not listening on 5173. Run "npm run dev" in the frontend folder and try again.' }

Write-Host ''
Write-Host 'Opening the tunnel... the link appears below in a few seconds. Press Ctrl+C to stop sharing.'
Write-Host ''

# cloudflared logs to stderr; in Windows PowerShell 5.1 that arrives as ErrorRecords, so relax the preference.
$ErrorActionPreference = 'Continue'
& $exe tunnel --url http://localhost:5173 --no-autoupdate 2>&1 | ForEach-Object {
    $line = "$_"
    if ($line -match 'https://[a-z0-9-]+\.trycloudflare\.com') {
        Write-Host ''
        Write-Host ("  SHARE THIS LINK:  " + $Matches[0]) -ForegroundColor Green
        Write-Host ''
    } elseif ($line -match '\bERR\b|failed|error') {
        Write-Host $line -ForegroundColor Yellow
    }
}
