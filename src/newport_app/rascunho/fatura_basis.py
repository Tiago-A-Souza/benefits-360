"""Resolução explícita de fatura_price_basis a partir do tipo fiscal.

O campo de UI «valor informado já inclui IOF?» saiu da etapa 2 por ser
redundante com tipo fiscal. O valor permanece no modelo; quando ainda está
desconhecido e o tipo fiscal basta, grava-se o basis explícito — sem omissão
no motor e sem sobrescrever decisão já gravada.
"""

from __future__ import annotations

from newport_app.models.draft import PriceBasisRascunho, RascunhoEstudo


def basis_explicito_para_tipo_fiscal(
    tipo_fiscal: str | None,
) -> PriceBasisRascunho | None:
    """Mapeia tipo fiscal → basis de fatura quando a decisão é determinada.

    - operadora: IOF não se aplica → nao_aplica
    - seguradora: valores de fatura/SISCOR entram sem IOF → exclui_iof
      (o motor aplica 2,38% na normalização)
    """
    if tipo_fiscal == "operadora":
        return PriceBasisRascunho.NAO_APLICA
    if tipo_fiscal == "seguradora":
        return PriceBasisRascunho.EXCLUI_IOF
    return None


def aplicar_fatura_price_basis_explicito(rascunho: RascunhoEstudo) -> int:
    """Preenche fatura_price_basis só quando ainda desconhecido e o tipo basta.

    Não sobrescreve inclui_iof / exclui_iof / nao_aplica já gravados (legado).
    Retorna quantos subgrupos foram alterados.
    """
    alterados = 0
    for sg in rascunho.subgrupos_atuais:
        if sg.fatura_price_basis != PriceBasisRascunho.DESCONHECIDO:
            continue
        resolvido = basis_explicito_para_tipo_fiscal(sg.tipo_fiscal)
        if resolvido is None:
            continue
        sg.fatura_price_basis = resolvido
        alterados += 1
    return alterados
