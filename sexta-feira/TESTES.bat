@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Execute instalar_windows.bat primeiro.
  exit /b 1
)
".venv\Scripts\python.exe" -m unittest discover -s tests -v
exit /b %errorlevel%
