# FSKU PowerShell Runner
param(
    [string]$Command = "serve",
    [string]$Host = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$Sync,
    [string]$Gpu = "H100"
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($Sync) {
    wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py sync"
    return
}

if ($Command -eq "forward") {
    wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py forward --gpu $Gpu"
    return
}

if ($Command -eq "list") {
    wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py list"
    return
}

if ($Command -eq "stats") {
    wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py stats"
    return
}

Write-Host "Starting FSKU Platform on http://$Host`:$Port ..." -ForegroundColor Cyan
wsl bash -c "cd /mnt/d/apps/sku_futures && python3 fsku_cli.py serve --host 0.0.0.0 --port $Port"
