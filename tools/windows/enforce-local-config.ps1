# =============================================================================
# tools/windows/enforce-local-config.ps1
# -----------------------------------------------------------------------------
# Aplica configuración local bloqueada al .env de PlumA en Windows y fija
# el uso de Ollama nativo cuando está disponible o del perfil bundled.
#
# Comportamiento:
#   1. Si no existe .env pero sí .env.example, lo copia.
#   2. Elimina del .env cualquier variable que la release pública NO permite
#      sobrescribir desde fuera, más variables obsoletas desde la arquitectura v0.7.0
#      (MODELO_NOMBRE, MODELFILE_PATH), más PLUMA_OLLAMA_MODE/URL que
#      las fija el propio instalador.
#   3. Garantiza PUERTO=8082 y MODELO_BASE=gemma4:e2b si no están definidas.
#   4. Detecta si hay Ollama nativo en el host y lista sus modelos.
#   5. Elige host si hay al menos un modelo local; en otro caso, bundled.
#   6. Escribe PLUMA_OLLAMA_MODE/URL y devuelve el perfil a instalar.bat.
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
#
# v0.7.2: se añaden los controles de seguridad del procesamiento. El compose
# los fija como literal; se bloquean aquí también para que un .env heredado de
# una instalación anterior no deje residuos que induzcan a pensar que siguen
# siendo configurables. USAR_SANDBOX_PARSERS es el caso crítico: a false
# desactivaba el aislamiento de proceso de los parsers de PDF/DOCX/imagen.
$blocked = @(
    'OLLAMA_URL', 'ALLOW_REMOTE_OLLAMA', 'ALLOW_NETWORK_EXPOSURE',
    'PLUMA_STRICT_LOCAL', 'OLLAMA_NO_CLOUD', 'PERFIL', 'COMPOSE_PROFILES',
    'MODELO_NOMBRE', 'MODELFILE_PATH',
    'PLUMA_OLLAMA_MODE', 'PLUMA_OLLAMA_URL',
    'USAR_SANDBOX_PARSERS', 'SANDBOX_TIMEOUT_SEGUNDOS', 'SANDBOX_MEMORIA_MB',
    'INCLUIR_HASH_DOCUMENTO_AUDITORIA', 'PERMITIR_APAGADO_UI'
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
$perfil = 'bundled'
$modo = 'container'
$ollamaUrl = 'http://ollama:11434'
$hostUtilizable = $false

# El cliente consulta exclusivamente loopback y no sigue redirecciones.
function Get-LocalOllamaJson([string]$Recurso) {
    $req = [Net.HttpWebRequest]::Create("http://127.0.0.1:11434/api/$Recurso")
    $req.Proxy = $null
    $req.AllowAutoRedirect = $false
    $req.Timeout = 5000
    $req.ReadWriteTimeout = 5000
    $resp = $req.GetResponse()
    try {
        if ([int]$resp.StatusCode -ne 200) { throw 'Respuesta HTTP inesperada de Ollama.' }
        $reader = [IO.StreamReader]::new($resp.GetResponseStream())
        try { return ($reader.ReadToEnd() | ConvertFrom-Json) } finally { $reader.Dispose() }
    } finally { $resp.Dispose() }
}
try {
    $version = (Get-LocalOllamaJson 'version').version
    $matchVersion = [regex]::Match([string]$version, '^v?(\d{1,5}\.\d{1,5}\.\d{1,5})(?:\+[0-9A-Za-z.-]+)?$')
    if ($version -isnot [string] -or -not $matchVersion.Success -or [version]$matchVersion.Groups[1].Value -lt [version]'0.35.0') {
        throw 'Se requiere Ollama estable 0.35.0 o posterior.'
    }
    $disabled = (Get-LocalOllamaJson 'status').cloud.disabled
    if ($disabled -isnot [bool] -or -not $disabled) {
        throw 'Para usar el motor nativo, active OLLAMA_NO_CLOUD=1 en el servicio Ollama y reinicielo.'
    }
    $nombres = @((Get-LocalOllamaJson 'tags').models | Where-Object {
        $_.name -is [string] -and $_.name -and $_.name -notmatch '(:cloud|:[^:]*-cloud)$' -and
        -not $_.remote_model -and -not $_.remote_host
    } | ForEach-Object { $_.name })
    if ($nombres.Count -eq 0) { throw 'El motor nativo no dispone de modelos locales.' }
    $hostUtilizable = $true
    Write-Host "Ollama $version con nube desactivada y modelos locales disponibles."
} catch {
    Write-Host "Motor nativo no disponible para PlumA. $($_.Exception.Message) Se usara el motor de Docker."
}

if ($hostUtilizable) {
    $perfil = 'host'
    $modo = 'host'
    $ollamaUrl = 'http://host.docker.internal:11434'
}

$text += "`n# Modo elegido automáticamente por el instalador`n"
$text += "PLUMA_OLLAMA_MODE=$modo`n"
$text += "PLUMA_OLLAMA_URL=$ollamaUrl`n"

# Escritura sin BOM, LF puros.
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($envPath, $text, $utf8NoBom)

Write-Host "Configuracion saneada. Perfil seleccionado: $perfil."

# Línea que el .bat parseará para saber qué profile activar.
Write-Host "PLUMA_INSTALADOR_PROFILE=$perfil"
