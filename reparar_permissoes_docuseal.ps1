# Restaura somente as permissões herdadas padrão do arquivo de configuração.
# Não lê, imprime, transmite ou altera a chave do DocuSeal.
$ErrorActionPreference = 'Stop'
$configPath = Join-Path $env:LOCALAPPDATA 'Robo do INSS\data\docuseal.json'
if (-not (Test-Path -LiteralPath $configPath)) { throw 'Configuração do DocuSeal não encontrada.' }
icacls $configPath /reset | Out-Null
Write-Host 'Permissões padrão restauradas. A chave foi preservada.' -ForegroundColor Green
