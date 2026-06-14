# setup.ps1 — one-command install for opencode-memory-store
param(
  [switch]$NoPlugin = $false,
  [switch]$NoIngest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Write-Host "=== opencode-memory-store setup ===" -ForegroundColor Cyan
Write-Host "Root: $Root"

# 1. Check uv
$uv = Get-Command "uv" -ErrorAction SilentlyContinue
if (-not $uv) {
  Write-Host "Installing uv..." -ForegroundColor Yellow
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  $uv = Get-Command "uv" -ErrorAction Stop
}
Write-Host "uv: $($uv.Source)" -ForegroundColor Green

# 2. Install Python package
Write-Host "`nInstalling Python package (editable)..." -ForegroundColor Yellow
& $uv.Source pip install -e $Root
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "CLI 'opencode-memory-store' ready" -ForegroundColor Green

# 3. Install plugin deps
if (-not $NoPlugin) {
  Write-Host "`nInstalling plugin dependencies..." -ForegroundColor Yellow
  Push-Location "$Root\plugin"
  npm install --no-fund --no-audit 2>&1 | Out-Null
  Pop-Location
  Write-Host "Plugin dependencies installed" -ForegroundColor Green
}

# 4. Wire opencode config
$globalConfig = "$env:USERPROFILE\.opencode\opencode.json"
$pluginRef = "file:///$($Root -replace '\\','/')/plugin"
if (Test-Path $globalConfig) {
  $cfg = Get-Content $globalConfig -Raw | ConvertFrom-Json
  if ($cfg.plugin -notcontains $pluginRef) {
    $cfg.plugin += $pluginRef
    $cfg | ConvertTo-Json -Depth 10 | Set-Content $globalConfig
    Write-Host "Plugin added to $globalConfig" -ForegroundColor Green
  } else {
    Write-Host "Plugin already registered in $globalConfig" -ForegroundColor Gray
  }
} else {
  @{ "$schema" = "https://opencode.ai/config.json"; "plugin" = @($pluginRef) } |
    ConvertTo-Json | Set-Content $globalConfig
  Write-Host "Created $globalConfig with plugin" -ForegroundColor Green
}

# 5. Verify
Write-Host "`n=== Verification ===" -ForegroundColor Cyan
$ver = & $uv.Source run -c "$Root" python -m opencode_memory_store.cli stats 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "WARNING: CLI stats failed" -ForegroundColor Red
  Write-Host $ver
} else {
  Write-Host "CLI works: $ver" -ForegroundColor Green
}

# 6. Ingest current project
if (-not $NoIngest) {
  Write-Host "`nIngesting current project into memory..." -ForegroundColor Yellow
  & $uv.Source run -c "$Root" python -m opencode_memory_store.cli ingest "$Root" 2>&1
  Write-Host "Done" -ForegroundColor Green
}

Write-Host "`n=== Setup complete! ===" -ForegroundColor Green
Write-Host "Commands:" -ForegroundColor Cyan
Write-Host "  opencode-memory-store stats" -ForegroundColor White
Write-Host "  opencode-memory-store recall <query>" -ForegroundColor White
Write-Host "  opencode-memory-store ingest <project-path>" -ForegroundColor White
Write-Host "  opencode-memory-store import <json-file>" -ForegroundColor White
Write-Host "`nPlugin loaded next time opencode starts" -ForegroundColor Cyan
