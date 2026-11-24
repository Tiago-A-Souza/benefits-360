@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Benefits 360 — TREINO (porta 8601 — não são as cotações reais)
if not exist ".venv\Scripts\python.exe" (
  echo  O robô ainda não foi instalado neste computador.
  echo  Dê dois cliques em "instalar.bat" primeiro.
  echo.
  pause
  exit /b 1
)
set "LOGDIR=%LOCALAPPDATA%\NewportCotacoes\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
echo.
echo  MODO TREINO — porta 8601 — pasta saida_simulador
echo  Não mistura com as cotações reais (porta 8600 / rpa\saida).
echo.
".venv\Scripts\python.exe" -m app --config config_simulador.yaml --porta 8601 --com-simulador --sem-navegador --log "%LOGDIR%\robo-treino.log"
if errorlevel 1 pause
