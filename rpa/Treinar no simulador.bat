@echo off
cd /d "%~dp0"
title Newport Cotacoes - SIMULADOR (treino, nada e emitido de verdade)
if not exist ".venv\Scripts\python.exe" (
  echo  O Newport Cotacoes ainda nao foi instalado neste computador.
  echo  De dois cliques em "instalar.bat" primeiro.
  echo.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m app --config config_simulador.yaml --com-simulador
if errorlevel 1 pause
