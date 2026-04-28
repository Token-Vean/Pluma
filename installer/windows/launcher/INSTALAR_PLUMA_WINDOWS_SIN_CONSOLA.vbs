Option Explicit
' PlumA - panel grafico Windows sin consola.
' Ejecutar con doble clic. No abra los .bat salvo uso avanzado.
Dim fso, shell, scriptDir, ps1, psExe, cmd, logDir, launchLog, localAppData
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = scriptDir & "\installer\windows\gui\PlumAInstaller.ps1"
If Not fso.FileExists(ps1) Then
  MsgBox "No se encuentra el panel grafico de PlumA:" & vbCrLf & ps1, vbCritical, "PlumA"
  WScript.Quit 1
End If
psExe = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
If Not fso.FileExists(psExe) Then
  psExe = "powershell.exe"
End If
localAppData = shell.ExpandEnvironmentStrings("%LOCALAPPDATA%")
logDir = localAppData & "\PlumA\installer"
If Not fso.FolderExists(logDir) Then
  On Error Resume Next
  If Not fso.FolderExists(localAppData & "\PlumA") Then
    fso.CreateFolder localAppData & "\PlumA"
  End If
  fso.CreateFolder logDir
  On Error GoTo 0
End If
launchLog = logDir & "\launcher.log"
cmd = Chr(34) & psExe & Chr(34) & " -STA -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File " & Chr(34) & ps1 & Chr(34) & " *> " & Chr(34) & launchLog & Chr(34)
shell.Run cmd, 0, False
