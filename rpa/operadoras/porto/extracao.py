"""Leitura e conferência dos valores da Porto (Seção 3 do mapa). Funções puras, sem navegador.

Taxa de inscrição = R$ 5,00 por vida. IOF = 2,38% × (sub-total + taxa). Total = sub-total + taxa + IOF.
Ler os valores só depois de preencher todas as vidas (o valor por vida muda com o total).
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from nucleo.texto import norm, rx

_NUM = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
RX_VALOR = re.compile(r"(?:R\$\s*)?" + _NUM)
RX_NUMERO = re.compile(r"cota[cç][aã]o n[ºo°]?\s*(\d+)", re.I)
TAXA_POR_VIDA = Decimal("5.00")
ALIQUOTA_IOF = Decimal("0.0238")


def _d(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def dinheiro(texto: str) -> Decimal:
    m = RX_VALOR.search(texto or "")
    if not m:
        raise ValueError(f"valor inválido: {texto!r}")
    return Decimal(m.group(1).replace(".", "").replace(",", "."))


def _num(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def ler_numero_cotacao(texto: str) -> str | None:
    m = RX_NUMERO.search(texto or "")
    return m.group(1) if m else None


def taxa_inscricao(vidas: int, por_vida: Decimal = TAXA_POR_VIDA) -> Decimal:
    return _d(por_vida * vidas)


def iof_de(subtotal: Decimal, taxa: Decimal, aliquota: Decimal = ALIQUOTA_IOF) -> Decimal:
    return _d((subtotal + taxa) * aliquota)


def conferir_detalhes(vidas: int, valores_por_faixa: dict[str, Decimal], quantidades: dict[str, int],
                      subtotal: Decimal, taxa: Decimal, iof: Decimal, total: Decimal,
                      aliquota: Decimal, por_vida: Decimal, tol: Decimal) -> list[str]:
    """soma (valor × vidas) = sub-total; taxa = R$ 5 por vida; IOF = alíquota × (sub-total + taxa); total bate."""
    problemas = []
    if valores_por_faixa:
        soma = _d(sum((_d(valores_por_faixa[r] * q) for r, q in quantidades.items() if q and r in valores_por_faixa),
                      Decimal("0")))
        if abs(soma - subtotal) > tol:
            problemas.append(f"soma por faixa {soma} ≠ sub-total {subtotal}")
    taxa_ok = taxa_inscricao(vidas, por_vida)
    if abs(taxa - taxa_ok) > tol:
        problemas.append(f"taxa de inscrição {taxa} ≠ {taxa_ok} (R$ {por_vida} × {vidas} vidas)")
    iof_ok = iof_de(subtotal, taxa, aliquota)
    if abs(iof - iof_ok) > tol:
        problemas.append(f"IOF {iof} ≠ {iof_ok} ({aliquota} × (sub-total {subtotal} + taxa {taxa}))")
    total_ok = _d(subtotal + taxa + iof)
    if abs(total - total_ok) > tol:
        problemas.append(f"total mensal {total} ≠ sub-total + taxa + IOF {total_ok}")
    return problemas


def ler_detalhes(texto: str) -> dict:
    """Lê número, sub-total, taxa, IOF e total do passo 4 (textos do vídeo/simulador)."""
    t = texto or ""
    numero = ler_numero_cotacao(t)
    def _rotulo(nome: str) -> Decimal | None:
        m = re.search(rf"{rx(nome).pattern}\s*:?\s*(?:R\$\s*)?{_NUM}", t, re.I)
        return _num(m.group(1)) if m else None
    return {
        "numero": numero,
        "subtotal": _rotulo("Sub-total") or _rotulo("Subtotal"),
        "taxa": _rotulo("Taxa de inscrição"),
        "iof": _rotulo("IOF Saúde") or _rotulo("IOF"),
        "total": _rotulo("Valor total mensal") or _rotulo("Total mensal"),
    }


def ler_resumo_passo3(texto: str) -> dict:
    t = texto or ""
    m_plano = re.search(r"Resumo da cota[cç][aã]o.*?(?:Plano\s*:?\s*)([^\n]+)", t, re.I | re.S)
    m_valor = re.search(r"(?:Valor|Pre[cç]o)\s*:?\s*(?:R\$\s*)?" + _NUM, t, re.I)
    return {
        "plano": " ".join((m_plano.group(1) if m_plano else "").split()),
        "valor": _num(m_valor.group(1)) if m_valor else None,
        "selecionado": "selecionado" in norm(t),
    }
