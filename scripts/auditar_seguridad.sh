#!/usr/bin/env bash
set -euo pipefail

IMAGE="pluma-app:0.7.4"

echo "PlumA v0.7.4 - auditoría local de seguridad"
echo "------------------------------------------------"

echo "[1/4] Comprobación estática del repositorio"
python scripts/security_static_check.py

echo "[2/4] Tests unitarios"
PYTHONPATH=backend python -m pytest -q

echo "[3/4] Build limpio de la imagen Docker"
docker compose build --no-cache app

echo "[4/4] Docker Scout: vulnerabilidades con fixed version"
OLLAMA_IMAGE="$(docker compose --profile bundled config --images | grep '^ollama/ollama:')"
for imagen in "$IMAGE" "$OLLAMA_IMAGE"; do
  docker scout cves --exit-code --only-severity critical "$imagen"
  docker scout cves --exit-code --only-severity high,medium --only-fixed "$imagen"
done

echo ""
echo "Criterio de release: 0 críticas, 0 altas corregibles y 0 medias corregibles."
echo "Revise SECURITY_NOTES.md para mitigaciones y riesgos residuales."
