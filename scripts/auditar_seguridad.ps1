$ErrorActionPreference = 'Stop'

$Image = 'pluma-app:0.7.1'
Write-Host 'PlumA v0.7.1 - auditoría local de seguridad' -ForegroundColor Cyan
Write-Host '------------------------------------------------'

Write-Host '[1/4] Comprobación estática del repositorio'
python scripts/security_static_check.py

Write-Host '[2/4] Tests unitarios'
$env:PYTHONPATH = 'backend'
python -m pytest -q

Write-Host '[3/4] Build limpio de la imagen Docker'
docker compose build --no-cache app

Write-Host '[4/4] Docker Scout: vulnerabilidades con fixed version'
docker scout cves --only-fixed $Image

Write-Host ''
Write-Host 'Criterio de release: 0 críticas, 0 altas corregibles y 0 medias corregibles.' -ForegroundColor Yellow
Write-Host 'Revise SECURITY_NOTES.md para mitigaciones y riesgos residuales.'
