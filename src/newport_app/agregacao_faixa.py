"""Agregação de valores por faixa etária — invariante compartilhado."""

from __future__ import annotations

_ALERTA_HETEROGENEO = (
    "Valores individuais diferentes — total observado exibido."
)


def agregar_valores_faixa(
    valores: list[int],
) -> tuple[int | None, int | None, str | None]:
    """Retorna (unitário representativo | None, total, alerta | None).

    O total é sempre a soma de todos os valores conhecidos. A homogeneidade
    decide apenas se um valor unitário representativo pode ser exibido.
    """
    if not valores:
        return None, None, None
    total = sum(valores)
    unicos = set(valores)
    if len(unicos) == 1:
        return next(iter(unicos)), total, None
    return None, total, _ALERTA_HETEROGENEO
