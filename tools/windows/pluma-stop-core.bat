@echo off
setlocal
call "%~dp0pluma-env.bat" >nul 2>nul
cd /d "%~dp0\..\.."
docker compose down
exit /b %errorlevel%
