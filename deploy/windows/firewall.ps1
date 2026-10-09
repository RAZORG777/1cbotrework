<#
.SYNOPSIS
  Закрывает порты ботов (8001, 8002) от сети: доступ только с этого сервера и с указанных адресов
  (аудит 09.10.2026, п.1). Запускать в PowerShell от администратора.
.DESCRIPTION
  1. Выключает разрешающие правила для python.exe (их создаёт окно «Разрешить доступ» при первом
     запуске Python) и правила, открывающие порты 8001/8002.
  2. Если указан -AllowFrom, добавляет одно правило: порты ботов открыты только для этих адресов
     (например, подсети Docker, где работает NGINX Proxy Manager).
  Подключения с самого сервера (127.0.0.1) брандмауэр не фильтрует: 1С и локальные проверки работают.
.EXAMPLE
  .\deploy\windows\firewall.ps1
  .\deploy\windows\firewall.ps1 -AllowFrom 172.17.0.0/16
#>
param(
    [string[]]$AllowFrom = @(),
    [int[]]$Ports = @(8001, 8002)
)
$ErrorActionPreference = "Stop"
$ruleName = "YasnoBots: порты ботов"

$portStrings = $Ports | ForEach-Object { "$_" }
$candidates = @()
$candidates += Get-NetFirewallApplicationFilter |
    Where-Object { $_.Program -match 'python[0-9.]*w?\.exe$' } | Get-NetFirewallRule
$candidates += Get-NetFirewallPortFilter -Protocol TCP |
    Where-Object { @($_.LocalPort) | Where-Object { $_ -in $portStrings } } | Get-NetFirewallRule

$opened = $candidates | Sort-Object -Property Name -Unique | Where-Object {
    $_.Direction -eq "Inbound" -and $_.Action -eq "Allow" -and $_.Enabled -eq "True" -and
    $_.DisplayName -ne $ruleName
}
foreach ($rule in $opened) {
    Disable-NetFirewallRule -Name $rule.Name
    Write-Host "Выключено правило: $($rule.DisplayName)"
}
if (-not $opened) { Write-Host "Разрешающих правил для python.exe и портов $($Ports -join ', ') не найдено." }

Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue | Remove-NetFirewallRule
if ($AllowFrom.Count -gt 0) {
    New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Protocol TCP `
        -LocalPort $Ports -RemoteAddress $AllowFrom -Action Allow | Out-Null
    Write-Host "Порты $($Ports -join ', ') открыты только для: $($AllowFrom -join ', ')"
}

foreach ($p in Get-NetFirewallProfile) {
    $state = if ($p.Enabled) { "включён" } else { "ВЫКЛЮЧЕН" }
    Write-Host "Профиль $($p.Name): брандмауэр $state, входящие по умолчанию: $($p.DefaultInboundAction)"
    if (-not $p.Enabled -or $p.DefaultInboundAction -eq "Allow") {
        Write-Warning "В профиле $($p.Name) входящие не блокируются по умолчанию — правила выше не защитят порты."
    }
}
Write-Host "Проверьте: https://1cmed.one-two.online/healthz должен отвечать {""status"":""ok""}."
