@echo off
setlocal
if not exist "%~dp0Preparar Cofre NFe.exe" (
  echo Extraia TODOS os arquivos do ZIP antes de executar o preparador.
  echo Depois, abra Preparar Cofre NFe.exe na pasta extraida.
  pause
  exit /b 1
)
"%~dp0Preparar Cofre NFe.exe"
exit /b %errorlevel%
