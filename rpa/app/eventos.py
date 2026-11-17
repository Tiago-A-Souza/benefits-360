"""Barramento de eventos: o robô (numa thread) publica, a tela (via SSE) recebe ao vivo."""
from __future__ import annotations

import asyncio
import threading


class Barramento:
    def __init__(self):
        self._filas: set[asyncio.Queue] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()

    def ligar(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def assinar(self) -> asyncio.Queue:
        fila: asyncio.Queue = asyncio.Queue(maxsize=2000)
        with self._lock:
            self._filas.add(fila)
        return fila

    def cancelar(self, fila: asyncio.Queue) -> None:
        with self._lock:
            self._filas.discard(fila)

    def publicar(self, evento: dict) -> None:
        """Pode ser chamado de qualquer thread."""
        if self._loop is None or self._loop.is_closed():
            return
        with self._lock:
            filas = list(self._filas)
        for fila in filas:
            try:
                self._loop.call_soon_threadsafe(_por, fila, evento)
            except RuntimeError:   # loop encerrando
                pass


def _por(fila: asyncio.Queue, evento: dict) -> None:
    try:
        fila.put_nowait(evento)
    except asyncio.QueueFull:
        pass
