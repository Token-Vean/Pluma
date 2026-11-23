<#
=============================================================================
PlumA - panel de control para Windows
-----------------------------------------------------------------------------
Ventana que guía la instalación y el uso diario de PlumA sin consola:
comprobar requisitos, instalar, iniciar, abrir, detener, diagnosticar,
ver el registro y desinstalar.

- Se abre con "PlumA - Instalar y abrir.vbs" (sin consola) o con
  "ayuda\Abrir sin VBScript.bat".
- Ejecuta los scripts no interactivos de panel\scripts, que siguen el mismo
  flujo que instalar.bat, iniciar.bat, detener.bat y desinstalar.bat y
  reutilizan del repositorio tools\windows\enforce-local-config.ps1 (el
  saneador de configuración), pluma-env.bat, pluma-wait-ready.bat y
  pluma-load-offline-assets.bat.
- Solo habla con 127.0.0.1 (PlumA en :8082, Ollama en :11434) y sin proxy.
- Registro en %LOCALAPPDATA%\PlumA\panel\panel.log (se rota al superar 1 MB).
- Cerrar el panel NO detiene PlumA.

Forma parte de PlumA (AGPL-3.0-or-later). Desde la v0.7.4 está versionado en
el repositorio (panel\) y scripts\empaquetar_windows.py lo incluye en el
paquete para Windows de cada release.

Codificación: UTF-8 con BOM. Windows PowerShell 5.1 interpreta como ANSI los
scripts sin BOM y estropearía los acentos de la interfaz.
=============================================================================
#>
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$script:PanelDir   = Join-Path $env:LOCALAPPDATA 'PlumA\panel'
$script:LogFile    = Join-Path $script:PanelDir 'panel.log'
$script:MaxLogBytes = 1MB
$script:UrlPlumA   = 'http://127.0.0.1:8082'
$script:UrlEstado  = 'http://127.0.0.1:8082/api/estado'
$script:UrlOllama  = 'http://127.0.0.1:11434/api/tags'
$script:UrlOllamaVersion = 'http://127.0.0.1:11434/api/version'
# Debe coincidir con VERSION_MINIMA_OLLAMA de backend\app\bootstrap.py: el
# backend tampoco arranca con un Ollama anterior (CVE-2026-103663).
$script:OllamaMinVersion = [version]'0.35.0'
$script:UrlDocker  = 'https://www.docker.com/products/docker-desktop/'
$script:Busy       = $false
$script:Closing    = $false
$script:CurrentProcess = $null
$script:LastOpenAt = [DateTime]::MinValue
$script:Form       = $null
$script:LogBox     = $null

function Show-FatalMessage([string]$Message) {
  try {
    Add-Type -AssemblyName System.Windows.Forms
    [void][System.Windows.Forms.MessageBox]::Show($Message, 'PlumA',
      [System.Windows.Forms.MessageBoxButtons]::OK,
      [System.Windows.Forms.MessageBoxIcon]::Error)
  } catch {
    try {
      $ws = New-Object -ComObject WScript.Shell
      [void]$ws.Popup($Message, 0, 'PlumA', 16)
    } catch {}
  }
}

# -----------------------------------------------------------------------------
# Registro
# -----------------------------------------------------------------------------
function Initialize-PanelFiles {
  New-Item -ItemType Directory -Force -Path $script:PanelDir | Out-Null
  if (Test-Path -LiteralPath $script:LogFile) {
    if ((Get-Item -LiteralPath $script:LogFile).Length -gt $script:MaxLogBytes) {
      Move-Item -LiteralPath $script:LogFile -Destination ($script:LogFile + '.1') -Force
    }
  }
  # Restos de ejecuciones interrumpidas (cierre forzado, apagón...).
  Get-ChildItem -LiteralPath $script:PanelDir -Filter 'run-*' -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
}

function Write-FileLog([string]$Text) {
  $ts = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
  try { Add-Content -LiteralPath $script:LogFile -Encoding UTF8 -Value "[$ts] $Text" } catch {}
}

function Write-PanelLog([string]$Text) {
  if ($null -eq $Text) { return }
  Write-FileLog $Text
  if ($null -eq $script:LogBox) { return }
  $ts = Get-Date -Format 'HH:mm:ss'
  if ($script:LogBox.TextLength -gt 200000) {
    $script:LogBox.Text = $script:LogBox.Text.Substring($script:LogBox.TextLength - 100000)
  }
  $script:LogBox.AppendText("[$ts] $Text`r`n")
  $script:LogBox.SelectionStart = $script:LogBox.TextLength
  $script:LogBox.ScrollToCaret()
  [System.Windows.Forms.Application]::DoEvents()
}

