<#
.SYNOPSIS
  Устанавливает (или обновляет параметры) службы Windows для обоих ботов через NSSM.
.EXAMPLE
  .\deploy\install-services.ps1 -NssmPath C:\tools\nssm.exe
#>
param(
    [string]$NssmPath = "nssm.exe",
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$Python = "python"
)
$ErrorActionPreference = "Stop"

$bots = @(
    @{ Name = "yasno-telegram-bot"; Dir = "telegram_bot"; Title = "ЯСНО ВИЖУ — Telegram-бот записи" },
    @{ Name = "yasno-max-bot";      Dir = "max_bot";      Title = "ЯСНО ВИЖУ — MAX-бот записи" }
)

if (-not (Get-Command $NssmPath -ErrorAction SilentlyContinue)) {
    throw "NSSM не найден: $NssmPath (укажите -NssmPath C:\путь\nssm.exe)"
}

foreach ($bot in $bots) {
    $dir = Join-Path $RepoRoot $bot.Dir
    $venv = Join-Path $dir ".venv"
    $py = Join-Path $venv "Scripts\python.exe"
    $logs = Join-Path $dir "logs"

    if (-not (Test-Path (Join-Path $dir ".env"))) {
        throw "Нет $dir\.env — скопируйте .env.example в .env и заполните."
    }
    if (-not (Test-Path $py)) {
        Write-Host "[$($bot.Name)] создаю виртуальное окружение"
        & $Python -m venv $venv
    }
    Write-Host "[$($bot.Name)] устанавливаю зависимости"
    & $py -m pip install --disable-pip-version-check -q -r (Join-Path $dir "requirements.txt")
    if ($LASTEXITCODE -ne 0) { throw "pip install завершился с ошибкой" }
    New-Item -ItemType Directory -Force -Path $logs | Out-Null

    & $NssmPath status $bot.Name *> $null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[$($bot.Name)] регистрирую службу"
        & $NssmPath install $bot.Name $py "-m" "app.main" | Out-Null
    }
    & $NssmPath set $bot.Name Application $py | Out-Null
    & $NssmPath set $bot.Name AppParameters "-m app.main" | Out-Null
    & $NssmPath set $bot.Name AppDirectory $dir | Out-Null
    & $NssmPath set $bot.Name DisplayName $bot.Title | Out-Null
    & $NssmPath set $bot.Name Start SERVICE_AUTO_START | Out-Null
    & $NssmPath set $bot.Name AppExit Default Restart | Out-Null
    & $NssmPath set $bot.Name AppRestartDelay 5000 | Out-Null
    & $NssmPath set $bot.Name AppStdout (Join-Path $logs "service.out.log") | Out-Null
    & $NssmPath set $bot.Name AppStderr (Join-Path $logs "service.err.log") | Out-Null
    & $NssmPath set $bot.Name AppRotateFiles 1 | Out-Null
    & $NssmPath set $bot.Name AppRotateBytes 10485760 | Out-Null
    & $NssmPath set $bot.Name AppEnvironmentExtra "PYTHONUTF8=1" | Out-Null
    Write-Host "[$($bot.Name)] готово"
}
Write-Host "Службы установлены. Запуск и проверка: .\deploy\deploy.ps1 -NssmPath $NssmPath -SkipPull"
