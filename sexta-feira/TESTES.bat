@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "SEXTA_RUNTIME=%~dp0.runtime"
if not "%~1"=="" set "SEXTA_RUNTIME=%~1"
if not exist "%SEXTA_RUNTIME%\venv\Scripts\python.exe" (
  echo Ambiente virtual nao encontrado. Informe a pasta runtime como primeiro argumento.
  exit /b 1
)
"%SEXTA_RUNTIME%\venv\Scripts\python.exe" -m unittest discover -s tests -v
exit /b %errorlevel%
