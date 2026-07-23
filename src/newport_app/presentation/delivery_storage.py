"""Contrato futuro para entrega hospedada — não implementado nesta etapa."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class DeliveryStorage(ABC):
    """Permite futuramente link autenticado ou temporário sem reescrever o renderer."""

    @abstractmethod
    def salvar(self, conteudo: bytes, *, nome_arquivo: str, estudo_id: str) -> str:
        """Persiste arquivo e retorna referência interna."""

    @abstractmethod
    def url_acesso(self, referencia: str) -> str | None:
        """Retorna URL se disponível; None no piloto local."""


class LocalFileDeliveryStorage(DeliveryStorage):
    def __init__(self, base_dir: Path) -> None:
        self._base = base_dir
        self._base.mkdir(parents=True, exist_ok=True)

    def salvar(self, conteudo: bytes, *, nome_arquivo: str, estudo_id: str) -> str:
        destino = self._base / estudo_id / nome_arquivo
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        return str(destino)

    def url_acesso(self, referencia: str) -> str | None:
        return None
