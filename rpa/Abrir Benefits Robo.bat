@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Benefits 360 — robô REAL (porta 8600 — deixe esta janela aberta)
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo  O robô ainda não foi instalado neste computador.
  echo  Dê dois cliques em "instalar.bat" primeiro.
  echo.
  pause
  exit /b 1
)
set "LOGDIR=%LOCALAPPDATA%\NewportCotacoes\logs"
if not exist "%LOGDIR%" mkdir "%LOGDIR%"
set "NEWPORT_RPA_ORIGENS=https://benefits-360-production.up.railway.app"
echo.
echo  Benefits 360 — robô REAL de cotações
echo  ====================================
echo.
echo  Porta 8600  ·  pasta rpa\saida  ·  config.yaml
echo  Não feche esta janela. Use o site:
echo    https://benefits-360-production.up.railway.app
echo  na aba Cotações (Chrome ou Edge).
echo.
echo  Log: %LOGDIR%\robo-real.log
echo  Na primeira vez o navegador pede acesso à rede local: Permita.
echo.
".venv\Scripts\python.exe" -m app --config config.yaml --porta 8600 --sem-navegador --log "%LOGDIR%\robo-real.log"
if errorlevel 1 pause
