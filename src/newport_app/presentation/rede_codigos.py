"""Códigos abreviados de cobertura hospitalar para a aba rede."""

from __future__ import annotations

from newport_app.presentation.rede_especialidade import tokens_especialidade_celula

_ORDEM = ("HGER", "HD", "MAT", "PSGER")
_ABREV = {"HGER": "H", "HD": "HD", "MAT": "M", "PSGER": "PS"}


_SIGLA_ZONA: dict[str, str] = {
    "ZONA NORTE": "ZN",
    "ZONA OESTE": "ZO",
    "ZONA SUL": "ZS",
    "ZONA LESTE": "ZL",
    "CENTRO": "ZC",
}


def sigla_zona_capital(zona: str) -> str:
    """Sigla de duas letras (ZN, ZO, ZS…) para prefixo na linha — SP/Rio."""
    from newport_app.siscor_importer.normalize import normalizar_cabecalho

    if not (zona or "").strip():
        return ""
    return _SIGLA_ZONA.get(normalizar_cabecalho(zona), "")


def formatar_cobertura_abreviada(valor: str | None, *, coberto: bool) -> str:
    """H, HD, M, PS — só tokens presentes na célula; vazio se não coberto."""
    if not coberto:
        return ""
    tokens = tokens_especialidade_celula(valor)
    if not tokens:
        return ""
    partes = [_ABREV[c] for c in _ORDEM if c in tokens]
    return " ".join(partes)
