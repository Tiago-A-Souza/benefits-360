"""Utilitários para fixtures XLSX fictícias."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS


def gerar_planilha_siscor(linhas: list[dict[str, object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(COLUNAS_OBRIGATORIAS))
    for linha in linhas:
        ws.append([linha.get(col) for col in COLUNAS_OBRIGATORIAS])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def linha_ficticia(
    idx: int,
    *,
    plano: str = "Plano Demo A",
    operadora: str = "Operadora Fictícia",
    cliente: str = "Empresa Demonstração Ltda.",
    valor: float | None = None,
) -> dict[str, object]:
    ano = 1970 + (idx % 30)
    valor_efetivo = 850.0 + idx if valor is None else valor
    return {
        "CLIENTE": cliente,
        "SEGURADO": f"Beneficiário Fictício {idx + 1}",
        "PARENTESCO": "TITULAR" if idx % 3 == 0 else "FILHO(A)",
        "DATA DE NASCIMENTO": f"01/01/{ano}",
        "PLANO": plano,
        "SEGURADORA": operadora,
        "VALOR": valor_efetivo,
        "STATUS SEGURADO": "ATIVO",
    }


def planilha_12_vidas() -> bytes:
    return gerar_planilha_siscor([linha_ficticia(i) for i in range(12)])


def planilha_41_vidas_2_planos() -> bytes:
    linhas = []
    for i in range(36):
        linhas.append(linha_ficticia(i, plano="Plano Fictício A"))
    for i in range(36, 41):
        linhas.append(linha_ficticia(i, plano="Plano Fictício B"))
    return gerar_planilha_siscor(linhas)
