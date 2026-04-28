#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../pluma"
chmod +x instalar.sh detener.sh desinstalar.sh 2>/dev/null || true
exec ./detener.sh
