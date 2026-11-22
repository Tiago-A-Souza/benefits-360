@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Benefits 360 — robô de cotações (deixe esta janela aberta)
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo  O robô ainda não foi instalado neste computador.
  echo  Dê dois cliques em "instalar.bat" primeiro.
  echo.
  pause
  exit /b 1
)
echo.
echo  Benefits 360 — robô de cotações
echo  ================================
echo.
echo  O robô vai ficar ligado nesta janela.
echo  Não feche. Use o site:
echo    https://benefits-360-production.up.railway.app
echo  na aba Cotações (Chrome ou Edge).
echo.
echo  Na primeira vez o navegador pede acesso à rede local: Permita.
echo.
".venv\Scripts\python.exe" -m app --sem-navegador
if errorlevel 1 pause
