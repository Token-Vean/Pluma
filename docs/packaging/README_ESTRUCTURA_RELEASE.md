# Empaquetado de releases

Este repositorio fuente no debe incluir artefactos generados de release, como ZIP finales, checksums, informes de generación o textos preparados para GitHub Releases.

La estructura recomendada para el repositorio es:

```text
backend/
frontend/
schemas/
scripts/
tests/
installer/
offline/
docs/
.github/
README.md
CHANGELOG.md
SECURITY.md
docker-compose.yml
Modelfile
```

Los paquetes de instalación sencilla para usuarios finales deben generarse fuera del árbol fuente y publicarse únicamente como assets en GitHub Releases.

Criterio operativo:

- El repositorio conserva código, documentación estable, tests y fuentes del instalador.
- La página de GitHub Releases conserva ZIP instalables, SHA256, informes de generación y texto de release.
- La carpeta `release/` no debe formar parte del árbol fuente del repositorio.
