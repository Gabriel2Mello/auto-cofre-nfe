@echo off
cd /d "%~dp0"
if exist "Cofre NFe.exe" (
  start "" "Cofre NFe.exe"
  exit /b
)
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" "cofre.py"
  exit /b
)
if exist "..\.venv\Scripts\pythonw.exe" (
  start "" "..\.venv\Scripts\pythonw.exe" "cofre.py"
  exit /b
)
echo Python nao encontrado. Consulte o README para preparar a instalacao.
pause
