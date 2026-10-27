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
$compiladorCofre = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
& $compiladorCofre /nologo /target:exe /platform:anycpu /optimize+ "/out:$(Join-Path $Destino 'Cofre NFe\Preparar Cofre NFe.exe')" (Join-Path $PSScriptRoot 'src\PrepararCofre.cs')
if ($LASTEXITCODE -ne 0) { throw 'O build do preparador da Cofre falhou.' }
foreach ($arquivoPreparacaoCofre in @('Preparar Cofre NFe.cmd', 'LEIA-ME.txt')) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot $arquivoPreparacaoCofre) -Destination (Join-Path $Destino 'Cofre NFe')
}
Write-Output "Build $Versao em $Destino\Cofre NFe. Pacote assinado é uma etapa separada."
