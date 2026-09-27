"""Normalização de campos SISCOR."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime

from newport_app.models.draft import ParentescoRascunho
from newport_app.siscor_importer.constants import PARENTESCO_MAP, STATUS_ATIVO

# Espaços e separadores invisíveis comuns em export Excel/SISCOR (NBSP, etc.).
# Não incluir hífen suave aqui — removido à parte para não virar espaço.
_RE_ESPACOS_CABECALHO = re.compile(
    r"[\t\r\n\v\f"
    r"\u00A0"  # NBSP
    r"\u1680"  # ogham space
    r"\u2000-\u200B"  # en/em/thin/… + ZWSP
    r"\u2028\u2029"  # line/paragraph separator
    r"\u202F"  # narrow NBSP
    r"\u205F"  # medium mathematical space
    r"\u2060"  # word joiner
    r"\u3000"  # ideographic space
    r"\uFEFF"  # BOM / ZWNBSP
    r" ]+"
)


def normalizar_cabecalho(valor: object) -> str:
    """Canônico de cabeçalho: invisíveis → espaço, acento removido, caixa alta.

    Planilhas reais (Anistia/SISCOR) usam U+00A0 entre palavras
    (``CPF\\xa0TITULAR``). A defesa é aqui — não alias por cabeçalho.
    """
    if valor is None:
        return ""
    texto = str(valor).replace("\u00AD", "")  # soft hyphen
    texto = _RE_ESPACOS_CABECALHO.sub(" ", texto).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.upper()


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


def normalizar_uf(valor: object) -> str | None:
    """UF da planilha — só o que está na célula, sem inferência."""
    if valor is None or str(valor).strip() == "":
        return None
    texto = normalizar_cabecalho(str(valor).strip())
    if len(texto) == 2 and texto.isalpha():
        return texto
    return None


def normalizar_cidade(valor: object) -> str | None:
    """Município — normalização de cabeçalho/casing, sem dedução geográfica."""
    if valor is None or str(valor).strip() == "":
        return None
    texto = normalizar_cabecalho(str(valor).strip())
    return texto or None


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
