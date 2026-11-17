"""Modelos da ponte Benefits ↔ RPA Cotações (sem troca de dados de estudo)."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RpaCotacoesEstadoResponse(BaseModel):
    ligado: bool
    url: str = Field(description="URL base da tela do RPA (iframe)")
    comando_subir: str | None = Field(
        default=None, description="Comando sugerido quando o robô não está no ar"
    )
    estado: dict[str, Any] | None = Field(
        default=None, description="Corpo de /api/estado do RPA, quando ligado"
    )