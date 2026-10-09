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

Add-Type -AssemblyName System.DirectoryServices.AccountManagement
$ctx = New-Object System.DirectoryServices.AccountManagement.PrincipalContext("Machine")
if (-not $ctx.ValidateCredentials($User, $plain)) {
    throw "Пароль для $User не подошёл. Сбросьте его: Set-LocalUser $User -Password (Read-Host -AsSecureString) и запустите скрипт снова."
}
$lu = Get-LocalUser -Name $User -ErrorAction SilentlyContinue
if ($lu -and -not $lu.Enabled) { Enable-LocalUser -Name $User; Write-Host "Учётная запись $User включена" }

# Задание с сохранённым паролем входит в Windows как пакетное задание. Обычным пользователям
# на Windows Server это право по умолчанию не выдано, и задание молча не стартует.
function Grant-BatchLogon([string]$Name) {
    $sid = (New-Object Security.Principal.NTAccount($Name)).Translate([Security.Principal.SecurityIdentifier]).Value
    $tmp = Join-Path $env:TEMP "yasno-secpol"
    New-Item -ItemType Directory -Force $tmp | Out-Null
    try {
        $inf = Join-Path $tmp "export.inf"
        secedit /export /cfg $inf /areas USER_RIGHTS | Out-Null
        $rights = Get-Content $inf
        $deny = $rights | Where-Object { $_ -like "SeDenyBatchLogonRight*" }
        if ($deny -match [regex]::Escape("*$sid") -or $deny -match "\b$([regex]::Escape($Name))\b") {
            Write-Warning "Учётке $User запрещён вход как пакетное задание (политика «Отказать во входе в качестве пакетного задания»). Уберите её оттуда в secpol.msc."
        }
        $line = $rights | Where-Object { $_ -like "SeBatchLogonRight*" }
        if ($line -match [regex]::Escape("*$sid") -or $line -match "\b$([regex]::Escape($Name))\b") { return }
        $value = if ($line) { "$line,*$sid" } else { "SeBatchLogonRight = *$sid" }
        $add = Join-Path $tmp "add.inf"
        @("[Unicode]", "Unicode=yes", "[Version]", 'signature="$CHICAGO$"', "Revision=1",
          "[Privilege Rights]", $value) | Set-Content $add -Encoding Unicode
        secedit /configure /db (Join-Path $tmp "add.sdb") /cfg $add /areas USER_RIGHTS | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "secedit завершился с кодом $LASTEXITCODE" }
        Write-Host "Учётке $User выдано право «Вход в качестве пакетного задания»"
    } finally {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
if ($User -ne $env:USERNAME) { Grant-BatchLogon $User }

$lsa = Get-ItemProperty "HKLM:\SYSTEM\CurrentControlSet\Control\Lsa" -ErrorAction SilentlyContinue
if ($lsa.disabledomaincreds -eq 1) {
    Write-Warning "Включена политика «Сетевой доступ: не разрешать хранение паролей». С ней задания с паролем не запускаются — отключите её в secpol.msc (Локальные политики → Параметры безопасности)."
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
# Журнал планировщика: без него не видно, почему задание не стартовало.
wevtutil sl Microsoft-Windows-TaskScheduler/Operational /e:true | Out-Null
Write-Host "Остановите ботов в окнах консоли (Ctrl+C) и запустите проверку:"
Write-Host "  .\deploy\windows\check-tasks.ps1 -Start"
