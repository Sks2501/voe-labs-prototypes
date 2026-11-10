@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo ===============================================
echo SEXTA-FEIRA - instalacao local gratuita Windows
echo ===============================================
where py >nul 2>&1
if errorlevel 1 (
  echo ERRO: Python Launcher nao encontrado.
  echo Instale Python 3.11 64-bit em https://www.python.org/downloads/
  exit /b 1
)
py -3.11 -c "import sys; assert sys.maxsize > 2**32, 'Python 64-bit obrigatorio'" 2>nul
if errorlevel 1 (
  echo ERRO: Python 3.11 64-bit nao encontrado.
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
echo Instalando PyTorch CPU (sem GPU, sem API paga)...
".venv\Scripts\python.exe" -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 exit /b 1
echo Instalando bibliotecas locais...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
echo Baixando pesos originais GPT-2 124M da OpenAI...
".venv\Scripts\python.exe" -m sexta_feira download --model small
if errorlevel 1 (
  echo ERRO: modelo nao baixado. Verifique internet e espaco em disco.
  exit /b 1
)
echo Instalacao concluida.
echo Para iniciar execute: iniciar_windows.bat
exit /b 0
