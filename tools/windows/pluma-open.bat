@echo off
call "%~dp0pluma-env.bat" >nul 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "try { $r=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:8082/api/estado' -TimeoutSec 4; if($r.StatusCode -eq 200){ Start-Process 'http://localhost:8082'; exit 0 } else { exit 1 } } catch { Write-Host $_.Exception.Message; exit 1 }"
exit /b %errorlevel%
