@echo off
REM Descarga las tipografias autohospedadas desde los repos oficiales.

cd /d "%~dp0"

echo Descargando Newsreader...
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Regular.ttf  "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Medium.ttf   "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Medium.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-SemiBold.ttf "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-SemiBold.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Italic.ttf   "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Italic.ttf"

echo Descargando IBM Plex Sans...
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Light.ttf    "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Light.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Regular.ttf  "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Medium.ttf   "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Medium.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-SemiBold.ttf "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-SemiBold.ttf"

echo Descargando IBM Plex Mono...
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexMono-Regular.ttf "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Mono/fonts/complete/ttf/IBMPlexMono-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexMono-Medium.ttf  "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Mono/fonts/complete/ttf/IBMPlexMono-Medium.ttf"

echo.
echo Verificando tamanos minimos de las fuentes...
for %%f in (*.ttf) do (
    if %%~zf LSS 100000 (
        echo ERROR: %%f no parece una fuente valida ^(%%~zf bytes^).
        echo Revise la URL de descarga o descarguela manualmente desde el repositorio oficial.
        pause
        exit /b 1
    )
)
echo Descarga completada. Comprueba que hay 10 ficheros .ttf en la carpeta.
dir *.ttf
pause
