<#
.SYNOPSIS
  Автозапуск ботов при старте сервера под отдельной учётной записью без прав администратора
  (аудит 09.10.2026, п.7). Замена службам NSSM. Запускать в PowerShell от администратора.
.EXAMPLE
  .\deploy\windows\install-tasks.ps1 -CreateUser
  # отдельная учётка yasno-bots без прав администратора (рекомендуется)
.EXAMPLE
  .\deploy\windows\install-tasks.ps1 -User $env:USERNAME
  # под текущей учётной записью
.NOTES
  Боты работают и без входа в Windows, переживают перезагрузку, после сбоя поднимаются через 5 с.
#>
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [string]$User = "yasno-bots",
    [switch]$CreateUser
)
$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "bots.psm1") -Force

$cred = Get-Credential -UserName $User -Message "Пароль учётной записи, под которой работают боты"
$plain = $cred.GetNetworkCredential().Password

if ($CreateUser -and -not (Get-LocalUser -Name $User -ErrorAction SilentlyContinue)) {
    New-LocalUser -Name $User -Password $cred.Password -PasswordNeverExpires `
        -UserMayNotChangePassword -Description "Боты записи ЯСНО ВИЖУ" | Out-Null
    Write-Host "Создан пользователь $User (обычный, без прав администратора)"
}

# Права: читать проект, писать только в каталоги ботов (БД, журналы, картинки рассылок).
icacls $RepoRoot /grant "${User}:(OI)(CI)RX" /T /C /Q | Out-Null
foreach ($bot in $Bots) {
    icacls (Join-Path $RepoRoot $bot.Dir) /grant "${User}:(OI)(CI)M" /T /C /Q | Out-Null
}

# Python должен быть установлен для всех пользователей, иначе учётке ботов он недоступен.
$base = & (Join-Path $RepoRoot "telegram_bot\.venv\Scripts\python.exe") -c "import sys; print(sys.base_prefix)"
if ($base -like "*\Users\*" -and $User -ne $env:USERNAME) {
    throw "Python установлен в профиль пользователя ($base). Установите Python для всех пользователей (Install for all users, C:\Program Files) и пересоздайте .venv в обоих ботах."
}

foreach ($bot in $Bots) {
    $dir = Join-Path $RepoRoot $bot.Dir
    $script = Join-Path $PSScriptRoot "run-bot.ps1"
    $action = New-ScheduledTaskAction -Execute "powershell.exe" `
        -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$script`" -BotDir `"$dir`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $bot.Name -Action $action -Trigger $trigger -Settings $settings `
        -User $User -Password $plain -RunLevel Limited -Force | Out-Null
    Remove-Item (Join-Path $dir "STOP") -ErrorAction SilentlyContinue
    Write-Host "[$($bot.Name)] задание создано"
}
Write-Host "Остановите ботов в окнах консоли (Ctrl+C) и запустите задания:"
Write-Host "  Start-ScheduledTask yasno-telegram-bot; Start-ScheduledTask yasno-max-bot"
