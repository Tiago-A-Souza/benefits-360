"""Normalização de campos SISCOR."""

from __future__ import annotations

import re
from datetime import date, datetime

from newport_app.models.draft import ParentescoRascunho
from newport_app.siscor_importer.constants import PARENTESCO_MAP, STATUS_ATIVO

_RE_ESPACOS_CABECALHO = re.compile(
    r"[\t\r\n\v\f\u00A0\u1680\u2000-\u200B\u202F\u205F\u3000 ]+"
)


def normalizar_cabecalho(valor: object) -> str:
    if valor is None:
        return ""
    texto = _RE_ESPACOS_CABECALHO.sub(" ", str(valor))
    return texto.strip().upper()


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


def normalizar_cpf(valor: object) -> str | None:
    if valor is None or str(valor).strip() == "":
        return None
    digitos = "".join(c for c in str(valor) if c.isdigit())
    if len(digitos) != 11:
        return None
    return digitos


def normalizar_matricula(valor: object) -> str | None:
    if valor is None or str(valor).strip() == "":
        return None
    texto = str(valor).strip()
    return texto


def normalizar_sexo(valor: object) -> tuple[str | None, str | None]:
    """Retorna (texto_original_upper, sexo_canonico) ou (texto, None) se ilegível."""
    if valor is None or str(valor).strip() == "":
        return None, None
    texto = str(valor).strip().upper()
    canonico_map = {
        "F": "feminino",
        "FEMININO": "feminino",
        "FEM": "feminino",
        "M": "masculino",
        "MASCULINO": "masculino",
        "MASC": "masculino",
    }
    canonico = canonico_map.get(texto)
    return texto, canonico


def normalizar_tipo_vida(valor: object) -> str | None:
    if valor is None or str(valor).strip() == "":
        return None
    return str(valor).strip().upper()


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
