# startup.ps1 - Start BhumiCheck frontend and backend together
# Usage: .\startup.ps1

$ErrorActionPreference = "Stop"
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"

function Log  ($msg) { Write-Host "[startup] $msg" -ForegroundColor White }
function Ok   ($msg) { Write-Host "  OK  $msg" -ForegroundColor Green }
function Warn ($msg) { Write-Host "  !!  $msg" -ForegroundColor Yellow }
function Err  ($msg) { Write-Host "  XX  $msg" -ForegroundColor Red }

# Check .env files
$missingEnv = $false
foreach ($dir in @($Backend, $Frontend)) {
    $envFile = Join-Path $dir ".env"
    $example = Join-Path $dir ".env.example"
    if (-not (Test-Path $envFile)) {
        if (Test-Path $example) {
            Warn ".env not found in $dir - copying from .env.example"
            Copy-Item $example $envFile
            Warn "Edit $envFile and fill in your credentials, then re-run."
            $missingEnv = $true
        } else {
            Err ".env missing in $dir and no .env.example found."
            $missingEnv = $true
        }
    }
}
if ($missingEnv) {
    Err "Fix missing .env files above, then re-run."
    exit 1
}

# Backend: create venv + install deps
Log "Setting up backend..."
$venv = Join-Path $Backend ".venv"

if (-not (Test-Path $venv)) {
    Log "Creating Python virtual environment..."
    python -m venv $venv
}

$python = Join-Path $venv "Scripts\python.exe"

$reqFile  = Join-Path $Backend "requirements.txt"
$stampFile = Join-Path $venv "installed.stamp"

if (-not (Test-Path $stampFile) -or ((Get-Item $reqFile).LastWriteTime -gt (Get-Item $stampFile).LastWriteTime)) {
    Log "Installing/updating Python dependencies..."
    & "$python" -m pip install -q --upgrade pip
    & "$python" -m pip install -q -r $reqFile
    New-Item -ItemType File -Path $stampFile -Force | Out-Null
    Ok "Backend dependencies ready"
} else {
    Ok "Backend dependencies already installed - skipping"
}

# Frontend: npm install
Log "Setting up frontend..."
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Err "Node.js not found. Install from https://nodejs.org"
    exit 1
}
$lockFile  = Join-Path $Frontend "package-lock.json"
$nmStamp   = Join-Path $Frontend "node_modules\.npm_stamp"

$needsInstall = -not (Test-Path (Join-Path $Frontend "node_modules"))
if (-not $needsInstall -and (Test-Path $nmStamp) -and (Test-Path $lockFile)) {
    $needsInstall = (Get-Item $lockFile).LastWriteTime -gt (Get-Item $nmStamp).LastWriteTime
}

if ($needsInstall) {
    Log "Installing npm packages..."
    Push-Location $Frontend
    npm install
    Pop-Location
    New-Item -ItemType File -Path $nmStamp -Force | Out-Null
    Ok "Frontend dependencies ready"
} else {
    Ok "Frontend dependencies already installed - skipping"
}

# Summary
Write-Host ""
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  BhumiCheck - opening two terminal windows" -ForegroundColor White
Write-Host "  Frontend  ->  http://localhost:5173" -ForegroundColor Cyan
Write-Host "  Backend   ->  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  API docs  ->  http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "  Close either terminal window to stop that server" -ForegroundColor Gray
Write-Host ""

# Launch backend in a new visible terminal window
$backendCmd = "& '$python' -m uvicorn app.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Backend'; $backendCmd" -WindowStyle Normal

# Launch frontend in a new visible terminal window
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$Frontend'; npm run dev" -WindowStyle Normal

Ok "Both servers launched in separate windows."
