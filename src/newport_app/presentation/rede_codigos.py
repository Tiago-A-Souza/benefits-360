"""Códigos abreviados de cobertura hospitalar para a aba rede."""

from __future__ import annotations

from newport_app.presentation.rede_especialidade import tokens_especialidade_celula

_ORDEM = ("HGER", "HD", "MAT", "PSGER")
_ABREV = {"HGER": "H", "HD": "HD", "MAT": "M", "PSGER": "PS"}


def formatar_cobertura_abreviada(valor: str | None, *, coberto: bool) -> str:
    """H, HD, M, PS — só tokens presentes na célula; vazio se não coberto."""
    if not coberto:
        return ""
    tokens = tokens_especialidade_celula(valor)
    if not tokens:
        return ""
    partes = [_ABREV[c] for c in _ORDEM if c in tokens]
    return " ".join(partes)
