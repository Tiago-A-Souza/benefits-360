"""Conversão monetária com Decimal — nunca float."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def valor_para_centavos(valor: object) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    try:
        if isinstance(valor, Decimal):
            dec = valor
        elif isinstance(valor, int):
            dec = Decimal(valor)
        elif isinstance(valor, float):
            dec = Decimal(str(valor))
        elif isinstance(valor, str):
            texto = valor.strip().replace(".", "").replace(",", ".")
            if not texto:
                return None
            dec = Decimal(texto)
        else:
            dec = Decimal(str(valor))
        centavos = int((dec * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return centavos
    except (InvalidOperation, ValueError, ArithmeticError):
        return None
