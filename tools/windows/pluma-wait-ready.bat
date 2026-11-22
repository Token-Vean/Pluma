@echo off
setlocal EnableExtensions
call "%~dp0pluma-env.bat" >nul 2>nul
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%\..\..") do set "PLUMA_DIR=%%~fI"
cd /d "%PLUMA_DIR%"
echo Esperando a que PlumA responda en http://127.0.0.1:8082 ...
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(180); while((Get-Date) -lt $deadline){ try { $r=Invoke-RestMethod -ErrorAction Stop 'http://127.0.0.1:8082/api/estado' -MaximumRedirection 0 -TimeoutSec 4; if($r.listo -is [bool] -and $r.listo){Write-Host 'PlumA lista.'; exit 0}; if($r.fase -eq 'error'){Write-Host $r.mensaje; exit 1} } catch {}; Start-Sleep -Seconds 2 }; exit 1"
if errorlevel 1 (
  echo No se ha podido verificar que PlumA este lista.
  echo.
  echo === Estado de contenedores ===
  docker compose ps
  echo.
  echo === Logs recientes de la aplicacion ===
  docker compose logs --tail=160 app
  exit /b 1
)
exit /b 0
