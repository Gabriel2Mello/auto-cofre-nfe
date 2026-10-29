@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m tests.preview_interface --desktop
  exit /b
)
if exist "..\.venv\Scripts\pythonw.exe" (
  start "" "..\.venv\Scripts\pythonw.exe" -m tests.preview_interface --desktop
  exit /b
)
echo Python nao encontrado. Consulte o README para preparar a instalacao.
pause
