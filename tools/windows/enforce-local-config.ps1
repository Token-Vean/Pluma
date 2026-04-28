$ErrorActionPreference = "Stop"

$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$envFile = Join-Path $root ".env"
$exampleFile = Join-Path $root ".env.example"

if (!(Test-Path -LiteralPath $exampleFile)) {
  throw "No se encuentra .env.example: $exampleFile"
}

if (!(Test-Path -LiteralPath $envFile)) {
  Copy-Item -LiteralPath $exampleFile -Destination $envFile -Force
}

$script:content = Get-Content -LiteralPath $envFile -Raw -Encoding UTF8
if ($null -eq $script:content) { $script:content = "" }

# Quitar claves peligrosas o heredadas. PLUMA_OLLAMA_URL se regenera abajo
# exclusivamente con valores locales permitidos.
$blocked = @(
  "OLLAMA_URL",
  "PLUMA_OLLAMA_URL",
  "PLUMA_OLLAMA_MODE",
  "ALLOW_REMOTE_OLLAMA",
  "ALLOW_NETWORK_EXPOSURE",
  "PLUMA_STRICT_LOCAL",
  "PERFIL",
  "COMPOSE_PROFILES"
)

foreach ($name in $blocked) {
  $escaped = [regex]::Escape($name)
  $pattern = "(?m)^\s*$escaped\s*=.*(?:\r?\n)?"
  $script:content = [regex]::Replace($script:content, $pattern, "")
}

function Set-Or-Add([string]$name, [string]$value) {
  $escaped = [regex]::Escape($name)
  $pattern = "(?m)^\s*$escaped\s*=.*$"
  $replacement = "$name=$value"
  if ($script:content -match $pattern) {
    $script:content = [regex]::Replace($script:content, $pattern, $replacement)
  } else {
    if ($script:content.Length -gt 0 -and -not $script:content.EndsWith("`r`n") -and -not $script:content.EndsWith("`n")) {
      $script:content += "`r`n"
    }
    $script:content += "$replacement`r`n"
  }
}

function Get-EnvValue([string]$name, [string]$default) {
  $escaped = [regex]::Escape($name)
  $m = [regex]::Match($script:content, "(?m)^\s*$escaped\s*=\s*(.+?)\s*$")
  if ($m.Success) { return $m.Groups[1].Value.Trim() }
  return $default
}

function Find-OllamaExe {
  $cmd = Get-Command ollama.exe -ErrorAction SilentlyContinue
  if ($cmd -and $cmd.Source) { return $cmd.Source }
  $candidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"),
    (Join-Path $env:ProgramFiles "Ollama\ollama.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Ollama\ollama.exe")
  )
  foreach ($c in $candidates) {
    if ($c -and (Test-Path -LiteralPath $c)) { return $c }
  }
  return $null
}

function Test-HostOllamaModel([string]$modelName) {
  $exe = Find-OllamaExe
  if (-not $exe) {
    Write-Host "Ollama de Windows/macOS no detectado en PATH ni rutas habituales. Se usara Ollama Docker."
    return $false
  }
  try {
    $out = & $exe list 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) {
      Write-Host "Ollama local instalado, pero no responde a 'ollama list'. Se usara Ollama Docker."
      Write-Host ($out | Out-String)
      return $false
    }
    $escaped = [regex]::Escape($modelName)
    if (($out | Out-String) -match "(?m)^\s*$escaped(\s|$)") {
      Write-Host "Modelo base ya detectado en Ollama local del usuario: $modelName"
      return $true
    }
    Write-Host "Ollama local detectado, pero no contiene el modelo base $modelName. Se usara Ollama Docker."
    return $false
  } catch {
    Write-Host "No se pudo comprobar Ollama local: $($_.Exception.Message). Se usara Ollama Docker."
    return $false
  }
}

# Valores funcionales permitidos.
Set-Or-Add "PUERTO" "8082"
if ($script:content -notmatch "(?m)^\s*MODELO_BASE\s*=") { Set-Or-Add "MODELO_BASE" "gemma4:e2b" }
Set-Or-Add "MODELO_NOMBRE" "pluma:0.5.0"

$modelBase = Get-EnvValue "MODELO_BASE" "gemma4:e2b"
if (Test-HostOllamaModel $modelBase) {
  # host.docker.internal sigue siendo local: es el host Windows/macOS visto desde Docker.
  Set-Or-Add "PLUMA_OLLAMA_MODE" "host"
  Set-Or-Add "PLUMA_OLLAMA_URL" "http://host.docker.internal:11434"
  Write-Host "PlumA usara Ollama local ya instalado para evitar descargar de nuevo el modelo."
} else {
  Set-Or-Add "PLUMA_OLLAMA_MODE" "container"
  Set-Or-Add "PLUMA_OLLAMA_URL" "http://ollama:11434"
  Write-Host "PlumA usara el contenedor Ollama interno. Si falta el modelo, lo descargara ahi."
}

# Normalizar saltos y escribir con UTF-8 BOM para Windows PowerShell 5.1.
$utf8Bom = New-Object System.Text.UTF8Encoding($true)
[System.IO.File]::WriteAllText($envFile, $script:content, $utf8Bom)
Write-Host "Configuracion publica saneada. Modo local bloqueado aplicado por Docker Compose y backend."
exit 0
