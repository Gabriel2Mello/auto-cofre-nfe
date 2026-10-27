param(
    [string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    [string]$Versao = ('local-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),
    [string]$Destino = (Join-Path $PSScriptRoot 'dist'),
    [string]$Trabalho = (Join-Path $PSScriptRoot 'build')
)
$ErrorActionPreference = 'Stop'
if ($Versao -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$') { throw 'Versão inválida.' }
$commitCofre = & git -C $PSScriptRoot rev-parse HEAD
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível identificar a revisão de origem.' }
$pendenciasCofre = & git -C $PSScriptRoot status --porcelain
$pastaMetadadosCofre = Join-Path $PSScriptRoot ('.local\builds\' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $pastaMetadadosCofre | Out-Null
$arquivoMetadadosCofre = Join-Path $pastaMetadadosCofre 'cofre-versao.json'
@{ versao = $Versao; commit = $commitCofre; checkout_modificado = [bool]$pendenciasCofre } |
    ConvertTo-Json | Set-Content -LiteralPath $arquivoMetadadosCofre -Encoding utf8
$buildAnteriorCofre = $env:NUNES_COFRE_BUILD
try {
    $env:NUNES_COFRE_BUILD = $arquivoMetadadosCofre
    & $Python -m PyInstaller --noconfirm --clean --distpath $Destino --workpath $Trabalho "$PSScriptRoot\Cofre Desktop.spec"
} finally {
    $env:NUNES_COFRE_BUILD = $buildAnteriorCofre
}
if ($LASTEXITCODE -ne 0) { throw 'O build desktop da Cofre falhou.' }
Write-Output "Build $Versao em $Destino\Cofre NFe. Pacote assinado é uma etapa separada."
