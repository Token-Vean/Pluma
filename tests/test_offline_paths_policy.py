from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_offline_compose_path_stays_inside_repo():
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "./offline/models:/offline/models:ro" in compose
    assert "../offline/models:/offline/models:ro" not in compose


def test_offline_placeholder_files_are_kept():
    assert (ROOT / "offline" / "images" / "README.md").exists()
    assert (ROOT / "offline" / "models" / "README.md").exists()
    assert (ROOT / "offline" / "models" / "Modelfile.template.parameters").exists()
