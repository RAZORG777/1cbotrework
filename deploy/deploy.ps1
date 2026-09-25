<#
.SYNOPSIS
  Выкладка: git pull → зависимости → перезапуск служб → проверка /healthz.
.EXAMPLE
  .\deploy\deploy.ps1 -NssmPath C:\tools\nssm.exe
#>
param(
    [string]$NssmPath = "nssm.exe",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [int]$HealthTimeoutSec = 30,
    [switch]$SkipPull
)
$ErrorActionPreference = "Stop"
Set-Location $RepoRoot

$bots = @(
    @{ Name = "yasno-telegram-bot"; Dir = "telegram_bot"; Health = "http://127.0.0.1:8001/healthz" },
    @{ Name = "yasno-max-bot";      Dir = "max_bot";      Health = "http://127.0.0.1:8002/max/healthz" }
)

if (-not $SkipPull) {
    Write-Host "git pull --ff-only"
    git pull --ff-only
    if ($LASTEXITCODE -ne 0) { throw "git pull не выполнен (есть локальные изменения или расхождение веток)" }
}

foreach ($bot in $bots) {
    $py = Join-Path $RepoRoot "$($bot.Dir)\.venv\Scripts\python.exe"
    if (-not (Test-Path $py)) { throw "Нет $py — сначала запустите deploy\install-services.ps1" }
    Write-Host "[$($bot.Name)] зависимости"
    & $py -m pip install --disable-pip-version-check -q -r (Join-Path $RepoRoot "$($bot.Dir)\requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install завершился с ошибкой" }
    Write-Host "[$($bot.Name)] перезапуск"
    & $NssmPath restart $bot.Name | Out-Null
}

$failed = @()
foreach ($bot in $bots) {
    $ok = $false
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $bot.Health -UseBasicParsing -TimeoutSec 3
            if ($r.StatusCode -eq 200) { $ok = $true; break }
        } catch { Start-Sleep -Seconds 1 }
    }
    if ($ok) { Write-Host "[$($bot.Name)] OK $($bot.Health)" }
    else { Write-Host "[$($bot.Name)] НЕ ОТВЕЧАЕТ $($bot.Health) — см. $($bot.Dir)\logs"; $failed += $bot.Name }
}
if ($failed.Count -gt 0) { exit 1 }
Write-Host "Выкладка завершена."
