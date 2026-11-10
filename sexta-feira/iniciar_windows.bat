@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute instalar_windows.bat primeiro.
  exit /b 1
)
set "SEXTA_OFFLINE=1"
echo ===============================================
echo SEXTA-FEIRA - servidor privado
echo ===============================================
echo Abra http://127.0.0.1:8765 no navegador.
echo Digite o token exibido abaixo na interface.
echo Encerre com CTRL+C.
".venv\Scripts\python.exe" -m sexta_feira serve --host 127.0.0.1 --port 8765 --model small
exit /b %errorlevel%
