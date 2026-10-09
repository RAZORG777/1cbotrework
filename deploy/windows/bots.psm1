# Общие функции скриптов управления ботами (планировщик Windows).

$Bots = @(
    @{ Name = "yasno-telegram-bot"; Dir = "telegram_bot"; Health = "http://127.0.0.1:8001/healthz" },
    @{ Name = "yasno-max-bot";      Dir = "max_bot";      Health = "http://127.0.0.1:8002/max/healthz" }
)

function Stop-BotProcess([string]$BotDir) {
    # Процессы Python этого бота (.venv внутри каталога бота) — вместе с дочерними.
    Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($BotDir, [StringComparison]::OrdinalIgnoreCase) } |
        ForEach-Object { taskkill /PID $_.ProcessId /T /F | Out-Null }
}

Export-ModuleMember -Function Stop-BotProcess -Variable Bots
