# Salva o segredo HMAC copiado em DocuSeal > Webhook > Security > HMAC.
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data\docuseal.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Configuração DocuSeal não encontrada.' }
$config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
$secure = Read-Host 'Cole o segredo HMAC whsec_' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try { $value = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim() } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
if (-not $value.StartsWith('whsec_')) { throw 'O segredo HMAC deve começar com whsec_.' }
if ($config.PSObject.Properties.Name -contains 'webhook_hmac_secret') { $config.webhook_hmac_secret = $value } else { $config | Add-Member -NotePropertyName webhook_hmac_secret -NotePropertyValue $value }
$config | ConvertTo-Json -Compress | Set-Content -LiteralPath $configPath -Encoding utf8 -NoNewline
Write-Host 'Segredo HMAC salvo localmente.' -ForegroundColor Green
