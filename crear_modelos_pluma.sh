#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"

echo
echo "PlumA - creacion opcional de perfiles Ollama"
echo "---------------------------------------------"
echo

echo "Comprobando Ollama..."
if ! command -v ollama >/dev/null 2>&1; then
  echo "ERROR: No se encuentra Ollama en el PATH."
  exit 1
fi

ollama --version || {
  echo "ERROR: Ollama esta instalado, pero no responde correctamente."
  exit 1
}

echo
echo "Modelos disponibles en Ollama:"
ollama list || true

declare -i CREADOS=0
declare -i FALLOS=0

echo
if ollama show qwen3.5:latest >/dev/null 2>&1; then
  echo "Creando/actualizando pluma-vision desde qwen3.5:latest..."
  if ollama create pluma-vision -f "$(pwd)/modelos_ollama/pluma-vision.Modelfile"; then
    CREADOS+=1
  else
    echo "ERROR: No se pudo crear pluma-vision."
    echo "Ejecuta manualmente: ollama create pluma-vision -f \"$(pwd)/modelos_ollama/pluma-vision.Modelfile\""
    FALLOS+=1
  fi
else
  echo "AVISO: No se encuentra qwen3.5:latest. No se crea pluma-vision."
  echo "       Puedes descargarlo con: ollama pull qwen3.5:latest"
fi

echo
if ollama show gemma4:e2b >/dev/null 2>&1; then
  echo "Creando/actualizando pluma-texto desde gemma4:e2b..."
  if ollama create pluma-texto -f "$(pwd)/modelos_ollama/pluma-texto.Modelfile"; then
    CREADOS+=1
  else
    echo "ERROR: No se pudo crear pluma-texto. Se mantiene pluma-vision si se creo correctamente."
    FALLOS+=1
  fi
else
  echo "AVISO: No se encuentra gemma4:e2b. No se crea pluma-texto."
  echo "       Puedes descargarlo con: ollama pull gemma4:e2b"
fi

echo
echo "Verificacion final:"
ollama list | grep -Ei 'pluma-vision|pluma-texto' || true

echo
if (( CREADOS == 0 )); then
  echo "No se ha creado ningun perfil. Revisa los avisos anteriores."
else
  echo "Perfiles creados/actualizados: $CREADOS"
fi

if (( FALLOS > 0 )); then
  echo "Fallos detectados: $FALLOS"
fi
