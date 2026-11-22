"""Construye el ZIP de Windows y su SHA-256 a partir de un único commit Git."""
from __future__ import annotations

import argparse
import hashlib
import io
import re
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
RAIZ = {
    ".env.example", "docker-compose.yml", "LICENSE", "README.md", "INSTALACION.md",
    "CHANGELOG.md", "CUMPLIMIENTO.md", "KNOWN_ISSUES.md", "SECURITY.md",
    "SECURITY_HARDENING.md", "SECURITY_NOTES.md", "CLA.md", "CONTRIBUTING.md",
}
for nombre in ("crear_modelos_pluma", "desinstalar", "detener", "iniciar", "instalar"):
    RAIZ.update({nombre + ".bat", nombre + ".sh"})
FIJOS = {
    "backend/.dockerignore", "backend/Dockerfile", "backend/requirements.txt",
    "backend/requirements.in", "backend/pyproject.toml", "backend/HASHES.md",
    "ejemplos/README.md", "frontend/README.md", "offline/images/README.md",
    "offline/models/README.md",
}
EXTENSIONES = {
    "backend/app/": {".py"}, "frontend/static/": {".html", ".js", ".css", ".png", ".ico", ".txt", ".md", ".woff2"},
    "schemas/": {".yaml"}, "modelos_ollama/": {".Modelfile"}, "tools/windows/": {".bat", ".ps1"},
}
PANEL = {
    "PlumA - Instalar y abrir.vbs", "ayuda/Abrir sin VBScript.bat", "ayuda/LEEME.txt",
    "programa/panel/PlumAPanel.ps1",
}
PANEL.update("programa/panel/scripts/pluma-" + nombre + ".bat" for nombre in
             ("diagnostico", "install-core", "mode", "start-core", "stop-core", "uninstall-core"))


def destino(ruta: str) -> str | None:
    if ruta.startswith("packaging/windows/"):
        rel = ruta.removeprefix("packaging/windows/")
        return rel if rel in PANEL else None
    if ruta in RAIZ or ruta in FIJOS or any(
        ruta.startswith(prefijo) and PurePosixPath(ruta).suffix in extensiones
        for prefijo, extensiones in EXTENSIONES.items()
    ):
        return "programa/" + ruta
    return None


def empaquetar(revision: str, salida: Path) -> Path:
    def git(*args: str) -> bytes:
        return subprocess.check_output(["git", *args], cwd=ROOT)

    commit = git("rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
    archivos: dict[str, bytes] = {}
    # git archive aplica conversiones de fin de línea en Windows. Leer los
    # objetos directamente garantiza el mismo ZIP con cualquier core.autocrlf.
    seleccion = []
    for entrada in git("ls-tree", "-rz", commit).split(b"\0"):
        if not entrada:
            continue
        metadatos, ruta = entrada.split(b"\t", 1)
        modo, tipo, sha = metadatos.decode().split()
        nombre = destino(ruta.decode())
        if not nombre:
            continue
        if tipo != "blob" or modo not in {"100644", "100755"}:
            raise ValueError("Tipo de archivo inesperado: " + nombre)
        seleccion.append((nombre, sha))
    consulta = "".join(sha + "\n" for _, sha in seleccion).encode()
    objetos = io.BytesIO(subprocess.check_output(["git", "cat-file", "--batch"], input=consulta, cwd=ROOT))
    for nombre, sha in seleccion:
        recibido, tipo, tamano = objetos.readline().decode().split()
        if recibido != sha or tipo != "blob":
            raise ValueError("Objeto Git inesperado para " + nombre)
        contenido = objetos.read(int(tamano))
        if objetos.read(1) != b"\n":
            raise ValueError("Objeto Git incompleto para " + nombre)
        if nombre.endswith((".bat", ".vbs", ".ps1")):
            contenido = contenido.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        archivos[nombre] = contenido
    faltan = (PANEL | {"programa/" + ruta for ruta in RAIZ | FIJOS}) - archivos.keys()
    if faltan:
        raise ValueError(f"Paquete incompleto: {sorted(faltan)}")
    version_app = re.search(rb'^APP_VERSION = "(\d+\.\d+\.\d+)"\r?$', archivos["programa/backend/app/version.py"], re.M)
    if not version_app:
        raise ValueError("No se encuentra APP_VERSION en el código de la revisión.")
    version = version_app[1].decode()
    archivos["REVISION.txt"] = f"PlumA {version}\r\nhttps://github.com/Token-Vean/Pluma/commit/{commit}\r\n".encode()
    archivos["ayuda/Novedades.txt"] = git("show", f"{commit}:releases/{version}.md").replace(b"\n", b"\r\n")
    salida.mkdir(parents=True, exist_ok=True)
    ruta = salida / ("PlumA-" + version.replace(".", "_") + "-windows.zip")
    with zipfile.ZipFile(ruta, "w") as salida_zip:
        for nombre, contenido in sorted(archivos.items()):
            info = zipfile.ZipInfo(f"PlumA-{version}/{nombre}", date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if nombre.endswith(".sh") else 0o100644) << 16
            # ZIP_STORED mantiene el resultado idéntico entre versiones de zlib.
            salida_zip.writestr(info, contenido)
    huella = hashlib.sha256(ruta.read_bytes()).hexdigest()
    ruta.with_suffix(".zip.sha256").write_bytes(f"{huella}  {ruta.name}\n".encode())
    return ruta


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--salida", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(empaquetar(args.ref, args.salida))
