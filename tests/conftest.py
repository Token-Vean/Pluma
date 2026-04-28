"""Configuración de tests para PlumA.

Permite importar el paquete local ``app`` cuando pytest se ejecuta desde
distintos directorios, como ocurre en GitHub Actions con working-directory:
backend y los tests ubicados en ../tests.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
