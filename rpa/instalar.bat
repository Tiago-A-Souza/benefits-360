@echo off
setlocal
cd /d "%~dp0"
title Newport Cotacoes - instalacao
echo.
echo  Newport Cotacoes - instalacao
echo  =============================
echo.

rem Procura o Python 3.11 ou mais novo: primeiro o "py" do Windows, depois "python".
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" >nul 2>nul && set "PY=python"
if not defined PY (
  echo  [ERRO] Nao encontrei o Python 3.11 ou mais novo neste computador.
  echo  Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH"
  echo  e de dois cliques neste arquivo de novo.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo  1/4  Criando o ambiente do robo ^(.venv^)...
  %PY% -m venv .venv || goto erro
) else (
  echo  1/4  Ambiente do robo ja existe.
)

echo  2/4  Instalando as bibliotecas...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q --upgrade pip
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -q -r requirements.txt || goto erro

echo  3/4  Instalando o navegador do robo ^(Chromium, separado do seu Chrome^)...
".venv\Scripts\python.exe" -m playwright install chromium || goto erro

echo  4/4  Conferindo a instalacao...
".venv\Scripts\python.exe" -m pytest -q tests\test_nucleo.py || goto erro

echo.
echo  Pronto. Para usar, de dois cliques em "Abrir Newport Cotacoes.bat".
echo  Para treinar sem o portal, use "Treinar no simulador.bat".
echo.
pause
exit /b 0

:erro
echo.
echo  [ERRO] A instalacao parou. Veja a mensagem acima.
echo  Se for proxy ou certificado, peca a TI para liberar o pip e o download do Chromium (Playwright).
echo.
pause
exit /b 1
