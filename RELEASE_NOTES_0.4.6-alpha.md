# PlumA v0.4.14-alpha — corrección del panel visual Windows

Esta versión corrige dos problemas detectados en el instalador/panel gráfico de Windows:

1. El texto aparecía con caracteres corruptos en algunos equipos con Windows PowerShell 5.1.
2. La acción **Comprobar** podía informar fallo aunque Docker estuviera disponible, por un error en el script de saneamiento de configuración local.

## Cambios técnicos

- `PlumAInstaller.ps1` y `enforce-local-config.ps1` se guardan con UTF-8 BOM para compatibilidad con Windows PowerShell 5.1.
- `enforce-local-config.ps1` deja de usar `$global:content` y usa una variable de script controlada.
- La comprobación distingue entre Docker CLI, Docker Engine y Docker Compose.
- El mensaje de fallo del botón **Comprobar** ahora indica qué requisito concreto ha fallado.
- Se mantiene el modo local bloqueado y la estructura offline-ready.

## Entrada recomendada en Windows

Ejecutar con doble clic:

```text
00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs
```

No usar los `.bat` salvo diagnóstico avanzado.
