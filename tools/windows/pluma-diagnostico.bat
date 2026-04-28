@echo off
setlocal
call "%~dp0pluma-env.bat" >nul 2>nul
cd /d "%~dp0\..\.."
echo === PlumA diagnostico local ===
echo Carpeta: %CD%
echo.
echo Docker:
docker --version
echo.
echo Compose:
docker compose version
echo.
echo Contenedores PlumA:
docker compose ps
echo.
echo Redes PlumA:
docker network ls | findstr pluma
echo.
echo Puerto publicado de app:
docker compose port app 8081
echo.
echo Estado HTTP:
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://localhost:8082/api/estado -TimeoutSec 5 | Select-Object -ExpandProperty Content } catch { Write-Host $_.Exception.Message; exit 1 }"
echo.
echo Seguridad local efectiva:
powershell -NoProfile -Command "try { Invoke-WebRequest -UseBasicParsing http://localhost:8082/api/seguridad-local -TimeoutSec 5 | Select-Object -ExpandProperty Content } catch { Write-Host $_.Exception.Message; exit 1 }"
exit /b %errorlevel%
