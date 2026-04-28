@echo off
setlocal
cd /d "%~dp0nsis"
where makensis >nul 2>nul
if errorlevel 1 (
  echo No se ha encontrado makensis.exe.
  echo Instala NSIS desde https://nsis.sourceforge.io/ y vuelve a ejecutar este script.
  exit /b 1
)
makensis PlumA-Setup.nsi
exit /b %errorlevel%
