#!/usr/bin/env bash
# Descarga las tipografías autohospedadas desde los repos oficiales.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

echo "Descargando Newsreader..."
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Regular.ttf  "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Medium.ttf   "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Medium.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-SemiBold.ttf "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-SemiBold.ttf"
curl -fL --retry 3 --connect-timeout 10 -o Newsreader-Italic.ttf   "https://raw.githubusercontent.com/productiontype/Newsreader/master/fonts/ttf/Newsreader-Italic.ttf"

echo "Descargando IBM Plex Sans..."
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Light.ttf    "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Light.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Regular.ttf  "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-Medium.ttf   "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-Medium.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexSans-SemiBold.ttf "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Sans/fonts/complete/ttf/IBMPlexSans-SemiBold.ttf"

echo "Descargando IBM Plex Mono..."
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexMono-Regular.ttf "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Mono/fonts/complete/ttf/IBMPlexMono-Regular.ttf"
curl -fL --retry 3 --connect-timeout 10 -o IBMPlexMono-Medium.ttf  "https://raw.githubusercontent.com/IBM/plex/master/IBM-Plex-Mono/fonts/complete/ttf/IBMPlexMono-Medium.ttf"

echo ""
echo "Verificando que los ficheros descargados son fuentes reales..."
fallos=0
for f in *.ttf; do
    tipo=$(file -b "$f")
    if [[ "$tipo" == *"TrueType"* ]] || [[ "$tipo" == *"OpenType"* ]]; then
        echo "  OK  $f"
    else
        echo "  ERR $f  ($tipo)"
        fallos=$((fallos+1))
    fi
done

if [ $fallos -eq 0 ]; then
    echo ""
    echo "Descarga completada. Las tipografías ya están en su sitio."
else
    echo ""
    echo "Hubo $fallos ficheros que no son fuentes válidas."
    echo "Descárgalas manualmente desde:"
    echo "  https://github.com/productiontype/Newsreader/tree/master/fonts/ttf"
    echo "  https://github.com/IBM/plex/tree/master/IBM-Plex-Sans/fonts/complete/ttf"
    echo "  https://github.com/IBM/plex/tree/master/IBM-Plex-Mono/fonts/complete/ttf"
    exit 1
fi
