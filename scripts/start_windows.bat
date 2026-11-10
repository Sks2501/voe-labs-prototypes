@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  py -3.11 -m venv .venv
  if errorlevel 1 (
    echo Python 3.11 precisa estar instalado no Windows.
    exit /b 1
  )
)
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
if errorlevel 1 exit /b 1
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 exit /b 1
python -m pip install -r requirements-local.txt
if errorlevel 1 exit /b 1
python src\local_api.py --threads 2 --port 8765
endlocal
