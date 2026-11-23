@echo off
REM =============================================================================
REM PlumA - abre el panel si VBScript esta desactivado en el equipo.
REM Puede verse un instante una ventana negra; es normal.
REM =============================================================================
if not exist "%~dp0..\programa\panel\PlumAPanel.ps1" (
    echo No se encuentra el panel de PlumA. Descomprime el ZIP completo.
    pause
    exit /b 1
)
start "" "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0..\programa\panel\PlumAPanel.ps1"
exit /b 0
