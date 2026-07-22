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
