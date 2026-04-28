@echo off
REM ============================================================================
REM Comprobacion pre-subida a GitHub (Windows)
REM ============================================================================
REM Ejecutar ANTES de hacer git push, para verificar que no se cuela nada
REM de las pruebas locales (.env, documentos personales, caches, etc).
REM ============================================================================
setlocal enabledelayedexpansion

cd /d "%~dp0\.."

set PROBLEMAS=0

echo ===========================================================================
echo   Comprobacion pre-subida a GitHub
echo ===========================================================================
echo.

if not exist ".git" (
    echo ERROR: no estas en la raiz de un repositorio git.
    exit /b 1
)

echo -- Ficheros que git ve como cambios pendientes --
git status --short
echo.

echo -- Comprobacion de .env --
git ls-files 2>nul | findstr /R "^\.env$ /\.env$" >nul 2>&1
if !errorlevel! equ 0 (
    echo PELIGRO: hay ficheros .env rastreados por git:
    git ls-files | findstr /R "^\.env$ /\.env$"
    echo   Ejecuta: git rm --cached .env
    set /a PROBLEMAS+=1
) else (
    echo OK: ningun .env rastreado
)

echo.
echo -- Comprobacion de cache Python --
git ls-files 2>nul | findstr /R "__pycache__ \.pyc$" >nul 2>&1
if !errorlevel! equ 0 (
    echo AVISO: hay __pycache__ o .pyc rastreados:
    git ls-files | findstr /R "__pycache__ \.pyc$"
    set /a PROBLEMAS+=1
) else (
    echo OK: sin cache Python rastreada
)

echo.
echo -- Comprobacion de documentos de prueba --
for /f "delims=" %%f in ('git ls-files ejemplos/ 2^>nul') do (
    echo %%f | findstr /E ".md" >nul
    if !errorlevel! neq 0 (
        echo AVISO: %%f no es .md
        set /a PROBLEMAS+=1
    )
)
if !PROBLEMAS! equ 0 echo OK: ejemplos/ contiene solo documentacion

echo.
echo ===========================================================================
if !PROBLEMAS! equ 0 (
    echo Listo para subir. No se han detectado problemas evidentes.
    echo.
    echo Recordatorio: revisa 'git status' y 'git diff --cached' antes de push.
) else (
    echo Se han detectado !PROBLEMAS! problema^(s^). Resuelvelos antes del push.
)
echo ===========================================================================
echo.
pause
exit /b !PROBLEMAS!
