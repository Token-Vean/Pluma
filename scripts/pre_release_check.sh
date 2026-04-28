#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if find . -name .env -print -quit | grep -q .; then
  echo "ERROR: no empaquetar ficheros .env"
  exit 1
fi

if find . -type d -name __pycache__ -print -quit | grep -q .; then
  echo "ERROR: eliminar __pycache__ antes de la release"
  exit 1
fi

python -m py_compile backend/app/*.py

echo "Comprobaciones locales básicas superadas."
