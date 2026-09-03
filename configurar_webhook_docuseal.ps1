# Execute após salvar o webhook no DocuSeal e copiar o segredo whsec_... da aba Security > HMAC.
$ErrorActionPreference = 'Stop'
$dataPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data'
$configPath = Join-Path $dataPath 'docuseal.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Execute configurar_docuseal.ps1 antes.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if (-not $config.webhook_path_token) {
    $config | Add-Member -NotePropertyName webhook_path_token -NotePropertyValue ([guid]::NewGuid().ToString('N'))
}
$secret = Read-Host 'Cole o segredo HMAC whsec_ (ou Enter para apenas gerar a URL)' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secret)
try { $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
if ($value) {
    if (-not $value.StartsWith('whsec_')) { throw 'O segredo HMAC deve começar com whsec_.' }
    if ($config.PSObject.Properties.Name -contains 'webhook_hmac_secret') { $config.webhook_hmac_secret = $value } else { $config | Add-Member -NotePropertyName webhook_hmac_secret -NotePropertyValue $value }
}
$config | ConvertTo-Json -Compress | Set-Content -LiteralPath $configPath -Encoding utf8 -NoNewline
Write-Host "Webhook URL: http://host.docker.internal:8000/api/assinatura/webhook/$($config.webhook_path_token)" -ForegroundColor Cyan
Write-Host 'Cole essa URL no DocuSeal. Depois copie o segredo HMAC e execute este script novamente.' -ForegroundColor Yellow