function Show-Message([string]$Text, [string]$Kind = 'Info', [switch]$YesNo) {
  if ($script:Closing) { return $false }
  $icon = [System.Windows.Forms.MessageBoxIcon]::Information
  if ($Kind -eq 'Error')    { $icon = [System.Windows.Forms.MessageBoxIcon]::Error }
  if ($Kind -eq 'Warning')  { $icon = [System.Windows.Forms.MessageBoxIcon]::Warning }
  if ($Kind -eq 'Question') { $icon = [System.Windows.Forms.MessageBoxIcon]::Question }
  $buttons = [System.Windows.Forms.MessageBoxButtons]::OK
  if ($YesNo) { $buttons = [System.Windows.Forms.MessageBoxButtons]::YesNo }
  $result = [System.Windows.Forms.MessageBox]::Show($script:Form, $Text, 'PlumA', $buttons, $icon)
  return ($result -eq [System.Windows.Forms.DialogResult]::Yes)
}

# -----------------------------------------------------------------------------
# Rutas y estado de la instalación
# -----------------------------------------------------------------------------
$script:RepoRoot = ''
$script:ScriptsDir = ''
$script:EnvFile  = ''

function Initialize-Paths {
  # Este fichero vive en <PlumA>\panel.
  $script:RepoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
  $script:ScriptsDir = Join-Path $PSScriptRoot 'scripts'
  $script:EnvFile  = Join-Path $script:RepoRoot '.env'
  if (-not (Test-Path -LiteralPath (Join-Path $script:RepoRoot 'docker-compose.yml'))) {
    throw "No se encuentra docker-compose.yml en $($script:RepoRoot). El panel debe estar en la carpeta panel dentro de la carpeta de PlumA."
  }
}

function Get-PlumAVersion {
  $file = Join-Path $script:RepoRoot 'backend\app\version.py'
  if (Test-Path -LiteralPath $file) {
    $m = [regex]::Match([System.IO.File]::ReadAllText($file), 'APP_VERSION\s*=\s*"([^"]+)"')
    if ($m.Success) { return $m.Groups[1].Value }
  }
  return '?'
}

function Get-OllamaMode {
  if (-not (Test-Path -LiteralPath $script:EnvFile)) { return '' }
  $m = [regex]::Match([System.IO.File]::ReadAllText($script:EnvFile), '(?m)^PLUMA_OLLAMA_MODE=([A-Za-z]+)')
  if ($m.Success) { return $m.Groups[1].Value.ToLowerInvariant() }
  return ''
}

function Test-Http([string]$Url, [int]$TimeoutMs) {
  $response = $null
  try {
    $request = [System.Net.WebRequest]::Create($Url)
    $request.Method = 'GET'
    $request.Timeout = $TimeoutMs
    # Sin proxy: un proxy corporativo no debe intervenir en tráfico local.
    $request.Proxy = $null
    $response = $request.GetResponse()
    return ([int]$response.StatusCode -eq 200)
  } catch {
    return $false
  } finally {
    if ($null -ne $response) { $response.Close() }
  }
}

# Devuelve el cuerpo de la respuesta o $null si no hay respuesta 200.
function Get-HttpText([string]$Url, [int]$TimeoutMs) {
  $response = $null
  $reader = $null
  try {
    $request = [System.Net.WebRequest]::Create($Url)
    $request.Method = 'GET'
    $request.Timeout = $TimeoutMs
    $request.Proxy = $null
    $response = $request.GetResponse()
    if ([int]$response.StatusCode -ne 200) { return $null }
    $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
    return $reader.ReadToEnd()
  } catch {
    return $null
  } finally {
    if ($null -ne $reader) { $reader.Close() }
    if ($null -ne $response) { $response.Close() }
  }
}

# Versión del Ollama del equipo como [version], o $null si no se puede leer.
function Get-OllamaVersion {
  $body = Get-HttpText $script:UrlOllamaVersion 3000
  if ($null -eq $body) { return $null }
  $m = [regex]::Match($body, '"version"\s*:\s*"v?(\d+)\.(\d+)\.(\d+)')
  if (-not $m.Success) { return $null }
  return New-Object System.Version([int]$m.Groups[1].Value, [int]$m.Groups[2].Value, [int]$m.Groups[3].Value)
}

