# Instalador Windows de PlumA con NSIS

Este directorio contiene la fuente del instalador gráfico de Windows.

## Objetivo

Crear un instalador `.exe` visual, sin ventanas de consola durante la instalación ordinaria, con:

- asistente de bienvenida;
- selección de carpeta;
- barra de progreso propia de NSIS;
- aplicación automática de configuración local bloqueada;
- accesos directos;
- desinstalador.

## Requisitos para compilar

- Windows 10/11.
- NSIS instalado.
- `makensis.exe` disponible en PATH.

## Compilación

Desde la carpeta raíz del paquete, ejecutar:

```bat
installer\windows\build-installer.bat
```

Salida esperada:

```text
installer\windows\nsis\PlumA-Setup-Windows-0.4.16-alpha.exe
```

## Nota importante

Este paquete incluye el **código fuente del instalador**, no el `.exe` ya compilado. El `.exe` debe compilarse en Windows con NSIS.

El instalador usa `nsExec` para ejecutar comprobaciones y scripts sin abrir ventanas de consola independientes.
