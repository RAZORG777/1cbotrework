<#
.SYNOPSIS
  Держит бота запущенным: запускает python -m app.main и перезапускает через 5 с после выхода
  (в том числе после кнопки «Перезапустить бот» в админке). Запускается заданием планировщика
  из install-tasks.ps1. Чтобы остановить насовсем — stop-bots.ps1.
#>
param([Parameter(Mandatory = $true)][string]$BotDir)
$ErrorActionPreference = "Continue"
$env:PYTHONUTF8 = "1"
Set-Location $BotDir
$py = Join-Path $BotDir ".venv\Scripts\python.exe"
$logs = Join-Path $BotDir "logs"
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$runner = Join-Path $logs "runner.log"
$stopFlag = Join-Path $BotDir "STOP"

while (-not (Test-Path $stopFlag)) {
    Add-Content -Path $runner -Value "$(Get-Date -Format s) запуск" -Encoding UTF8
    # Журнал бот пишет сам (logs\*.log); сюда попадают только ошибки до его старта (например, .env).
    & $py -m app.main 2>> (Join-Path $logs "startup-errors.log") | Out-Null
    Add-Content -Path $runner -Value "$(Get-Date -Format s) завершился с кодом $LASTEXITCODE" -Encoding UTF8
    Start-Sleep -Seconds 5
}
Add-Content -Path $runner -Value "$(Get-Date -Format s) найден файл STOP — остановка" -Encoding UTF8
