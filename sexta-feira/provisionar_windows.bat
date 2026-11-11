@echo off
setlocal
chcp 65001 >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\provision.ps1" %*
set "SEXTA_PROVISION_RESULT=%errorlevel%"
echo.
if not "%SEXTA_PROVISION_RESULT%"=="0" echo O provisionamento encontrou um erro. Leia a mensagem acima. Os arquivos existentes foram preservados.
echo Pressione uma tecla para fechar esta janela.
pause >nul
exit /b %SEXTA_PROVISION_RESULT%
