"""Formatação para renderers — centavos e datas apenas aqui."""

from __future__ import annotations

from datetime import date, datetime


def formatar_reais(centavos: int | None) -> str:
    if centavos is None:
        return "—"
    sinal = "-" if centavos < 0 else ""
    valor = abs(centavos)
    reais, cents = divmod(valor, 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


def formatar_data_br(valor: date | datetime | str | None) -> str | None:
    """Exibe datas como dd/mm/aaaa; aceita ISO ou date/datetime."""
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    texto = str(valor).strip()
    if not texto:
        return None
    if len(texto) >= 10 and texto[4] == "-" and texto[7] == "-":
        try:
            return date.fromisoformat(texto[:10]).strftime("%d/%m/%Y")
        except ValueError:
            return texto
    return texto