function Find-DockerExe {
  $candidates = New-Object System.Collections.ArrayList
  $cmd = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($null -ne $cmd) { [void]$candidates.Add($cmd.Path) }
  [void]$candidates.Add((Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe'))
  [void]$candidates.Add((Join-Path $env:LOCALAPPDATA 'Docker\Docker\resources\bin\docker.exe'))
  foreach ($candidate in $candidates) {
    if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
  }
  return $null
}

function Find-DockerDesktopExe {
  foreach ($candidate in @(
      (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
      (Join-Path $env:LOCALAPPDATA 'Docker\Docker\Docker Desktop.exe'))) {
    if (Test-Path -LiteralPath $candidate) { return $candidate }
  }
  return $null
}

# -----------------------------------------------------------------------------
# Ejecución de procesos sin ventana
# -----------------------------------------------------------------------------
function Wait-ProcessResponsive($Process, [int]$TimeoutSeconds) {
  $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  while (-not $Process.HasExited) {
    if ($TimeoutSeconds -gt 0 -and (Get-Date) -gt $deadline) {
      try { $Process.Kill() } catch {}
      return $false
    }
    Start-Sleep -Milliseconds 150
    [System.Windows.Forms.Application]::DoEvents()
  }
  return $true
}

function Wait-Responsive([int]$Seconds) {
  $deadline = (Get-Date).AddSeconds($Seconds)
  while ((Get-Date) -lt $deadline) {
    Start-Sleep -Milliseconds 150
    [System.Windows.Forms.Application]::DoEvents()
  }
}

# Ejecuta un programa sin mostrar su salida y devuelve el código de salida
# (-1 si se agota el tiempo).
function Invoke-Quiet([string]$FileName, [string]$Arguments, [int]$TimeoutSeconds = 30) {
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = $FileName
  $psi.Arguments = $Arguments
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $process = [System.Diagnostics.Process]::Start($psi)
  # Vaciar los flujos en segundo plano para que el proceso no se bloquee.
  $null = $process.StandardOutput.ReadToEndAsync()
  $null = $process.StandardError.ReadToEndAsync()
  if (-not (Wait-ProcessResponsive $process $TimeoutSeconds)) { return -1 }
  $process.WaitForExit()
  return $process.ExitCode
}

# Lee lo que el script haya añadido al fichero de salida desde $Offset y lo
# vuelca al registro. Solo procesa líneas completas salvo al final.
function Read-NewOutput([string]$Path, [long]$Offset, [bool]$Final) {
  if (-not (Test-Path -LiteralPath $Path)) { return $Offset }
  $stream = $null
  try {
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $length = $stream.Length
    if ($length -le $Offset) { return $Offset }
    $count = [int]($length - $Offset)
    $buffer = New-Object byte[] $count
    [void]$stream.Seek($Offset, [System.IO.SeekOrigin]::Begin)
    $read = $stream.Read($buffer, 0, $count)
    $usable = $read
    if (-not $Final) {
      $usable = 0
      for ($i = $read - 1; $i -ge 0; $i--) {
        if ($buffer[$i] -eq 10) { $usable = $i + 1; break }
      }
    }
    if ($usable -le 0) { return $Offset }
    $text = [System.Text.Encoding]::UTF8.GetString($buffer, 0, $usable)
    foreach ($line in ($text -split "`r?`n")) {
      # Las barras de progreso reescriben la línea con retornos de carro:
      # se conserva solo el último estado.
      $visible = ($line -split "`r")[-1]
      if ($visible.Trim().Length -gt 0) { Write-PanelLog $visible }
    }
    return ($Offset + $usable)
  } catch {
    return $Offset
  } finally {
    if ($null -ne $stream) { $stream.Close() }
  }
}

# Ejecuta panel\scripts\<BatName> sin ventana, con su salida en el registro.
function Invoke-CoreScript([string]$BatName) {
  $bat = Join-Path $script:ScriptsDir $BatName
  if (-not (Test-Path -LiteralPath $bat)) { throw "No se encuentra $bat" }
  $id = [Guid]::NewGuid().ToString('N')
  $cmdFile = Join-Path $script:PanelDir "run-$id.cmd"
  $outFile = Join-Path $script:PanelDir "run-$id.log"
  # En un .cmd, % debe duplicarse para quedar literal. Las comillas no pueden
  # aparecer en rutas de Windows.
  $batQ = '"' + ($bat -replace '%', '%%') + '"'
  $outQ = '"' + ($outFile -replace '%', '%%') + '"'
  # chcp 65001 va antes de cualquier ruta: cmd lee el resto del fichero como
  # UTF-8 y las rutas con tildes o eñes (C:\Users\José) funcionan.
  $lines = @(
    '@echo off',
    'chcp 65001 >nul',
    ('call ' + $batQ + ' 1>' + $outQ + ' 2>&1'),
    'exit /b %ERRORLEVEL%'
  )
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($cmdFile, (($lines -join "`r`n") + "`r`n"), $utf8NoBom)

  Write-PanelLog "> $BatName"
  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = Join-Path $env:SystemRoot 'System32\cmd.exe'
  # /s con comillas exteriores: cmd conserva las interiores aunque la ruta
  # contenga espacios o paréntesis.
  $psi.Arguments = '/d /s /c ""' + $cmdFile + '""'
  $psi.WorkingDirectory = $script:RepoRoot
  $psi.UseShellExecute = $false
  $psi.CreateNoWindow = $true
  $process = $null
  try {
    $process = [System.Diagnostics.Process]::Start($psi)
    $script:CurrentProcess = $process
    $offset = [long]0
    while (-not $process.HasExited) {
      $offset = Read-NewOutput $outFile $offset $false
      Start-Sleep -Milliseconds 200
      [System.Windows.Forms.Application]::DoEvents()
    }
    $process.WaitForExit()
    $offset = Read-NewOutput $outFile $offset $true
    Write-PanelLog ("Código de salida: " + $process.ExitCode)
    return $process.ExitCode
  } finally {
    $script:CurrentProcess = $null
    Remove-Item -LiteralPath $cmdFile -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $outFile -Force -ErrorAction SilentlyContinue
  }
}

function Stop-CurrentProcess {
  $process = $script:CurrentProcess
  if ($null -ne $process -and -not $process.HasExited) {
    $taskkill = Join-Path $env:SystemRoot 'System32\taskkill.exe'
    [void](Invoke-Quiet $taskkill ('/PID ' + $process.Id + ' /T /F') 15)
  }
}

# -----------------------------------------------------------------------------
# Docker
# -----------------------------------------------------------------------------
# Devuelve 'ok', 'missing' (no instalado) o 'stopped' (no responde). Si Docker
# Desktop está instalado pero parado, lo abre y espera a que responda.
function Start-DockerIfNeeded {
  $docker = Find-DockerExe
  if ($null -eq $docker) { return 'missing' }
  if ((Invoke-Quiet $docker 'info' 30) -eq 0) { return 'ok' }
  $desktop = Find-DockerDesktopExe
  if ($null -eq $desktop) { return 'stopped' }
  Write-PanelLog 'Docker Desktop no está arrancado. Abriéndolo (puede tardar un par de minutos)...'
  Start-Process -FilePath $desktop -WindowStyle Minimized
  $deadline = (Get-Date).AddSeconds(150)
  while ((Get-Date) -lt $deadline) {
    Wait-Responsive 3
    if ((Invoke-Quiet $docker 'info' 20) -eq 0) {
      Write-PanelLog 'Docker Desktop ya responde.'
      return 'ok'
    }
  }
  return 'stopped'
}

function Get-DockerProblemText([string]$State) {
  if ($State -eq 'missing') {
    return 'Docker Desktop no está instalado (no se encuentra docker.exe). Pulsa «1. Comprobar requisitos» para abrir la página de descarga.'
  }
  return 'Docker no responde. Abre Docker Desktop, espera a que indique que está en marcha y vuelve a intentarlo.'
}

# -----------------------------------------------------------------------------
# Acciones
# -----------------------------------------------------------------------------
function Invoke-Guarded([string]$Label, [scriptblock]$Action) {
  if ($script:Busy) { return }
  $script:Busy = $true
  Set-Busy $true $Label
  try {
    & $Action
  } catch {
    Write-PanelLog ('ERROR: ' + $_.Exception.Message)
    [void](Show-Message ($_.Exception.Message + "`r`n`r`nRegistro: " + $script:LogFile) 'Error')
  } finally {
    $script:Busy = $false
    Set-Busy $false 'Listo.'
    Update-State
  }
}

function Test-Requirements {
  $problems = New-Object System.Collections.Generic.List[string]
  $notes = New-Object System.Collections.Generic.List[string]

  Write-PanelLog 'Comprobando Docker...'
  $dockerState = Start-DockerIfNeeded
  if ($dockerState -ne 'ok') {
    $problems.Add((Get-DockerProblemText $dockerState))
  } else {
    $docker = Find-DockerExe
    Write-PanelLog "Docker disponible: $docker"
    if ((Invoke-Quiet $docker 'compose version' 30) -ne 0) {
      $problems.Add('Docker Compose v2 no está disponible. Actualiza Docker Desktop.')
    }
  }

  Write-PanelLog 'Buscando un Ollama instalado en el equipo...'
  if (Test-Http $script:UrlOllama 3000) {
    $ollamaVersion = Get-OllamaVersion
    if ($null -eq $ollamaVersion) {
      $problems.Add("No se ha podido leer la versión del Ollama del equipo. PlumA necesita Ollama $($script:OllamaMinVersion) o posterior: comprueba la versión con «ollama --version» y, si es anterior, actualízalo desde https://ollama.com/download.")
    } elseif ($ollamaVersion -lt $script:OllamaMinVersion) {
      $problems.Add("El Ollama del equipo es la versión $ollamaVersion, afectada por un aviso de seguridad (CVE-2026-103663). PlumA necesita Ollama $($script:OllamaMinVersion) o posterior: actualízalo desde https://ollama.com/download, reinícialo y vuelve a pulsar «1. Comprobar requisitos».")
    } else {
      Write-PanelLog "Ollama del equipo: versión $ollamaVersion"
      $notes.Add('Ollama del equipo detectado: si tiene algún modelo, PlumA lo reutilizará sin descargar nada. Conviene que escuche solo en 127.0.0.1 y que tenga desactivadas las funciones cloud (OLLAMA_NO_CLOUD=1); ver INSTALACION.md.')
    }
  } else {
    $notes.Add('No hay Ollama en el equipo: la instalación arrancará Ollama dentro de Docker y descargará el modelo base (varios GB, requiere Internet solo esa vez).')
  }

  try {
    $drive = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($script:RepoRoot))
    $freeGb = [math]::Round($drive.AvailableFreeSpace / 1GB, 1)
    Write-PanelLog "Espacio libre en $($drive.Name): $freeGb GB"
    if ($freeGb -lt 10) {
      $notes.Add("Quedan $freeGb GB libres en $($drive.Name). La imagen y el modelo pueden necesitar unos 10 GB.")
    }
  } catch {}

  foreach ($note in $notes) { Write-PanelLog $note }
  if ($problems.Count -eq 0) {
    [void](Show-Message ("Todo listo para instalar o iniciar PlumA.`r`n`r`n- " + ($notes -join "`r`n- ")) 'Info')
    return
  }
  foreach ($problem in $problems) { Write-PanelLog ('PENDIENTE: ' + $problem) }
  $message = "Hay requisitos pendientes:`r`n`r`n- " + ($problems -join "`r`n- ")
  if ($dockerState -eq 'missing') {
    if (Show-Message ($message + "`r`n`r`n¿Abrir la página de descarga de Docker Desktop?") 'Warning' -YesNo) {
      Start-Process $script:UrlDocker
    }
  } else {
    [void](Show-Message $message 'Warning')
  }
}

function Open-PlumA([bool]$Force = $false) {
  if (-not (Test-Http $script:UrlEstado 3000)) {
    [void](Show-Message "PlumA no responde en $($script:UrlPlumA).`r`n`r`nPulsa «Iniciar» (o «Instalar» si es la primera vez)." 'Warning')
    return
  }
  $now = Get-Date
  if (-not $Force -and ($now - $script:LastOpenAt).TotalSeconds -lt 5) {
    Write-PanelLog 'Apertura omitida para no duplicar pestañas.'
    return
  }
  $script:LastOpenAt = $now
  Write-PanelLog "Abriendo $($script:UrlPlumA)"
  Start-Process $script:UrlPlumA
}

function Invoke-InstallOrStart([string]$BatName, [string]$SuccessText) {
  $dockerState = Start-DockerIfNeeded
  if ($dockerState -ne 'ok') {
    [void](Show-Message (Get-DockerProblemText $dockerState) 'Warning')
    return
  }
  $code = Invoke-CoreScript $BatName
  if ($code -ne 0) {
    [void](Show-Message ("La operación no ha terminado bien (código $code). Revisa el registro del panel o pulsa «Diagnóstico».`r`n`r`nRegistro: " + $script:LogFile) 'Warning')
    return
  }
  if (Test-Http $script:UrlEstado 5000) {
    if (Show-Message ($SuccessText + "`r`n`r`n¿Abrir PlumA en el navegador?") 'Question' -YesNo) {
      Open-PlumA $true
    }
  } else {
    [void](Show-Message 'Los servicios han arrancado, pero PlumA todavía no responde. Espera unos segundos y pulsa «Abrir PlumA», o usa «Diagnóstico».' 'Warning')
  }
}

function Invoke-Stop {
  $docker = Find-DockerExe
  if ($null -eq $docker -or (Invoke-Quiet $docker 'info' 30) -ne 0) {
    [void](Show-Message 'Docker no está en marcha, así que PlumA ya está detenida.' 'Info')
    return
  }
  $code = Invoke-CoreScript 'pluma-stop-core.bat'
  if ($code -eq 0) {
    [void](Show-Message 'PlumA se ha detenido. Los datos y el modelo se conservan.' 'Info')
  } else {
    [void](Show-Message "No se pudo detener PlumA (código $code). Revisa el registro." 'Warning')
  }
}

function Invoke-Uninstall {
  $mode = Get-OllamaMode
  $text = "Se eliminarán los contenedores y volúmenes de PlumA y su imagen local."
  if ($mode -eq 'host') {
    $text += "`r`n`r`nNO se tocará tu Ollama ni sus modelos."
  } else {
    $text += "`r`n`r`nTambién se eliminará el modelo descargado dentro de Docker (3-5 GB)."
  }
  $text += "`r`nNo se borrará la carpeta del proyecto ni Docker.`r`n`r`n¿Continuar?"
  if (-not (Show-Message $text 'Warning' -YesNo)) { return }
  $dockerState = Start-DockerIfNeeded
  if ($dockerState -ne 'ok') {
    [void](Show-Message (Get-DockerProblemText $dockerState) 'Warning')
    return
  }
  $code = Invoke-CoreScript 'pluma-uninstall-core.bat'
  if ($code -eq 0) {
    [void](Show-Message 'Desinstalación completada. Puedes borrar la carpeta del proyecto si ya no la necesitas.' 'Info')
  } else {
    [void](Show-Message "La desinstalación terminó con errores (código $code). Revisa el registro." 'Warning')
  }
}

function Open-LogFile {
  if (-not (Test-Path -LiteralPath $script:LogFile)) { Write-FileLog 'Registro creado.' }
  Start-Process -FilePath (Join-Path $env:SystemRoot 'notepad.exe') -ArgumentList ('"' + $script:LogFile + '"')
}

# -----------------------------------------------------------------------------
# Interfaz
# -----------------------------------------------------------------------------
function New-UiFont([single]$Size, [string]$Style = 'Regular') {
  $fontStyle = [System.Drawing.FontStyle]::Regular
  if ($Style -eq 'Bold') { $fontStyle = [System.Drawing.FontStyle]::Bold }
  return New-Object System.Drawing.Font('Segoe UI', $Size, $fontStyle)
}

function Set-Busy([bool]$IsBusy, [string]$Message) {
  $script:StatusLabel.Text = $Message
  if ($IsBusy) {
    $script:Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
    $script:Progress.MarqueeAnimationSpeed = 30
    foreach ($b in $script:Buttons) { $b.Enabled = $false }
  } else {
    $script:Progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
    $script:Progress.MarqueeAnimationSpeed = 0
    $script:Progress.Value = 0
  }
  [System.Windows.Forms.Application]::DoEvents()
}

function Update-State {
  if ($script:Busy) { return }
  $installed = Test-Path -LiteralPath $script:EnvFile
  $running = Test-Http $script:UrlEstado 1500
  $mode = Get-OllamaMode

  if ($running) {
    $script:StateLabel.Text = 'PlumA: en marcha en ' + $script:UrlPlumA
    $script:StateLabel.ForeColor = [System.Drawing.Color]::FromArgb(28, 110, 60)
  } elseif ($installed) {
    $script:StateLabel.Text = 'PlumA: detenida'
    $script:StateLabel.ForeColor = [System.Drawing.Color]::FromArgb(150, 90, 0)
  } else {
    $script:StateLabel.Text = 'PlumA: sin instalar en esta carpeta'
    $script:StateLabel.ForeColor = [System.Drawing.Color]::FromArgb(90, 95, 105)
  }
  if ($mode -eq 'host') {
    $script:ModeLabel.Text = 'Motor de IA: Ollama del equipo'
  } elseif ($mode -eq 'container') {
    $script:ModeLabel.Text = 'Motor de IA: Ollama dentro de Docker'
  } else {
    $script:ModeLabel.Text = 'Motor de IA: se decidirá al instalar'
  }

  foreach ($b in $script:Buttons) { $b.Enabled = $true }
  $script:BtnStart.Enabled = $installed -and -not $running
  $script:BtnOpen.Enabled = $running
  $script:BtnStop.Enabled = $installed
  $script:BtnUninstall.Enabled = $installed
}

function New-ActionButton([string]$Text, [string]$Tip, [scriptblock]$Handler) {
  $button = New-Object System.Windows.Forms.Button
  $button.Text = $Text
  $button.AutoSize = $true
  $button.MinimumSize = New-Object System.Drawing.Size(112, 34)
  $button.Padding = New-Object System.Windows.Forms.Padding(6, 2, 6, 2)
  $button.Margin = New-Object System.Windows.Forms.Padding(0, 0, 8, 8)
  $button.Add_Click($Handler)
  $script:ToolTip.SetToolTip($button, $Tip)
  $script:ButtonBar.Controls.Add($button)
  [void]$script:Buttons.Add($button)
  return $button
}

function Show-Panel {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
  [System.Windows.Forms.Application]::EnableVisualStyles()

  $version = Get-PlumAVersion
  $form = New-Object System.Windows.Forms.Form
  $script:Form = $form
  $form.Text = "PlumA $version - panel de control"
  $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
  $form.ClientSize = New-Object System.Drawing.Size(880, 620)
  $form.MinimumSize = New-Object System.Drawing.Size(760, 540)
  $form.BackColor = [System.Drawing.Color]::FromArgb(248, 249, 251)
  $form.Font = New-UiFont 9
  $iconFile = Join-Path $script:RepoRoot 'frontend\static\img\favicon.ico'
  if (Test-Path -LiteralPath $iconFile) {
    try { $form.Icon = New-Object System.Drawing.Icon($iconFile) } catch {}
  }

  $layout = New-Object System.Windows.Forms.TableLayoutPanel
  $layout.Dock = [System.Windows.Forms.DockStyle]::Fill
  $layout.Padding = New-Object System.Windows.Forms.Padding(18, 14, 18, 10)
  $layout.ColumnCount = 1
  $layout.RowCount = 7
  [void]$layout.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
  foreach ($i in 0..3) {
    [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
  }
  [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
  [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::Percent, 100)))
  [void]$layout.RowStyles.Add((New-Object System.Windows.Forms.RowStyle([System.Windows.Forms.SizeType]::AutoSize)))
  $form.Controls.Add($layout)

  # Fila 0: logotipo o título, y distintivo de modo local.
  $header = New-Object System.Windows.Forms.TableLayoutPanel
  $header.Dock = [System.Windows.Forms.DockStyle]::Fill
  $header.AutoSize = $true
  $header.ColumnCount = 2
  [void]$header.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100)))
  [void]$header.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::AutoSize)))
  $logoFile = Join-Path $script:RepoRoot 'frontend\static\img\pluma-logo-full.png'
  $logoShown = $false
  if (Test-Path -LiteralPath $logoFile) {
    try {
      $picture = New-Object System.Windows.Forms.PictureBox
      $picture.Size = New-Object System.Drawing.Size(230, 58)
      $picture.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
      $picture.Image = [System.Drawing.Image]::FromFile($logoFile)
      $header.Controls.Add($picture, 0, 0)
      $logoShown = $true
    } catch {}
  }
  if (-not $logoShown) {
    $title = New-Object System.Windows.Forms.Label
    $title.Text = 'PlumA'
    $title.Font = New-UiFont 22 'Bold'
    $title.AutoSize = $true
    $header.Controls.Add($title, 0, 0)
  }
  $badge = New-Object System.Windows.Forms.Label
  $badge.Text = "v$version  ·  solo local (127.0.0.1)"
  $badge.Font = New-UiFont 9 'Bold'
  $badge.AutoSize = $true
  $badge.Anchor = [System.Windows.Forms.AnchorStyles]::Right
  $badge.ForeColor = [System.Drawing.Color]::FromArgb(28, 92, 56)
  $badge.BackColor = [System.Drawing.Color]::FromArgb(222, 245, 232)
  $badge.Padding = New-Object System.Windows.Forms.Padding(10, 5, 10, 5)
  $header.Controls.Add($badge, 1, 0)
  $layout.Controls.Add($header, 0, 0)

  # Fila 1: explicación.
  $intro = New-Object System.Windows.Forms.Label
  $intro.Text = "Primera vez: pulsa «1. Comprobar requisitos» y después «2. Instalar». " +
    "El resto de días basta con «Iniciar» y «Abrir PlumA». Los documentos se procesan en este equipo. " +
    "Cerrar este panel no detiene PlumA: usa «Detener» cuando termines."
  $intro.AutoSize = $true
  $intro.MaximumSize = New-Object System.Drawing.Size(840, 0)
  $intro.Margin = New-Object System.Windows.Forms.Padding(3, 10, 3, 8)
  $intro.ForeColor = [System.Drawing.Color]::FromArgb(60, 65, 72)
  $layout.Controls.Add($intro, 0, 1)

  # Fila 2: estado de PlumA y del motor.
  $stateRow = New-Object System.Windows.Forms.FlowLayoutPanel
  $stateRow.AutoSize = $true
  $stateRow.Dock = [System.Windows.Forms.DockStyle]::Fill
  $script:StateLabel = New-Object System.Windows.Forms.Label
  $script:StateLabel.AutoSize = $true
  $script:StateLabel.Font = New-UiFont 10 'Bold'
  $script:StateLabel.Margin = New-Object System.Windows.Forms.Padding(3, 0, 24, 0)
  $script:ModeLabel = New-Object System.Windows.Forms.Label
  $script:ModeLabel.AutoSize = $true
  $script:ModeLabel.Font = New-UiFont 10
  $stateRow.Controls.Add($script:StateLabel)
  $stateRow.Controls.Add($script:ModeLabel)
  $layout.Controls.Add($stateRow, 0, 2)

  # Fila 3: operación en curso.
  $script:StatusLabel = New-Object System.Windows.Forms.Label
  $script:StatusLabel.AutoSize = $true
  $script:StatusLabel.Margin = New-Object System.Windows.Forms.Padding(3, 8, 3, 4)
  $script:StatusLabel.Text = 'Listo.'
  $layout.Controls.Add($script:StatusLabel, 0, 3)

  # Fila 4: progreso.
  $script:Progress = New-Object System.Windows.Forms.ProgressBar
  $script:Progress.Dock = [System.Windows.Forms.DockStyle]::Fill
  $script:Progress.Height = 16
  $layout.Controls.Add($script:Progress, 0, 4)

  # Fila 5: registro.
  $script:LogBox = New-Object System.Windows.Forms.TextBox
  $script:LogBox.Multiline = $true
  $script:LogBox.ReadOnly = $true
  $script:LogBox.MaxLength = 0
  $script:LogBox.WordWrap = $true
  $script:LogBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
  $script:LogBox.BackColor = [System.Drawing.Color]::White
  $script:LogBox.Font = New-Object System.Drawing.Font('Consolas', 9)
  $script:LogBox.Dock = [System.Windows.Forms.DockStyle]::Fill
  $script:LogBox.Margin = New-Object System.Windows.Forms.Padding(3, 8, 3, 10)
  $layout.Controls.Add($script:LogBox, 0, 5)

  # Fila 6: botones.
  $script:ButtonBar = New-Object System.Windows.Forms.FlowLayoutPanel
  $script:ButtonBar.AutoSize = $true
  $script:ButtonBar.Dock = [System.Windows.Forms.DockStyle]::Fill
  $script:ButtonBar.WrapContents = $true
  $layout.Controls.Add($script:ButtonBar, 0, 6)
  $script:ToolTip = New-Object System.Windows.Forms.ToolTip
  $script:Buttons = New-Object System.Collections.ArrayList

  [void](New-ActionButton '1. Comprobar requisitos' 'Comprueba Docker, Ollama y el espacio en disco. No modifica nada.' {
    Invoke-Guarded 'Comprobando requisitos...' { Test-Requirements }
  })
  [void](New-ActionButton '2. Instalar' 'Prepara la configuración local, el motor de IA y la aplicación. La primera vez tarda varios minutos.' {
    Invoke-Guarded 'Instalando PlumA (la primera vez puede tardar bastante)...' {
      Invoke-InstallOrStart 'pluma-install-core.bat' 'PlumA se ha instalado y está en marcha.'
    }
  })
  $script:BtnStart = New-ActionButton 'Iniciar' 'Arranca PlumA ya instalada, sin reconstruir ni descargar nada.' {
    Invoke-Guarded 'Iniciando PlumA...' {
      Invoke-InstallOrStart 'pluma-start-core.bat' 'PlumA está en marcha.'
    }
  }
  $script:BtnOpen = New-ActionButton 'Abrir PlumA' 'Abre la interfaz en el navegador.' {
    Invoke-Guarded 'Abriendo PlumA...' { Open-PlumA }
  }
  $script:BtnStop = New-ActionButton 'Detener' 'Detiene PlumA (y Ollama si corre dentro de Docker). Los datos se conservan.' {
    Invoke-Guarded 'Deteniendo PlumA...' { Invoke-Stop }
  }
  [void](New-ActionButton 'Diagnóstico' 'Muestra en el registro el estado de Docker, contenedores y servicio.' {
    Invoke-Guarded 'Ejecutando diagnóstico...' { [void](Invoke-CoreScript 'pluma-diagnostico.bat') }
  })
  [void](New-ActionButton 'Ver registro' 'Abre el registro completo del panel en el Bloc de notas.' {
    Invoke-Guarded 'Abriendo el registro...' { Open-LogFile }
  })
  $script:BtnUninstall = New-ActionButton 'Desinstalar…' 'Elimina contenedores, volúmenes e imagen de PlumA. Pide confirmación.' {
    Invoke-Guarded 'Desinstalando PlumA...' { Invoke-Uninstall }
  }

  $form.Add_FormClosing({
    param($sender, $e)
    if ($script:Busy) {
      $answer = Show-Message "Hay una operación en curso. ¿Cancelarla y cerrar el panel?`r`n`r`nPlumA puede quedar a medio instalar; bastará con volver a pulsar «Instalar»." 'Warning' -YesNo
      if ($answer) {
        Write-PanelLog 'Operación cancelada al cerrar el panel.'
        $script:Closing = $true
        Stop-CurrentProcess
      } else {
        $e.Cancel = $true
      }
    }
  })

  $script:Timer = New-Object System.Windows.Forms.Timer
  $script:Timer.Interval = 10000
  $script:Timer.Add_Tick({ Update-State })

  $form.Add_Shown({
    Write-PanelLog "Panel iniciado. Carpeta de PlumA: $($script:RepoRoot)"
    Write-PanelLog "Registro completo: $($script:LogFile)"
    Update-State
    $script:Timer.Start()
  })

  [void]$form.ShowDialog()
  $script:Timer.Stop()
  $script:Closing = $true
}

# -----------------------------------------------------------------------------
# Arranque (una sola instancia por usuario)
# -----------------------------------------------------------------------------
$mutex = $null
$ownsMutex = $false
try {
  Initialize-PanelFiles
  Initialize-Paths
  $mutex = New-Object System.Threading.Mutex($false, 'Local\PlumA-Panel')
  try {
    $ownsMutex = $mutex.WaitOne(0)
  } catch [System.Threading.AbandonedMutexException] {
    $ownsMutex = $true
  }
  if (-not $ownsMutex) {
    Show-FatalMessage 'El panel de PlumA ya está abierto.'
    exit 0
  }
  Show-Panel
} catch {
  $message = "El panel de PlumA se ha cerrado por un error inesperado:`r`n`r`n" +
    $_.Exception.Message + "`r`n`r`nRegistro: " + $script:LogFile
  Write-FileLog $message
  Show-FatalMessage $message
  exit 1
} finally {
  if ($ownsMutex -and $null -ne $mutex) { $mutex.ReleaseMutex() }
}
