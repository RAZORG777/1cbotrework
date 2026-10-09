<#
.SYNOPSIS
  Останавливает ботов, запущенных заданиями планировщика (например, для отката на старых ботов).
  Запустить снова: Start-ScheduledTask yasno-telegram-bot; Start-ScheduledTask yasno-max-bot
#>
param([string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "bots.psm1") -Force
foreach ($bot in $Bots) {
    $dir = Join-Path $RepoRoot $bot.Dir
    New-Item -ItemType File -Force -Path (Join-Path $dir "STOP") | Out-Null
    Stop-ScheduledTask -TaskName $bot.Name -ErrorAction SilentlyContinue
    Stop-BotProcess $dir
    Remove-Item (Join-Path $dir "STOP") -ErrorAction SilentlyContinue
    Write-Host "[$($bot.Name)] остановлен"
}
