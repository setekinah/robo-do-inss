# Reinicia apenas a configuração local do webhook. A chave API do DocuSeal é preservada.
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data\docuseal.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Configuração DocuSeal não encontrada.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
foreach ($name in @('webhook_path_token', 'webhook_hmac_secret')) {
    $property = $config.PSObject.Properties[$name]
    if ($property) { $config.PSObject.Properties.Remove($name) }
}
$config | ConvertTo-Json -Compress | Set-Content -LiteralPath $configPath -Encoding utf8 -NoNewline
Write-Host 'Webhook local resetado. A chave de API foi preservada.' -ForegroundColor Green
