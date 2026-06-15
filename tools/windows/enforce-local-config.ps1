# =============================================================================
# tools/windows/enforce-local-config.ps1
# -----------------------------------------------------------------------------
# Aplica configuración local bloqueada al .env de PlumA en Windows y fija
# el uso de Ollama nativo/local del usuario.
#
# Comportamiento:
#   1. Si no existe .env pero sí .env.example, lo copia.
#   2. Elimina del .env cualquier variable que la release pública NO permite
#      sobrescribir desde fuera, más variables obsoletas desde la arquitectura v0.7.0
#      (MODELO_NOMBRE, MODELFILE_PATH), más PLUMA_OLLAMA_MODE/URL que
#      las fija el propio instalador.
#   3. Garantiza PUERTO=8082 y MODELO_BASE=gemma4:e2b si no están definidas.
#   4. Detecta si hay Ollama nativo en el host y lista sus modelos.
#   5. Escribe PLUMA_OLLAMA_MODE=host y PLUMA_OLLAMA_URL en .env.
#   6. Devuelve por stdout una línea "PLUMA_INSTALADOR_PROFILE=" para que
#      Compose no active el contenedor de Ollama por defecto.
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
# estrictamente local. MODELO_NOMBRE y MODELFILE_PATH son obsoletas desde la arquitectura v0.7.0.
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
# Leer MODELO_BASE del estado actual del texto. Es preferencia, no requisito:
# si no existe, la UI permitirá elegir otro modelo local descargado.
$modeloBase = 'gemma4:e2b'
$m = [regex]::Match($text, '(?m)^MODELO_BASE=(.+)$')
if ($m.Success) { $modeloBase = $m.Groups[1].Value.Trim() }

try {
    # 127.0.0.1 explícito: evita problemas de resolución IPv6 de localhost.
    $resp = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' `
                              -TimeoutSec 5 `
                              -UseBasicParsing `
                              -ErrorAction Stop
    if ($resp.StatusCode -eq 200) {
        $tags = $resp.Content | ConvertFrom-Json
        $nombres = @($tags.models | ForEach-Object { $_.name } | Where-Object { $_ })
        if ($nombres.Count -eq 0) {
            Write-Host "Ollama del host responde, pero no hay modelos descargados. Ejecute: ollama pull $modeloBase"
        } elseif (($nombres -contains $modeloBase) -or ($nombres -contains ($modeloBase + ':latest'))) {
            Write-Host "Ollama del host responde y tiene $modeloBase."
        } else {
            Write-Host "Ollama del host responde, pero no tiene $modeloBase. PlumA usara otro modelo local disponible: $($nombres[0])"
        }
    }
} catch {
    Write-Host "Ollama nativo no responde en 127.0.0.1:11434. PlumA arrancara, pero mostrara error hasta que Ollama este iniciado."
}

$text += "`n# Modo elegido por el instalador: Ollama nativo/local del usuario`n"
$text += "PLUMA_OLLAMA_MODE=host`n"
$text += "PLUMA_OLLAMA_URL=http://host.docker.internal:11434`n"
$perfil = ''

# Escritura sin BOM, LF puros.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envPath, $text, $utf8NoBom)

Write-Host "Configuracion saneada. Se usara Ollama nativo/local; no se activa Ollama en Docker por defecto."

# Línea que el .bat parseará para saber qué profile activar.
Write-Host "PLUMA_INSTALADOR_PROFILE=$perfil"
