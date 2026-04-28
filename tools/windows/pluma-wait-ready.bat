@echo off
setlocal EnableExtensions
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
cd /d "%PLUMA_DIR%"
echo Esperando a que PlumA responda en http://127.0.0.1:8082 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$ErrorActionPreference='SilentlyContinue'; $deadline=(Get-Date).AddSeconds(180); $ok=$false; while((Get-Date) -lt $deadline){ try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8082/api/estado' -TimeoutSec 4; if($r.StatusCode -eq 200){ Write-Host 'PlumA responde correctamente.'; $ok=$true; break } } catch { Write-Host ('Esperando servicio HTTP: ' + $_.Exception.Message) }; Start-Sleep -Seconds 3 }; if($ok){ exit 0 } else { exit 1 }"
if errorlevel 1 (
  echo PlumA no ha respondido dentro del tiempo esperado.
  echo.
  echo === Estado de contenedores ===
  docker compose ps
  echo.
  echo === Logs recientes de la aplicacion ===
  docker compose logs --tail=160 app
  exit /b 1
)
exit /b 0
