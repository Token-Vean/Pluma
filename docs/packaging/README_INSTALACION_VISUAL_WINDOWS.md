# Instalación visual de PlumA en Windows

La vía recomendada para Windows es:

```text
00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs
```

Este lanzador abre un panel gráfico WinForms sin mostrar consola. Internamente ejecuta los comandos necesarios con ventana oculta y muestra el avance dentro del propio panel.

## Por qué se han movido los `.bat`

Los archivos `.bat` siempre abren consola en Windows. Para evitar que el usuario no técnico vea una ventana negra de comandos, los `.bat` se han desplazado a:

```text
soporte/linea_comandos_windows/
```

La instalación ordinaria debe hacerse con el lanzador `.vbs` o, cuando se compile NSIS, con:

```text
PlumA-Setup-Windows-0.4.16-alpha.exe
```

## Compilar instalador NSIS

Instala NSIS y ejecuta:

```bat
installer\windows\build-installer.bat
```

La fuente está en:

```text
installer/windows/nsis/PlumA-Setup.nsi
```


Nota v0.4.16-alpha: el panel gráfico incluye registro persistente en `%LOCALAPPDATA%\PlumA\installer\installer.log` y botón **Ver log** para diagnóstico.
