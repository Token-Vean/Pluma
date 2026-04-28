# PlumA v0.4.14-alpha

Release de corrección del instalador visual Windows.

## Cambios principales

- Corrección del cierre inesperado del panel gráfico al pulsar **Comprobar**.
- Sustitución de lectura asíncrona de stdout/stderr por ejecución oculta con log intermedio.
- Registro persistente en `%LOCALAPPDATA%\PlumA\installer\installer.log`.
- Nuevo botón **Ver log** en el panel gráfico.
- Lanzador `.vbs` reforzado para usar PowerShell de 64 bits cuando esté disponible.
- Se mantiene el modo local bloqueado y la estructura offline-ready introducidos en versiones anteriores.

## Uso recomendado en Windows

Ejecutar con doble clic:

```text
00_INSTALAR_PLUMA_WINDOWS_SIN_CONSOLA.vbs
```

Los scripts `.bat` quedan reservados para uso avanzado.
