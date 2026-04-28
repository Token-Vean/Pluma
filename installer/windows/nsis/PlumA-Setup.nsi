!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"

!define APPNAME "PlumA"
!define VERSION "0.4.16-alpha"
!define PUBLISHER "PlumA open-source project"

Name "${APPNAME} ${VERSION}"
OutFile "PlumA-Setup-Windows-${VERSION}.exe"
InstallDir "$LOCALAPPDATA\PlumA"
InstallDirRegKey HKCU "Software\PlumA" "InstallDir"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails nevershow
ShowUninstDetails nevershow
BrandingText "PlumA - instalación local bloqueada"

!define MUI_ABORTWARNING
!define MUI_ICON "..\..\..\pluma\frontend\static\img\favicon.ico"
!define MUI_UNICON "..\..\..\pluma\frontend\static\img\favicon.ico"
!define MUI_WELCOMEPAGE_TITLE "Instalador de PlumA"
!define MUI_WELCOMEPAGE_TEXT "Este asistente instalará PlumA en modo local bloqueado.$\r$\n$\r$\nLa aplicación se ejecutará en localhost y no permitirá configuración remota de Ollama ni exposición en red desde la configuración estándar."
!define MUI_FINISHPAGE_TITLE "PlumA se ha instalado"
!define MUI_FINISHPAGE_TEXT "La instalación ha finalizado. Puedes abrir PlumA desde el acceso directo del escritorio o desde el menú Inicio."
!define MUI_FINISHPAGE_RUN "$INSTDIR\pluma\tools\windows\pluma-open.bat"
!define MUI_FINISHPAGE_RUN_TEXT "Abrir PlumA ahora"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Spanish"

Function .onInit
  nsExec::ExecToStack 'cmd.exe /c if exist "%ProgramFiles%\Docker\Docker\resources\bin\docker.exe" set "PATH=%ProgramFiles%\Docker\Docker\resources\bin;%PATH%" & docker --version'
  Pop $0
  Pop $1
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "No se ha encontrado Docker. PlumA necesita Docker Desktop para ejecutarse.$\r$\n$\r$\nLa instalación puede continuar, pero deberás instalar y abrir Docker Desktop antes de iniciar PlumA."
  ${EndIf}
FunctionEnd

Section "Instalar PlumA" SEC01
  SetOutPath "$INSTDIR"
  File /r "..\..\..\*.*"
  WriteRegStr HKCU "Software\PlumA" "InstallDir" "$INSTDIR"

  DetailPrint "Aplicando configuración local bloqueada..."
  nsExec::ExecToLog 'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\pluma\tools\windows\enforce-local-config.ps1"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP|MB_OK "No se ha podido aplicar la configuración local bloqueada. La instalación se detendrá."
    Abort
  ${EndIf}

  CreateDirectory "$SMPROGRAMS\PlumA"
  CreateShortcut "$DESKTOP\PlumA.lnk" "$INSTDIR\pluma\tools\windows\pluma-open.bat"
  CreateShortcut "$SMPROGRAMS\PlumA\Abrir PlumA.lnk" "$INSTDIR\pluma\tools\windows\pluma-open.bat"
  CreateShortcut "$SMPROGRAMS\PlumA\Panel gráfico de PlumA.lnk" "$INSTDIR\00_ABRIR_PANEL_GRAFICO_WINDOWS.vbs"
  CreateShortcut "$SMPROGRAMS\PlumA\Iniciar PlumA.lnk" "$INSTDIR\pluma\tools\windows\pluma-install-core.bat"
  CreateShortcut "$SMPROGRAMS\PlumA\Detener PlumA.lnk" "$INSTDIR\pluma\tools\windows\pluma-stop-core.bat"
  CreateShortcut "$SMPROGRAMS\PlumA\Desinstalar PlumA.lnk" "$INSTDIR\Uninstall-PlumA.exe"

  WriteUninstaller "$INSTDIR\Uninstall-PlumA.exe"
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'cmd.exe /c "$INSTDIR\pluma\tools\windows\pluma-uninstall-core.bat"'
  Delete "$DESKTOP\PlumA.lnk"
  Delete "$SMPROGRAMS\PlumA\Abrir PlumA.lnk"
  Delete "$SMPROGRAMS\PlumA\Panel gráfico de PlumA.lnk"
  Delete "$SMPROGRAMS\PlumA\Iniciar PlumA.lnk"
  Delete "$SMPROGRAMS\PlumA\Detener PlumA.lnk"
  Delete "$SMPROGRAMS\PlumA\Desinstalar PlumA.lnk"
  RMDir "$SMPROGRAMS\PlumA"
  DeleteRegKey HKCU "Software\PlumA"
  RMDir /r "$INSTDIR"
SectionEnd
