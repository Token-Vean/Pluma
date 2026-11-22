Option Explicit
' =============================================================================
' PlumA - instalar, iniciar y abrir PlumA desde un panel, sin consola.
' Doble clic para usarlo.
'
' Si Windows tiene VBScript desactivado, usa "ayuda\Abrir sin VBScript.bat".
' El panel esta en programa\panel\PlumAPanel.ps1.
' =============================================================================
Dim fso, shell, baseDir, ps1, psExe, cmd
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
baseDir = fso.GetParentFolderName(WScript.ScriptFullName)
ps1 = fso.BuildPath(baseDir, "programa\panel\PlumAPanel.ps1")
If Not fso.FileExists(ps1) Then
  MsgBox "No se encuentra el panel de PlumA:" & vbCrLf & ps1 & vbCrLf & vbCrLf & _
    "Descomprime el ZIP completo y abre este fichero desde la carpeta extraida.", vbCritical, "PlumA"
  WScript.Quit 1
End If
psExe = shell.ExpandEnvironmentStrings("%SystemRoot%") & "\System32\WindowsPowerShell\v1.0\powershell.exe"
If Not fso.FileExists(psExe) Then psExe = "powershell.exe"
cmd = """" & psExe & """ -NoProfile -STA -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & ps1 & """"
shell.Run cmd, 0, False
