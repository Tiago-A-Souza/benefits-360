"""Critério de recorte geográfico da rede — configuração única."""

from __future__ import annotations

from enum import StrEnum

from newport_app.siscor_importer.normalize import normalizar_cabecalho


class ModoRecorteGeografico(StrEnum):
    """Trocar aqui altera o recorte em todo o pipeline (fase C)."""

    MUNICIPIO_E_CAPITAL_UF = "municipio_e_capital_uf"
    SOMENTE_MUNICIPIO = "somente_municipio"


# Critério provisório (Wesley ainda não confirmou) — uma linha para mudar o modo.
CRITERIO_RECORTE_GEOGRAFICO: ModoRecorteGeografico = ModoRecorteGeografico.MUNICIPIO_E_CAPITAL_UF

# Capitais dos estados (normalizadas como `normalizar_cabecalho`).
CAPITAIS_UF: dict[str, str] = {
    "AC": "RIO BRANCO",
    "AL": "MACEIO",
    "AM": "MANAUS",
    "AP": "MACAPA",
    "BA": "SALVADOR",
    "CE": "FORTALEZA",
    "DF": "BRASILIA",
    "ES": "VITORIA",
    "GO": "GOIANIA",
    "MA": "SAO LUIS",
    "MG": "BELO HORIZONTE",
    "MS": "CAMPO GRANDE",
    "MT": "CUIABA",
    "PA": "BELEM",
    "PB": "JOAO PESSOA",
    "PE": "RECIFE",
    "PI": "TERESINA",
    "PR": "CURITIBA",
    "RJ": "RIO DE JANEIRO",
    "RN": "NATAL",
    "RO": "PORTO VELHO",
    "RR": "BOA VISTA",
    "RS": "PORTO ALEGRE",
    "SC": "FLORIANOPOLIS",
    "SE": "ARACAJU",
    "SP": "SAO PAULO",
    "TO": "PALMAS",
}


def chave_municipio(uf: str, cidade: str) -> str:
    return f"{uf.strip().upper()}.{normalizar_cabecalho(cidade)}"


def parse_municipio_base(valor: str) -> tuple[str, str]:
    """Converte rótulo da base (`RJ.RIO DE JANEIRO`) em UF e cidade normalizada."""
    texto = str(valor or "").strip()
    if "." not in texto:
        raise ValueError(f"município inválido na base: {valor!r}")
    uf, cidade = texto.split(".", 1)
    return uf.strip().upper(), normalizar_cabecalho(cidade.strip())


def municipios_permitidos(
    localizacoes: set[tuple[str, str]],
    municipios_na_base: set[str],
    *,
    modo: ModoRecorteGeografico | None = None,
) -> set[str]:
    """UF+cidade dos beneficiários → chaves `UF.CIDADE` presentes na base de rede."""
    escolhido = modo if modo is not None else CRITERIO_RECORTE_GEOGRAFICO
    permitidos: set[str] = set()
    for uf, cidade in localizacoes:
        uf = uf.strip().upper()
        cidade_norm = normalizar_cabecalho(cidade)
        if not uf or not cidade_norm:
            continue
        chave = chave_municipio(uf, cidade_norm)
        if chave in municipios_na_base:
            permitidos.add(chave)
        if escolhido == ModoRecorteGeografico.MUNICIPIO_E_CAPITAL_UF:
            cap = CAPITAIS_UF.get(uf)
            if cap:
                ch_cap = chave_municipio(uf, cap)
                if ch_cap in municipios_na_base:
                    permitidos.add(ch_cap)
    return permitidos
