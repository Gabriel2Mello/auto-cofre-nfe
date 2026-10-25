param([string]$Python = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))
$ErrorActionPreference = 'Stop'
& $Python -m PyInstaller --noconfirm --clean --distpath "$PSScriptRoot\dist" --workpath "$PSScriptRoot\build" "$PSScriptRoot\Cofre Desktop.spec"
if ($LASTEXITCODE -ne 0) { throw 'O build desktop da Cofre falhou.' }
Write-Output 'Distribua a pasta inteira dist\Cofre NFe. Dados ficam no perfil; consulte DESKTOP.md para migração.'
