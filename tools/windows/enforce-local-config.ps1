# =============================================================================
# tools/windows/enforce-local-config.ps1
# -----------------------------------------------------------------------------
# Aplica configuración local bloqueada al .env de PlumA en Windows y decide
# el modo de Ollama (host nativo vs. contenedor) según detección.
#
# Comportamiento:
#   1. Si no existe .env pero sí .env.example, lo copia.
#   2. Elimina del .env cualquier variable que la release pública NO permite
#      sobrescribir desde fuera, más variables obsoletas desde v0.6
#      (MODELO_NOMBRE, MODELFILE_PATH), más PLUMA_OLLAMA_MODE/URL que
#      las fija el propio instalador.
#   3. Garantiza PUERTO=8082 y MODELO_BASE=gemma4:e2b si no están definidas.
#   4. Detecta si hay Ollama nativo en el host con el MODELO_BASE descargado.
#   5. Escribe PLUMA_OLLAMA_MODE y PLUMA_OLLAMA_URL en .env según el caso.
#   6. Devuelve por stdout una línea "PLUMA_INSTALADOR_PROFILE=bundled" o
#      "PLUMA_INSTALADOR_PROFILE=" para que el .bat la lea y ajuste
#      COMPOSE_PROFILES antes del `docker compose up`.
#
# Se invoca desde instalar.bat con la CWD ya situada en la raíz del repo.
# =============================================================================

$ErrorActionPreference = 'Stop'

$repoRoot = (Get-Location).Path
$envPath = Join-Path $repoRoot '.env'
$envExamplePath = Join-Path $repoRoot '.env.example'

if (-not (Test-Path -LiteralPath $envPath) -and (Test-Path -LiteralPath $envExamplePath)) {
    Copy-Item -LiteralPath $envExamplePath -Destination $envPath
}

$content = ''
if (Test-Path -LiteralPath $envPath) {
    $content = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
}

# Variables que NO se pueden definir desde fuera: la release pública es
# estrictamente local. MODELO_NOMBRE y MODELFILE_PATH son obsoletas desde v0.6.
# PLUMA_OLLAMA_MODE y PLUMA_OLLAMA_URL las fija este script.
$blocked = @(
    'OLLAMA_URL', 'ALLOW_REMOTE_OLLAMA', 'ALLOW_NETWORK_EXPOSURE',
    'PLUMA_STRICT_LOCAL', 'PERFIL', 'COMPOSE_PROFILES',
    'MODELO_NOMBRE', 'MODELFILE_PATH',
    'PLUMA_OLLAMA_MODE', 'PLUMA_OLLAMA_URL'
)

$kept = New-Object System.Collections.Generic.List[string]
foreach ($line in ($content -split "`r?`n")) {
    if ($line -match '^\s*([^=#\s]+)\s*=' -and ($blocked -contains $Matches[1])) {
        continue
    }
    $kept.Add($line)
}

while ($kept.Count -gt 0 -and [string]::IsNullOrWhiteSpace($kept[$kept.Count - 1])) {
    $kept.RemoveAt($kept.Count - 1)
}

$text = if ($kept.Count -gt 0) { ($kept -join "`n") + "`n" } else { "" }

function Ensure-Line {
    param([string]$Key, [string]$Value)
    $pattern = '(?m)^' + [regex]::Escape($Key) + '='
    if ($script:text -notmatch $pattern) {
        $script:text += "$Key=$Value`n"
    }
}

Ensure-Line 'PUERTO' '8082'
Ensure-Line 'MODELO_BASE' 'gemma4:e2b'

# -----------------------------------------------------------------------------
# Detección de Ollama nativo en el host
# -----------------------------------------------------------------------------
# Leer MODELO_BASE del estado actual del texto.
$modeloBase = 'gemma4:e2b'
$m = [regex]::Match($text, '(?m)^MODELO_BASE=(.+)$')
if ($m.Success) { $modeloBase = $m.Groups[1].Value.Trim() }

$usarHostOllama = $false
try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:11434/api/tags' `
                              -TimeoutSec 2 `
                              -UseBasicParsing `
                              -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        $tags = $resp.Content | ConvertFrom-Json
        $nombres = @($tags.models | ForEach-Object { $_.name })
        if (($nombres -contains $modeloBase) -or ($nombres -contains ($modeloBase + ':latest'))) {
            $usarHostOllama = $true
            Write-Host "Ollama del host responde y tiene $modeloBase. Se evitara descarga duplicada."
        } else {
            Write-Host "Ollama del host responde pero NO tiene $modeloBase. Se usara Ollama dentro de Docker."
        }
    }
} catch {
    Write-Host "Ollama nativo no detectado en el host. Se usara Ollama dentro de Docker."
}

if ($usarHostOllama) {
    $text += "`n# Modo elegido por el instalador en funcion de la deteccion del host`n"
    $text += "PLUMA_OLLAMA_MODE=host`n"
    $text += "PLUMA_OLLAMA_URL=http://host.docker.internal:11434`n"
    $perfil = ''
} else {
    $text += "`n# Modo elegido por el instalador en funcion de la deteccion del host`n"
    $text += "PLUMA_OLLAMA_MODE=container`n"
    $text += "PLUMA_OLLAMA_URL=http://ollama:11434`n"
    $perfil = 'bundled'
}

# Escritura sin BOM, LF puros.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envPath, $text, $utf8NoBom)

Write-Host "Configuracion saneada. No se permite endpoint remoto ni publicacion en red."

# Línea que el .bat parseará para saber qué profile activar.
Write-Host "PLUMA_INSTALADOR_PROFILE=$perfil"
