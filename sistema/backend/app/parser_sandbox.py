"""
Ejecución aislada de parsers documentales.

Los parsers de PDF/DOCX/imagen procesan entradas no confiables. Aunque el
router aplica límites estrictos, esta capa ejecuta el procesamiento en un
proceso hijo con timeout y, en sistemas POSIX, límites de memoria/CPU.

Objetivo: si un parser se bloquea, consume recursos excesivos o falla de forma
nativa, no tumba el proceso principal de FastAPI.
"""

from __future__ import annotations

import importlib
import multiprocessing as mp
import os
import time
import traceback
from dataclasses import dataclass
from typing import Any


@dataclass
class SandboxExecutionError(Exception):
    """Error devuelto por el proceso aislado."""

    exception_type: str
    message: str
    traceback_text: str | None = None

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"{self.exception_type}: {self.message}"


def _bool_env(nombre: str, defecto: bool) -> bool:
    valor = os.getenv(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def sandbox_activo() -> bool:
    """Permite desactivar el sandbox solo para depuración o tests controlados."""
    return _bool_env("USAR_SANDBOX_PARSERS", True)


def _aplicar_limites_recursos(timeout_segundos: int, memoria_mb: int) -> None:
    """Aplica límites POSIX cuando el módulo resource está disponible."""
    try:
        import resource
    except Exception:
        return

    if memoria_mb > 0:
        limite_memoria = memoria_mb * 1024 * 1024
        try:
            resource.setrlimit(resource.RLIMIT_AS, (limite_memoria, limite_memoria))
        except Exception:
            # Algunos entornos no permiten RLIMIT_AS. El timeout sigue activo.
            pass

    if timeout_segundos > 0:
        limite_cpu = max(1, int(timeout_segundos) + 5)
        try:
            resource.setrlimit(resource.RLIMIT_CPU, (limite_cpu, limite_cpu))
        except Exception:
            pass


def _resolver_funcion(ruta_funcion: str):
    modulo, nombre = ruta_funcion.split(":", 1)
    return getattr(importlib.import_module(modulo), nombre)


def _worker(
    ruta_funcion: str,
    args: tuple[Any, ...],
    kwargs: dict[str, Any],
    memoria_mb: int,
    timeout_segundos: int,
    salida,
) -> None:
    os.environ["_PLUMA_SANDBOX_CHILD"] = "1"
    _aplicar_limites_recursos(timeout_segundos=timeout_segundos, memoria_mb=memoria_mb)

    try:
        funcion = _resolver_funcion(ruta_funcion)
        resultado = funcion(*args, **kwargs)
        salida.send(("ok", resultado))
    except BaseException as exc:  # noqa: BLE001 - se serializa para el proceso padre
        try:
            salida.send((
                "error",
                {
                    "exception_type": exc.__class__.__name__,
                    "message": str(exc),
                    "traceback_text": traceback.format_exc(limit=20),
                },
            ))
        except Exception:
            pass
    finally:
        try:
            salida.close()
        except Exception:
            pass


def ejecutar_en_sandbox(
    ruta_funcion: str,
    *args: Any,
    timeout_segundos: int | None = None,
    memoria_mb: int | None = None,
    **kwargs: Any,
) -> Any:
    """
    Ejecuta una función top-level en un proceso hijo y devuelve su resultado.

    `ruta_funcion` debe tener forma ``"app.router:_procesar_impl"`` para evitar
    depender del pickle de objetos función entre plataformas.
    """
    timeout_segundos = timeout_segundos or int(os.getenv("SANDBOX_TIMEOUT_SEGUNDOS", "90"))
    memoria_mb = memoria_mb or int(os.getenv("SANDBOX_MEMORIA_MB", "1536"))
    metodo = os.getenv("SANDBOX_START_METHOD", "spawn")

    try:
        ctx = mp.get_context(metodo)
    except ValueError:
        ctx = mp.get_context("spawn")

    receptor, emisor = ctx.Pipe(duplex=False)
    proceso = ctx.Process(
        target=_worker,
        args=(ruta_funcion, args, kwargs, memoria_mb, timeout_segundos, emisor),
        daemon=True,
    )
    proceso.start()
    emisor.close()

    deadline = time.monotonic() + timeout_segundos
    estado = None
    payload = None

    while True:
        if receptor.poll(0.1):
            estado, payload = receptor.recv()
            proceso.join(5)
            break

        if not proceso.is_alive():
            codigo = proceso.exitcode
            receptor.close()
            raise SandboxExecutionError(
                "ProcesoParserFinalizado",
                f"El proceso de parser terminó sin devolver resultado (exitcode={codigo}).",
            )

        if time.monotonic() >= deadline:
            proceso.terminate()
            proceso.join(5)
            if proceso.is_alive():
                try:
                    proceso.kill()
                except AttributeError:
                    pass
                proceso.join(2)
            receptor.close()
            raise SandboxExecutionError(
                "Timeout",
                f"El procesamiento superó el límite de {timeout_segundos} segundos.",
            )

    receptor.close()

    if estado == "ok":
        return payload

    raise SandboxExecutionError(
        payload.get("exception_type", "ErrorParser"),
        payload.get("message", "Error no especificado en parser."),
        payload.get("traceback_text"),
    )
