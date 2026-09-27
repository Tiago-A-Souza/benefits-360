"""Constantes do layout piloto SISCOR."""

from __future__ import annotations

COLUNAS_OBRIGATORIAS = (
    "CLIENTE",
    "SEGURADO",
    "PARENTESCO",
    "DATA DE NASCIMENTO",
    "PLANO",
    "SEGURADORA",
    "VALOR",
    "STATUS SEGURADO",
)

COLUNAS_OPCIONAIS = (
    "SEXO",
    "CPF TITULAR",
    "TITULAR",
    "MATRICULA",
    "TIPO DE VIDA",
    "UF",
    "CIDADE",
)

# Variações de rótulo → nome canônico (após normalizar_cabecalho).
# Não use alias para NBSP/espaços: isso é papel da normalização.
ALIAS_COLUNAS_OPCIONAIS: dict[str, str] = {
    "SEXO": "SEXO",
    "CPF TITULAR": "CPF TITULAR",
    "CPF DO TITULAR": "CPF TITULAR",
    "TITULAR": "TITULAR",
    "MATRICULA": "MATRICULA",
    "TIPO DE VIDA": "TIPO DE VIDA",
    "UF": "UF",
    "ESTADO": "UF",
    "CIDADE": "CIDADE",
    "MUNICIPIO": "CIDADE",
}

MAPEAMENTO_COLUNAS = {nome: nome for nome in COLUNAS_OBRIGATORIAS}

STATUS_ATIVO = "ATIVO"

PARENTESCO_MAP = {
    "TITULAR": "titular",
    "CÔNJUGE": "conjuge",
    "CONJUGE": "conjuge",
    "FILHO": "filho",
    "FILHA": "filho",
    "FILHO(A)": "filho",
    "COMPANHEIRO": "companheiro",
    "COMPANHEIRO(A)": "companheiro",
}
