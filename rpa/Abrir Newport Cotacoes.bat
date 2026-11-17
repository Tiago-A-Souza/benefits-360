@echo off
cd /d "%~dp0"
title Newport Cotacoes - deixe esta janela aberta
if not exist ".venv\Scripts\python.exe" (
  echo  O Newport Cotacoes ainda nao foi instalado neste computador.
  echo  De dois cliques em "instalar.bat" primeiro.
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app
if errorlevel 1 pause
