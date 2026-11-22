@echo off
REM =============================================================================
REM pluma-diagnostico.bat
REM -----------------------------------------------------------------------------
REM Parte del panel del paquete para Windows.
REM Resumen del estado local de PlumA. Lo usa el panel del paquete para
REM Windows. Devuelve 0 si PlumA responde en 127.0.0.1:8082.
REM =============================================================================
setlocal EnableExtensions
call "%~dp0..\..\tools\windows\pluma-env.bat" >nul 2>nul
call "%~dp0pluma-mode.bat"
cd /d "%~dp0..\.."
echo === PlumA - diagnostico local ===
echo Carpeta: %CD%
echo Motor de IA: %PLUMA_OLLAMA_MODE%
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
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8082/api/estado' -TimeoutSec 5).Content } catch { Write-Host $_.Exception.Message; exit 1 }"
set "HTTP_ESTADO=%ERRORLEVEL%"
echo.
echo Seguridad local efectiva:
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8082/api/seguridad-local' -TimeoutSec 5).Content } catch { Write-Host $_.Exception.Message }"
echo.
if /I "%PLUMA_OLLAMA_MODE%"=="host" (
    echo Ollama del equipo:
    powershell -NoProfile -Command "try { $null = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 5; Write-Host 'Responde en 127.0.0.1:11434' } catch { Write-Host $_.Exception.Message }"
    echo.
)
exit /b %HTTP_ESTADO%
