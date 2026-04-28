from __future__ import annotations

from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).resolve().parents[1]


def fail(msg: str) -> None:
    print(f"[FAIL] {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_runtime_artifacts() -> None:
    forbidden_names = {".env", ".git"}
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if p.name in forbidden_names:
            fail(f"artefacto no distribuible encontrado: {rel}")
        if p.name == "__pycache__" or p.suffix == ".pyc":
            fail(f"artefacto Python generado encontrado: {rel}")
    ok("sin .env, .git, __pycache__ ni .pyc")


def test_compose_local_locked() -> None:
    compose = ROOT / "docker-compose.yml"
    if not compose.exists():
        fail("no existe docker-compose.yml")
    if yaml is None:
        text = read(compose)
        if 'host_ip: "127.0.0.1"' not in text or 'published: "8082"' not in text:
            fail("docker-compose.yml no publica la app solo en 127.0.0.1:8082")
        ok("docker-compose.yml revisado por texto")
        return

    data = yaml.safe_load(read(compose))
    app = data["services"]["app"]
    ports = app.get("ports") or []
    if not ports:
        fail("el servicio app no publica puerto")
    p = ports[0]
    if p.get("host_ip") != "127.0.0.1" or str(p.get("published")) != "8082" or int(p.get("target")) != 8081:
        fail(f"puerto inseguro o inesperado en app: {p}")
    env = app.get("environment") or {}
    expected = {
        "PLUMA_STRICT_LOCAL": "true",
        "ALLOW_REMOTE_OLLAMA": "false",
        "ALLOW_NETWORK_EXPOSURE": "false",
        "PERMITIR_APAGADO_UI": "${PERMITIR_APAGADO_UI:-false}",
    }
    for key, expected_value in expected.items():
        if env.get(key) != expected_value:
            fail(f"{key} tiene valor inesperado: {env.get(key)!r}")
    ok("docker-compose.yml mantiene publicación local y flags bloqueados")


def test_public_env_does_not_expose_dangerous_flags() -> None:
    env_example = read(ROOT / ".env.example")
    active_lines = [line.strip() for line in env_example.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    for token in ("ALLOW_REMOTE_OLLAMA=", "ALLOW_NETWORK_EXPOSURE=", "COMPOSE_PROFILES="):
        if any(line.startswith(token) for line in active_lines):
            fail(f".env.example expone opción peligrosa: {token}")
    if "PERMITIR_APAGADO_UI=false" not in active_lines:
        fail("PERMITIR_APAGADO_UI debe estar desactivado por defecto")
    ok(".env.example no expone flags de red/remoto y desactiva apagado UI")


def test_dockerignore_minimal_context() -> None:
    dockerignore = ROOT / "backend" / ".dockerignore"
    if not dockerignore.exists():
        fail("falta backend/.dockerignore")
    text = read(dockerignore)
    for token in ("*", "!requirements.txt", "!app/", ".env", "*.pyc"):
        if token not in text:
            fail(f"backend/.dockerignore no contiene {token!r}")
    ok("backend/.dockerignore limita el contexto de build")


def test_version_coherence() -> None:
    files = {
        "version.py": read(ROOT / "backend" / "app" / "version.py"),
        "docker-compose.yml": read(ROOT / "docker-compose.yml"),
        ".env.example": read(ROOT / ".env.example"),
        "frontend/static/app.js": read(ROOT / "frontend" / "static" / "app.js"),
        "backend/app/api.py": read(ROOT / "backend" / "app" / "api.py"),
        "Modelfile": read(ROOT / "Modelfile"),
    }
    for file_name, text in files.items():
        if "0.5.0" not in text:
            fail(f"versión 0.5.0 ausente en {file_name}")
    ok("versión coherente en ficheros activos")


if __name__ == "__main__":
    test_no_runtime_artifacts()
    test_compose_local_locked()
    test_public_env_does_not_expose_dangerous_flags()
    test_dockerignore_minimal_context()
    test_version_coherence()
    print("\nComprobaciones estáticas de release superadas.")
