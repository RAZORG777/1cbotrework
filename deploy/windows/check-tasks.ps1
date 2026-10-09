<#
.SYNOPSIS
  Проверка автозапуска ботов: состояние заданий, причина ошибки, журнал запуска, ответ /healthz.
  Запускать в PowerShell от администратора.
.EXAMPLE
  .\deploy\windows\check-tasks.ps1 -Start
  # запустить задания, подождать 20 с и показать результат
#>
param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$Start
)
Import-Module (Join-Path $PSScriptRoot "bots.psm1") -Force

$codes = @{
    0          = "успешно"
    267009     = "работает"
    267011     = "ещё ни разу не запускалось"
    267014     = "остановлено вручную"
    2147943785 = "у учётки нет права «Вход в качестве пакетного задания» — запустите install-tasks.ps1 ещё раз"
    2147943726 = "неверный пароль учётки — запустите install-tasks.ps1 ещё раз"
    2147943712 = "Windows не хранит пароли заданий — отключите политику «Сетевой доступ: не разрешать хранение паролей»"
    2147942402 = "не найден файл (powershell.exe или run-bot.ps1)"
    2147942405 = "отказано в доступе к файлам — запустите install-tasks.ps1 ещё раз"
    2147946720 = "задание отключено"
}

if ($Start) {
    foreach ($bot in $Bots) {
        Remove-Item (Join-Path $RepoRoot "$($bot.Dir)\STOP") -ErrorAction SilentlyContinue
        Enable-ScheduledTask -TaskName $bot.Name -ErrorAction SilentlyContinue | Out-Null
        Start-ScheduledTask -TaskName $bot.Name
    }
    Write-Host "Задания запущены, ждём 20 секунд..."
    Start-Sleep 20
}

foreach ($bot in $Bots) {
    Write-Host ""
    Write-Host "=== $($bot.Name) ===" -ForegroundColor Cyan
    $task = Get-ScheduledTask -TaskName $bot.Name -ErrorAction SilentlyContinue
    if (-not $task) { Write-Host "Задание не создано"; continue }
    $info = $task | Get-ScheduledTaskInfo
    $code = [int64][uint32]$info.LastTaskResult
    $meaning = if ($codes.ContainsKey($code)) { $codes[$code] } else { "код 0x{0:X8}" -f $code }
    Write-Host ("Состояние: {0}; запуск от имени: {1} ({2})" -f $task.State, $task.Principal.UserId, $task.Principal.LogonType)
    Write-Host ("Последний запуск: {0}; результат: {1} — {2}" -f $info.LastRunTime, $code, $meaning)

    $events = Get-WinEvent -FilterHashtable @{
        LogName = "Microsoft-Windows-TaskScheduler/Operational"; StartTime = (Get-Date).AddHours(-3)
    } -ErrorAction SilentlyContinue | Where-Object { $_.Message -like "*\$($bot.Name)*" } | Select-Object -First 6
    if ($events) {
        Write-Host "Журнал планировщика:"
        foreach ($e in $events) {
            $msg = ($e.Message -split "`r?`n")[0..1] -join " "
            Write-Host ("  {0:HH:mm:ss} [{1}] {2}" -f $e.TimeCreated, $e.Id, $msg)
        }
    } else {
        Write-Host "Журнал планировщика: событий нет (если журнал был выключен — он включается install-tasks.ps1)"
    }

    $logs = Join-Path $RepoRoot "$($bot.Dir)\logs"
    foreach ($name in "runner.log", "startup-errors.log") {
        $f = Join-Path $logs $name
        if (Test-Path $f) {
            Write-Host "${name}:"
            Get-Content $f -Tail 5 -Encoding UTF8 | ForEach-Object { Write-Host "  $_" }
        } else {
            Write-Host "${name}: нет файла"
        }
    }

    $url = $bot.Health
    try {
        $r = Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 3
        Write-Host "healthz: $($r.StatusCode) $($r.Content)" -ForegroundColor Green
    } catch {
        Write-Host "healthz: не отвечает" -ForegroundColor Red
    }
}
