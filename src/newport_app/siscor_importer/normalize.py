"""Normalização de campos SISCOR."""

from __future__ import annotations

from datetime import date, datetime

from newport_app.models.draft import ParentescoRascunho
from newport_app.siscor_importer.constants import PARENTESCO_MAP, STATUS_ATIVO


def normalizar_cabecalho(valor: object) -> str:
    if valor is None:
        return ""
    return str(valor).strip().upper()


def normalizar_status(valor: object) -> tuple[str | None, str | None]:
    if valor is None or str(valor).strip() == "":
        return None, None
    texto = str(valor).strip()
    if texto.upper() == STATUS_ATIVO:
        return STATUS_ATIVO, STATUS_ATIVO
    return texto, None


def normalizar_parentesco(valor: object) -> tuple[str | None, ParentescoRascunho | None]:
    if valor is None or str(valor).strip() == "":
        return None, None
    texto = str(valor).strip().upper()
    mapeado = PARENTESCO_MAP.get(texto)
    if mapeado:
        return texto, ParentescoRascunho(mapeado)
    return texto, None


def parse_data_nascimento(valor: object) -> tuple[str | None, date | None, bool]:
    if valor is None or str(valor).strip() == "":
        return None, None, False
    if isinstance(valor, datetime):
        d = valor.date()
        return d.isoformat(), d, False
    if isinstance(valor, date):
        return valor.isoformat(), valor, False
    texto = str(valor).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            d = datetime.strptime(texto, fmt).date()
            return d.isoformat(), d, False
        except ValueError:
            continue
    return texto, None, True
