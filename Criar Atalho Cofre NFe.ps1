$ErrorActionPreference = 'Stop'
$executavelCofre = Join-Path $PSScriptRoot 'Cofre NFe.exe'
$scriptCofre = Join-Path $PSScriptRoot 'cofre.py'
$iconeCofre = Join-Path $PSScriptRoot 'icons\icone.ico'
$argumentosCofre = ''
if (Test-Path -LiteralPath $executavelCofre -PathType Leaf) {
    $destinoCofre = $executavelCofre
} else {
    $destinoCofre = $null
    foreach ($ambienteCofre in @('.venv', '..\.venv')) {
        $pythonCofre = Join-Path $PSScriptRoot "$ambienteCofre\Scripts\pythonw.exe"
        if (Test-Path -LiteralPath $pythonCofre -PathType Leaf) {
            $destinoCofre = (Resolve-Path -LiteralPath $pythonCofre).Path
            break
        }
    }
    if (-not $destinoCofre) { throw 'Python não encontrado em .venv ou ..\.venv. Consulte o README.' }
    $argumentosCofre = '"' + $scriptCofre + '"'
    if (-not (Test-Path -LiteralPath $scriptCofre -PathType Leaf)) { throw 'cofre.py não encontrado.' }
}
if (-not (Test-Path -LiteralPath $iconeCofre -PathType Leaf)) { throw 'Ícone da aplicação não encontrado.' }
$caminhoAtalhoCofre = Join-Path $PSScriptRoot 'Abrir Cofre NFe.lnk'
if ($argumentosCofre) {
    $argumentosAtalhoCofre = '"' + $scriptCofre + '" --criar-atalho "' + $caminhoAtalhoCofre + '"'
} else {
    $argumentosAtalhoCofre = '--criar-atalho "' + $caminhoAtalhoCofre + '"'
}
$processoAtalhoCofre = Start-Process -FilePath $destinoCofre -ArgumentList $argumentosAtalhoCofre -WindowStyle Hidden -Wait -PassThru
if ($processoAtalhoCofre.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $caminhoAtalhoCofre -PathType Leaf)) {
    throw 'O iniciador não confirmou a criação do atalho Cofre NF-e.'
}
Write-Output 'Atalho Cofre NF-e criado com identidade desktop Nunes.'
