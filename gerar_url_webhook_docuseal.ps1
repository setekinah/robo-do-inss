# Gera a URL local do webhook; não solicita nenhuma chave.
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data\docuseal.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Execute configurar_docuseal.ps1 antes.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if (-not $config.webhook_path_token) {
    $config | Add-Member -NotePropertyName webhook_path_token -NotePropertyValue ([guid]::NewGuid().ToString('N'))
    $config | ConvertTo-Json -Compress | Set-Content -LiteralPath $configPath -Encoding utf8 -NoNewline
}
Write-Host "Webhook URL: http://host.docker.internal:8000/api/assinatura/webhook/$($config.webhook_path_token)" -ForegroundColor Cyan
