Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

try {
  Add-Type -AssemblyName System.Windows.Forms
  Add-Type -AssemblyName System.Drawing
} catch {
  try {
    $ws = New-Object -ComObject WScript.Shell
    $ws.Popup("No se ha podido cargar Windows Forms para abrir el panel grafico de PlumA.`r`n`r`n" + $_.Exception.Message, 0, "PlumA", 16) | Out-Null
  } catch {}
  exit 1
}

$Global:PlumALogDir = Join-Path $env:LOCALAPPDATA "PlumA\installer"
$Global:PlumALogFile = Join-Path $Global:PlumALogDir "installer.log"
New-Item -ItemType Directory -Force -Path $Global:PlumALogDir | Out-Null

function Add-FileLog([string]$text) {
  $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
  Add-Content -LiteralPath $Global:PlumALogFile -Encoding UTF8 -Value "[$ts] $text"
}

function Main {
  $scriptRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
  $root = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $scriptRoot))
  $tools = Join-Path $root "pluma\tools\windows"
  $plumaDir = Join-Path $root "pluma"
  $offlineDir = Join-Path $root "offline"

  if (!(Test-Path -LiteralPath $plumaDir)) { throw "No se encuentra la carpeta principal de PlumA: $plumaDir" }
  if (!(Test-Path -LiteralPath $tools)) { throw "No se encuentra la carpeta de herramientas Windows: $tools" }

  $script:DockerExe = $null
  $script:DockerBin = $null
  $script:LastOpenAt = [DateTime]::MinValue

  function New-Font([int]$size, [string]$style = "Regular") {
    $fs = [System.Drawing.FontStyle]::Regular
    if ($style -eq "Bold") { $fs = [System.Drawing.FontStyle]::Bold }
    if ($style -eq "Italic") { $fs = [System.Drawing.FontStyle]::Italic }
    return New-Object System.Drawing.Font("Segoe UI", $size, $fs)
  }

  function Unique-Strings($items) {
    $seen = @{}
    $out = New-Object System.Collections.ArrayList
    foreach ($item in $items) {
      if ([string]::IsNullOrWhiteSpace($item)) { continue }
      $key = $item.ToLowerInvariant()
      if (-not $seen.ContainsKey($key)) { $seen[$key] = $true; [void]$out.Add($item) }
    }
    return $out
  }

  function Find-DockerExe {
    $candidates = New-Object System.Collections.ArrayList
    try {
      $cmd = Get-Command docker.exe -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($cmd -and $cmd.Source) { [void]$candidates.Add($cmd.Source) }
    } catch {}
    [void]$candidates.Add((Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"))
    if (${env:ProgramFiles(x86)}) { [void]$candidates.Add((Join-Path ${env:ProgramFiles(x86)} "Docker\Docker\resources\bin\docker.exe")) }
    [void]$candidates.Add((Join-Path $env:LOCALAPPDATA "Docker\Docker\resources\bin\docker.exe"))
    $candidates = Unique-Strings $candidates
    foreach ($candidate in $candidates) {
      if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return $null
  }

  function Find-DockerDesktopExe {
    $candidates = @(
      (Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"),
      (Join-Path $env:LOCALAPPDATA "Docker\Docker\Docker Desktop.exe")
    )
    foreach ($candidate in $candidates) {
      if (Test-Path -LiteralPath $candidate) { return (Resolve-Path -LiteralPath $candidate).Path }
    }
    return $null
  }

  function Find-PowerShellExe {
    $candidate = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
    if (Test-Path -LiteralPath $candidate) { return $candidate }
    return "powershell.exe"
  }

  $form = New-Object System.Windows.Forms.Form
  $form.Text = "PlumA - instalador local"
  $form.Size = New-Object System.Drawing.Size(900, 665)
  $form.MinimumSize = New-Object System.Drawing.Size(900, 665)
  $form.StartPosition = "CenterScreen"
  $form.BackColor = [System.Drawing.Color]::FromArgb(248,249,251)
  $form.Font = New-Font 9

  $iconFile = Join-Path $plumaDir "frontend\static\img\favicon.ico"
  if (Test-Path -LiteralPath $iconFile) {
    try { $form.Icon = New-Object System.Drawing.Icon($iconFile) } catch {}
  }

  $logoFile = Join-Path $plumaDir "frontend\static\img\pluma-logo-full.png"
  if (Test-Path -LiteralPath $logoFile) {
    $picture = New-Object System.Windows.Forms.PictureBox
    $picture.Location = New-Object System.Drawing.Point(26,18)
    $picture.Size = New-Object System.Drawing.Size(230,58)
    $picture.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
    try { $picture.Image = [System.Drawing.Image]::FromFile($logoFile) } catch {}
    $form.Controls.Add($picture)
  } else {
    $title = New-Object System.Windows.Forms.Label
    $title.Text = "PlumA"
    $title.Font = New-Font 24 "Bold"
    $title.AutoSize = $true
    $title.Location = New-Object System.Drawing.Point(26,18)
    $form.Controls.Add($title)
  }

  $subtitle = New-Object System.Windows.Forms.Label
  $subtitle.Text = "Instalador grafico - modo local bloqueado - sin consola - v0.4.16-alpha"
  $subtitle.Font = New-Font 10
  $subtitle.AutoSize = $true
  $subtitle.Location = New-Object System.Drawing.Point(30,82)
  $form.Controls.Add($subtitle)

  $badge = New-Object System.Windows.Forms.Label
  $badge.Text = "LOCAL STRICT"
  $badge.Font = New-Font 9 "Bold"
  $badge.AutoSize = $true
  $badge.ForeColor = [System.Drawing.Color]::FromArgb(28,92,56)
  $badge.BackColor = [System.Drawing.Color]::FromArgb(222,245,232)
  $badge.Padding = New-Object System.Windows.Forms.Padding(10,5,10,5)
  $badge.Location = New-Object System.Drawing.Point(720,30)
  $form.Controls.Add($badge)

  $intro = New-Object System.Windows.Forms.Label
  $intro.Text = "Use este panel para comprobar requisitos, instalar, iniciar, abrir, diagnosticar o retirar PlumA. Los comandos se ejecutan ocultos y el registro queda guardado localmente. PlumA solo se abre cuando el servicio HTTP responde; esto evita ventanas duplicadas o paginas en blanco."
  $intro.AutoSize = $false
  $intro.Size = New-Object System.Drawing.Size(820,50)
  $intro.Location = New-Object System.Drawing.Point(30,108)
  $intro.ForeColor = [System.Drawing.Color]::FromArgb(60,65,72)
  $form.Controls.Add($intro)

  $status = New-Object System.Windows.Forms.Label
  $status.Text = "Listo. Selecciona una accion."
  $status.AutoSize = $false
  $status.Size = New-Object System.Drawing.Size(820,24)
  $status.Location = New-Object System.Drawing.Point(30,165)
  $status.ForeColor = [System.Drawing.Color]::FromArgb(48,52,58)
  $form.Controls.Add($status)

  $progress = New-Object System.Windows.Forms.ProgressBar
  $progress.Location = New-Object System.Drawing.Point(30,193)
  $progress.Size = New-Object System.Drawing.Size(820,18)
  $progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
  $progress.Minimum = 0
  $progress.Maximum = 100
  $progress.Value = 0
  $form.Controls.Add($progress)

  $log = New-Object System.Windows.Forms.TextBox
  $log.Multiline = $true
  $log.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
  $log.ReadOnly = $true
  $log.BackColor = [System.Drawing.Color]::White
  $log.BorderStyle = [System.Windows.Forms.BorderStyle]::FixedSingle
  $log.Location = New-Object System.Drawing.Point(30,227)
  $log.Size = New-Object System.Drawing.Size(820,300)
  $log.Font = New-Object System.Drawing.Font("Consolas", 9)
  $form.Controls.Add($log)

  $buttons = New-Object System.Collections.ArrayList

  function Write-Log([string]$text) {
    if ($null -eq $text) { return }
    $ts = Get-Date -Format "HH:mm:ss"
    Add-FileLog $text
    $log.AppendText("[$ts] $text`r`n")
    $log.SelectionStart = $log.Text.Length
    $log.ScrollToCaret()
    [System.Windows.Forms.Application]::DoEvents()
  }

  function Set-UiBusy([bool]$busy, [string]$message) {
    $status.Text = $message
    if ($busy) {
      $progress.Style = [System.Windows.Forms.ProgressBarStyle]::Marquee
      $progress.MarqueeAnimationSpeed = 30
    } else {
      $progress.Style = [System.Windows.Forms.ProgressBarStyle]::Blocks
      $progress.MarqueeAnimationSpeed = 0
      $progress.Value = 0
    }
    foreach ($c in $buttons) { $c.Enabled = -not $busy }
    [System.Windows.Forms.Application]::DoEvents()
  }

  function Q([string]$s) { return '"' + ($s -replace '"','\"') + '"' }

  function Get-ExtraPath {
    $paths = New-Object System.Collections.ArrayList
    if ($script:DockerBin) { [void]$paths.Add($script:DockerBin) }
    $common = @(
      (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin"),
      (Join-Path $env:LOCALAPPDATA "Docker\Docker\resources\bin")
    )
    foreach ($p in $common) { if (Test-Path -LiteralPath $p) { [void]$paths.Add($p) } }
    $paths = Unique-Strings $paths
    return ($paths -join ';')
  }

  function Write-CmdFile([string]$commandLine, [string]$workingDirectory, [string]$commandLog, [string]$extraPath) {
    $cmdFile = Join-Path $Global:PlumALogDir ("run-" + [Guid]::NewGuid().ToString("N") + ".cmd")
    $lines = New-Object System.Collections.ArrayList
    [void]$lines.Add("@echo off")
    [void]$lines.Add("setlocal EnableExtensions")
    [void]$lines.Add("chcp 65001 > nul")
    if ($extraPath -and $extraPath.Trim().Length -gt 0) { [void]$lines.Add("set ""PATH=$extraPath;%PATH%""") }
    [void]$lines.Add("cd /d " + (Q $workingDirectory))
    [void]$lines.Add("echo ==== PlumA command started %DATE% %TIME% ====>>" + (Q $commandLog))
    [void]$lines.Add($commandLine + " 1>>" + (Q $commandLog) + " 2>&1")
    [void]$lines.Add("set EXITCODE=%ERRORLEVEL%")
    [void]$lines.Add("echo ==== PlumA command finished with code %EXITCODE% ====>>" + (Q $commandLog))
    [void]$lines.Add("exit /b %EXITCODE%")
    Set-Content -LiteralPath $cmdFile -Encoding ASCII -Value $lines
    return $cmdFile
  }

  function Append-NewLog([string]$commandLog, [ref]$lastLength) {
    if (!(Test-Path -LiteralPath $commandLog)) { return }
    $fs = $null
    try {
      $fs = [System.IO.File]::Open($commandLog, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
      if ($fs.Length -le $lastLength.Value) { return }
      $fs.Seek($lastLength.Value, [System.IO.SeekOrigin]::Begin) | Out-Null
      $reader = New-Object System.IO.StreamReader($fs, [System.Text.Encoding]::UTF8, $true)
      $newText = $reader.ReadToEnd()
      $lastLength.Value = $fs.Length
      $reader.Close()
      if ($newText -and $newText.Trim().Length -gt 0) {
        foreach ($line in ($newText -split "`r?`n")) {
          if ($line.Trim().Length -gt 0) { Write-Log $line }
        }
      }
    } catch {
      # Evita cerrar la interfaz por una lectura temporal fallida.
    } finally {
      if ($fs) { $fs.Close() }
    }
  }

  function Invoke-Hidden([string]$commandLine, [string]$workingDirectory = $plumaDir) {
    Write-Log "> $commandLine"
    $commandLog = Join-Path $Global:PlumALogDir ("command-" + [Guid]::NewGuid().ToString("N") + ".log")
    $cmdFile = Write-CmdFile $commandLine $workingDirectory $commandLog (Get-ExtraPath)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = "/d /c " + (Q $cmdFile)
    $psi.WorkingDirectory = $workingDirectory
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    $last = 0L
    [void]$p.Start()
    while (-not $p.HasExited) {
      Append-NewLog $commandLog ([ref]$last)
      Start-Sleep -Milliseconds 250
      [System.Windows.Forms.Application]::DoEvents()
    }
    $p.WaitForExit()
    Append-NewLog $commandLog ([ref]$last)
    Write-Log "Codigo de salida: $($p.ExitCode)"
    try { Remove-Item -LiteralPath $cmdFile -Force -ErrorAction SilentlyContinue } catch {}
    return $p.ExitCode
  }

  function Invoke-Docker([string]$dockerArgs) {
    if (-not $script:DockerExe) { $script:DockerExe = Find-DockerExe }
    if (-not $script:DockerExe) { return 9009 }
    $script:DockerBin = Split-Path -Parent $script:DockerExe
    return Invoke-Hidden ((Q $script:DockerExe) + " " + $dockerArgs) $plumaDir
  }

  function Wait-DockerEngine([int]$seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
      $code = Invoke-Docker "info"
      if ($code -eq 0) { return $true }
      Start-Sleep -Seconds 5
      [System.Windows.Forms.Application]::DoEvents()
    }
    return $false
  }

  function Ensure-DockerAvailable([System.Collections.Generic.List[string]]$failures) {
    $script:DockerExe = Find-DockerExe
    if (-not $script:DockerExe) {
      $failures.Add("No se ha encontrado docker.exe. Instala Docker Desktop o revisa la ruta de instalacion.")
      return
    }
    $script:DockerBin = Split-Path -Parent $script:DockerExe
    Write-Log "Docker CLI detectado en: $script:DockerExe"

    $version = Invoke-Docker "--version"
    if ($version -ne 0) {
      $failures.Add("Docker existe, pero no se puede ejecutar docker --version.")
      return
    }

    $engine = Invoke-Docker "info"
    if ($engine -ne 0) {
      $desktop = Find-DockerDesktopExe
      if ($desktop) {
        Write-Log "Docker Desktop detectado pero Engine no responde. Intentando abrir Docker Desktop..."
        try { Start-Process -FilePath $desktop -WindowStyle Minimized | Out-Null } catch { Write-Log $_.Exception.Message }
        $status.Text = "Abriendo Docker Desktop y esperando a que arranque..."
        [System.Windows.Forms.Application]::DoEvents()
        if (-not (Wait-DockerEngine 75)) {
          $failures.Add("Docker esta instalado, pero Docker Engine no responde. Abre Docker Desktop, espera a que finalice el arranque y vuelve a pulsar Comprobar.")
        }
      } else {
        $failures.Add("Docker CLI existe, pero Docker Desktop/Engine no responde.")
      }
    }

    $compose = Invoke-Docker "compose version"
    if ($compose -ne 0) {
      $failures.Add("Docker Compose v2 no esta disponible desde Docker CLI. Actualiza Docker Desktop.")
    }
  }

  function Test-PlumAReady([int]$timeoutSec = 4) {
    try {
      $req = [System.Net.WebRequest]::Create("http://127.0.0.1:8082/api/estado")
      $req.Timeout = $timeoutSec * 1000
      $req.Method = "GET"
      $resp = $req.GetResponse()
      try {
        $code = [int]$resp.StatusCode
        if ($code -eq 200) { return $true }
      } finally {
        $resp.Close()
      }
    } catch {
      Write-Log ("PlumA aun no responde: " + $_.Exception.Message)
    }
    return $false
  }

  function Wait-PlumAReady([int]$seconds = 90) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
      if (Test-PlumAReady 3) { return $true }
      Start-Sleep -Seconds 3
      [System.Windows.Forms.Application]::DoEvents()
    }
    return $false
  }

  function Run-Bat([string]$batName, [string]$label, [bool]$showSuccessMessage = $true) {
    try {
      Set-UiBusy $true $label
      $bat = Join-Path $tools $batName
      if (!(Test-Path -LiteralPath $bat)) { throw "No se encuentra $bat" }
      $script:DockerExe = Find-DockerExe
      if ($script:DockerExe) { $script:DockerBin = Split-Path -Parent $script:DockerExe }
      $code = Invoke-Hidden ("call " + (Q $bat)) $plumaDir
      if ($code -eq 0) {
        $status.Text = "Operacion finalizada correctamente."
        if ($showSuccessMessage) {
          [System.Windows.Forms.MessageBox]::Show("Operacion finalizada correctamente.", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
        }
      } else {
        $status.Text = "La operacion termino con errores. Codigo: $code"
        [System.Windows.Forms.MessageBox]::Show("La operacion termino con errores. Revisa el registro del panel.`r`n`r`nRegistro: $Global:PlumALogFile", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
      }
      return $code
    } catch {
      Write-Log $_.Exception.Message
      [System.Windows.Forms.MessageBox]::Show($_.Exception.Message + "`r`n`r`nRegistro: $Global:PlumALogFile", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
      return 1
    } finally {
      Set-UiBusy $false "Listo. Selecciona una accion."
    }
  }

  function Install-OrStart {
    $code = Run-Bat "pluma-install-core.bat" "Instalando o iniciando PlumA. La primera vez puede tardar mientras Docker construye la imagen o descarga componentes..." $false
    if ($code -ne 0) { return }
    Set-UiBusy $true "Comprobando que PlumA responde antes de abrir el navegador..."
    $ready = Wait-PlumAReady 30
    Set-UiBusy $false "Listo. Selecciona una accion."
    if ($ready) {
      [System.Windows.Forms.MessageBox]::Show("PlumA esta iniciado y responde correctamente. Se abrira ahora en el navegador.", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
      Open-PlumA $true
    } else {
      [System.Windows.Forms.MessageBox]::Show("Docker ha terminado la orden, pero PlumA no responde todavia en http://localhost:8082.`r`n`r`nPulsa Diagnostico o revisa el registro del panel.", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
    }
  }

  function Check-Requirements {
    try {
      Set-UiBusy $true "Comprobando requisitos..."
      $failures = New-Object System.Collections.Generic.List[string]

      Write-Log "Comprobando Docker Desktop / Docker CLI..."
      Ensure-DockerAvailable $failures

      Write-Log "Aplicando/verificando configuracion local bloqueada..."
      $ps1 = Join-Path $tools "enforce-local-config.ps1"
      if (!(Test-Path -LiteralPath $ps1)) { throw "No se encuentra $ps1" }
      $cfg = Invoke-Hidden ((Q (Find-PowerShellExe)) + " -NoProfile -ExecutionPolicy Bypass -File " + (Q $ps1)) $plumaDir
      if ($cfg -ne 0) { $failures.Add("No se ha podido sanear la configuracion local de PlumA.") }

      if (Test-Path -LiteralPath (Join-Path $offlineDir "images")) { Write-Log "Carpeta offline/images preparada." }
      if (Test-Path -LiteralPath (Join-Path $offlineDir "models")) { Write-Log "Carpeta offline/models preparada." }
      try {
        $envFile = Join-Path $plumaDir ".env"
        $envText = if (Test-Path -LiteralPath $envFile) { Get-Content -LiteralPath $envFile -Raw -Encoding UTF8 } else { "" }
        if ($envText -match "(?m)^PLUMA_OLLAMA_MODE=host") {
          Write-Log "Ollama local del usuario detectado: PlumA usara host.docker.internal para evitar descargar de nuevo el modelo."
        } else {
          Write-Log "PlumA usara Ollama Docker interno. Si falta el modelo, se descargara dentro del volumen Docker."
        }
      } catch {
        Write-Log "No se pudo determinar el modo de Ollama; se revisara al instalar."
      }

      if ($failures.Count -eq 0) {
        $status.Text = "Requisitos comprobados correctamente."
        [System.Windows.Forms.MessageBox]::Show("Requisitos principales comprobados. Docker, Docker Engine y Docker Compose estan disponibles. La configuracion local ha sido saneada.", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Information) | Out-Null
      } else {
        $status.Text = "Hay requisitos pendientes. Revisa el detalle."
        $message = "Alguna comprobacion ha fallado:`r`n`r`n - " + ($failures -join "`r`n - ") + "`r`n`r`nRegistro: $Global:PlumALogFile"
        [System.Windows.Forms.MessageBox]::Show($message, "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
      }
    } catch {
      Write-Log $_.Exception.Message
      [System.Windows.Forms.MessageBox]::Show($_.Exception.Message + "`r`n`r`nRegistro: $Global:PlumALogFile", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    } finally {
      Set-UiBusy $false "Listo. Selecciona una accion."
    }
  }

  function Open-PlumA([bool]$force = $false) {
    try {
      if (-not (Test-PlumAReady 4)) {
        [System.Windows.Forms.MessageBox]::Show("PlumA aun no responde en http://localhost:8082.`r`n`r`nPulsa '2. Instalar / iniciar' o ejecuta 'Diagnostico' para ver el estado de los contenedores.", "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Warning) | Out-Null
        return
      }
      $now = Get-Date
      if ((-not $force) -and (($now - $script:LastOpenAt).TotalSeconds -lt 5)) {
        Write-Log "Apertura omitida para evitar duplicar ventanas del navegador."
        return
      }
      $script:LastOpenAt = $now
      Start-Process "http://localhost:8082"
      Write-Log "Abriendo http://localhost:8082"
    }
    catch { Write-Log $_.Exception.Message }
  }

  function Open-LogFile {
    try {
      if (!(Test-Path -LiteralPath $Global:PlumALogFile)) { Add-FileLog "Apertura manual del log." }
      Start-Process "notepad.exe" $Global:PlumALogFile
    } catch {
      [System.Windows.Forms.MessageBox]::Show($_.Exception.Message, "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
    }
  }

  function Add-Button($text, $x, $y, $w, $handler) {
    $b = New-Object System.Windows.Forms.Button
    $b.Text = $text
    $b.Location = New-Object System.Drawing.Point($x,$y)
    $b.Size = New-Object System.Drawing.Size($w,38)
    $b.Add_Click($handler)
    $form.Controls.Add($b)
    [void]$buttons.Add($b)
    return $b
  }

  Add-Button "1. Comprobar" 30 548 125 { Check-Requirements } | Out-Null
  Add-Button "2. Instalar / iniciar" 165 548 155 { Install-OrStart } | Out-Null
  Add-Button "Abrir PlumA" 332 548 112 { Open-PlumA } | Out-Null
  Add-Button "Diagnostico" 456 548 110 { Run-Bat "pluma-diagnostico.bat" "Ejecutando diagnostico..." } | Out-Null
  Add-Button "Detener" 578 548 88 { Run-Bat "pluma-stop-core.bat" "Deteniendo PlumA..." } | Out-Null
  Add-Button "Ver log" 678 548 80 { Open-LogFile } | Out-Null
  Add-Button "Desinstalar" 770 548 90 {
    $r = [System.Windows.Forms.MessageBox]::Show("Esto detendra PlumA y eliminara volumenes Docker asociados. Continuar?", "PlumA", [System.Windows.Forms.MessageBoxButtons]::YesNo, [System.Windows.Forms.MessageBoxIcon]::Warning)
    if ($r -eq [System.Windows.Forms.DialogResult]::Yes) { Run-Bat "pluma-uninstall-core.bat" "Desinstalando PlumA..." }
  } | Out-Null

  Write-Log "Panel grafico iniciado. Ruta: $root"
  Write-Log "Registro persistente: $Global:PlumALogFile"
  Write-Log "Modo local bloqueado: no se permite Ollama remoto ni publicacion en red."
  Write-Log "Offline ready: puede colocar imagenes Docker en offline/images y modelos GGUF en offline/models."
  [void]$form.ShowDialog()
}

try {
  Main
} catch {
  $msg = "El panel grafico de PlumA se ha cerrado por un error no controlado:`r`n`r`n" + $_.Exception.Message + "`r`n`r`nRegistro: " + $Global:PlumALogFile
  Add-FileLog $msg
  [System.Windows.Forms.MessageBox]::Show($msg, "PlumA", [System.Windows.Forms.MessageBoxButtons]::OK, [System.Windows.Forms.MessageBoxIcon]::Error) | Out-Null
  exit 1
}
