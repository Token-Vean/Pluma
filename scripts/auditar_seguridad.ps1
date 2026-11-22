$ErrorActionPreference = 'Stop'

$Image = 'pluma-app:0.7.4'
Write-Host 'PlumA v0.7.4 - auditoría local de seguridad' -ForegroundColor Cyan
Write-Host '------------------------------------------------'

Write-Host '[1/4] Comprobación estática del repositorio'
python scripts/security_static_check.py
if ($LASTEXITCODE) { exit $LASTEXITCODE }

Write-Host '[2/4] Tests unitarios'
$env:PYTHONPATH = 'backend'
python -m pytest -q
if ($LASTEXITCODE) { exit $LASTEXITCODE }

Write-Host '[3/4] Build limpio de la imagen Docker'
docker compose build --no-cache app
if ($LASTEXITCODE) { exit $LASTEXITCODE }

Write-Host '[4/4] Docker Scout: vulnerabilidades con fixed version'
$config = docker compose --profile bundled config --format json
if ($LASTEXITCODE) { exit $LASTEXITCODE }
$motor = ($config | Out-String | ConvertFrom-Json).services.ollama.image
foreach ($imagen in @($Image, $motor)) {
    docker scout cves --exit-code --only-severity critical $imagen
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    docker scout cves --exit-code --only-severity high,medium --only-fixed $imagen
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
}

Write-Host ''
Write-Host 'Criterio de release: 0 críticas, 0 altas corregibles y 0 medias corregibles.' -ForegroundColor Yellow
Write-Host 'Revise SECURITY_NOTES.md para mitigaciones y riesgos residuales.'
