# Executar localmente uma única vez após copiar a chave em DocuSeal > Configurações > API.
# A chave não é exibida no terminal nem armazenada no repositório.
$ErrorActionPreference = 'Stop'
$dataPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data'
$configPath = Join-Path $dataPath 'docuseal.json'
New-Item -ItemType Directory -Force -Path $dataPath | Out-Null

$secureToken = Read-Host 'Cole a chave X-Auth-Token do DocuSeal' -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureToken)
try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
if ([string]::IsNullOrWhiteSpace($token)) { throw 'A chave não pode ficar vazia.' }

@{ url = 'http://127.0.0.1:3000'; api_token = $token } |
    ConvertTo-Json -Compress |
    Set-Content -LiteralPath $configPath -Encoding utf8 -NoNewline

# %LOCALAPPDATA% já é privado ao perfil do Windows. Não altere a ACL manualmente:
# o servidor local pode ser executado por um processo filho com outro token.
Write-Host 'Configuração local do DocuSeal salva. Reinicie o PrevIA para aplicar.' -ForegroundColor Green
