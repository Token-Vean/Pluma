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

# Aviso (no bloqueante) sobre hashes en requirements.txt
if ! grep -q -- "--hash=sha256:" backend/requirements.txt; then
  echo ""
  echo "AVISO: backend/requirements.txt no contiene hashes SHA-256."
  echo "Para releases públicas se recomienda regenerar con:"
  echo "  cd backend && pip-compile --generate-hashes \\"
  echo "    --output-file requirements.txt requirements.in"
  echo "y modificar el Dockerfile para usar 'pip install --require-hashes'."
  echo "Ver backend/HASHES.md para más detalles."
  echo ""
fi

echo "Comprobaciones locales básicas superadas."
