@echo off
setlocal
chcp 65001 >nul
set "SEXTA_RUNTIME=%~dp0.runtime"
if not "%~1"=="" set "SEXTA_RUNTIME=%~1"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1" -RuntimeRoot "%SEXTA_RUNTIME%"
exit /b %errorlevel%
