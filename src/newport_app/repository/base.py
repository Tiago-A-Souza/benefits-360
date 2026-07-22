"""Contrato de persistência de rascunhos."""

from __future__ import annotations

from typing import Protocol

from newport_app.models.draft import RascunhoEstudo


class StudyRepository(Protocol):
    def obter_rascunho(self, estudo_id: str) -> RascunhoEstudo | None: ...

    def salvar_rascunho(self, rascunho: RascunhoEstudo) -> None: ...

    def listar_ids(self) -> list[str]: ...
