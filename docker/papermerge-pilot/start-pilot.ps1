[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$pilotDirectory = Split-Path -Parent $PSCommandPath
$envFile = Join-Path $pilotDirectory '.env'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker Desktop não foi encontrado. Instale-o, inicie-o e execute este script novamente.'
}

if (-not (Test-Path -LiteralPath $envFile)) {
    # Credenciais locais do piloto: geradas somente nesta máquina e ignoradas pelo Git.
    $secretKey = (([guid]::NewGuid().ToString('N')) + ([guid]::NewGuid().ToString('N')))
    $adminPassword = (([guid]::NewGuid().ToString('N')) + 'P!')
    $databasePassword = (([guid]::NewGuid().ToString('N')) + 'D!')
    @(
        "PAPERMERGE_SECRET_KEY=$secretKey"
        "PAPERMERGE_ADMIN_PASSWORD=$adminPassword"
        "PAPERMERGE_DB_PASSWORD=$databasePassword"
    ) | Set-Content -LiteralPath $envFile -Encoding utf8
    Write-Host 'Credenciais locais do piloto foram geradas em .env (arquivo não versionado).'
}

Push-Location $pilotDirectory
try {
    docker compose --env-file .env up -d
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível iniciar o Papermerge.' }
    Write-Host 'Piloto Papermerge iniciado em http://localhost:8081'
    Write-Host 'Use somente documentos anonimizados até a homologação concluir.'
}
finally {
    Pop-Location
}
