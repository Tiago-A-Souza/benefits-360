"""Formatação monetária para renderers — centavos inteiros apenas aqui."""

from __future__ import annotations


def formatar_reais(centavos: int | None) -> str:
    if centavos is None:
        return "—"
    sinal = "-" if centavos < 0 else ""
    valor = abs(centavos)
    reais, cents = divmod(valor, 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"
