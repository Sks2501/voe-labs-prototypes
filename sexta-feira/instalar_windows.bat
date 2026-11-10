@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\install.ps1" %*
set "SEXTA_INSTALL_EXIT=%errorlevel%"
echo.
if not "%SEXTA_INSTALL_EXIT%"=="0" echo Instalacao interrompida. Leia o erro acima antes de tentar novamente.
if /i not "%SEXTA_NO_PAUSE%"=="1" pause
exit /b %SEXTA_INSTALL_EXIT%
