@echo off
REM ============================================================================
REM PlumA - detener servicios
REM ----------------------------------------------------------------------------
REM Detiene los contenedores Docker de PlumA. Los datos no se pierden:
REM la proxima vez que ejecutes 1_INSTALAR.bat, se reanudaran donde quedaron.
REM ============================================================================

cd /d "%~dp0"

if not exist "sistema\" (
    echo ERROR: no encuentro la carpeta 'sistema'.
    pause
    exit /b 1
)

cd sistema

echo.
echo Deteniendo PlumA...
docker compose down

echo.
echo OK - PlumA detenida.
echo.
echo Para arrancarla de nuevo, ejecuta 1_INSTALAR.bat
echo.
pause
