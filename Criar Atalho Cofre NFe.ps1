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
$shellCofre = New-Object -ComObject WScript.Shell
$atalhoCofre = $shellCofre.CreateShortcut((Join-Path $PSScriptRoot 'Abrir Cofre NFe.lnk'))
$atalhoCofre.TargetPath = $destinoCofre
$atalhoCofre.Arguments = $argumentosCofre
$atalhoCofre.WorkingDirectory = $PSScriptRoot
$atalhoCofre.IconLocation = $iconeCofre + ',0'
$atalhoCofre.Description = 'Baixar e organizar XML e PDF do Cofre NF-e'
$atalhoCofre.WindowStyle = 1
$atalhoCofre.Save()
Write-Output 'Atalho Cofre NF-e criado com o ícone Nunes.'
