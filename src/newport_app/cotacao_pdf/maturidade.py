"""Níveis de maturidade da extração PDF — distintos de homologação financeira."""

from __future__ import annotations

from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata

LIMIAR_SELECAO_CONSCIENTE = 3
_CODIGOS_TABELA_AUSENTE = frozenset({"PDF-PORTO-004", "PDF-SUL-001"})


def opcoes_ativas(extracao: ExtracaoCotacaoCandidata) -> list:
    return [o for o in extracao.opcoes if not o.excluida]


def exige_selecao_consciente(extracao: ExtracaoCotacaoCandidata) -> bool:
    """Porto e documentos com muitos planos na tabela geral exigem escolha explícita."""
    template_id = extracao.documento.template_id or ""
    if template_id.startswith("porto-"):
        return True
    return len(opcoes_ativas(extracao)) > LIMIAR_SELECAO_CONSCIENTE


def avaliar_maturidade(extracao: ExtracaoCotacaoCandidata) -> dict[str, bool]:
    """
    Diferencia estágios da pipeline:
    - template_reconhecido: família identificada antes da extração
    - tabela_extraida: opções tarifárias localizadas
    - valores_reconciliados: somatórios internos coerentes por opção
    - proposta_pronta_aplicacao: campos confirmados nas opções alvo

    Reconhecer o template não implica extração financeira homologada.
    """
    ativas = opcoes_ativas(extracao)
    template_reconhecido = (
        extracao.estado not in ("nao_reconhecido", "erro")
        and bool(extracao.documento.template_id)
    )
    tabela_extraida = bool(ativas) and not any(
        a.codigo in _CODIGOS_TABELA_AUSENTE for a in extracao.alertas
    )
    valores_reconciliados = bool(ativas) and all(
        o.reconciliacao is not None and o.reconciliacao.ok for o in ativas
    )

    if exige_selecao_consciente(extracao):
        alvo = [o for o in ativas if o.selecionada_para_comparativo]
    else:
        alvo = ativas

    proposta_pronta = bool(alvo) and all(not pendencias_opcao(o) for o in alvo)

    return {
        "template_reconhecido": template_reconhecido,
        "tabela_extraida": tabela_extraida,
        "valores_reconciliados": valores_reconciliados,
        "proposta_pronta_aplicacao": proposta_pronta,
        "extracao_financeira_homologada": False,
        "exige_selecao_consciente": exige_selecao_consciente(extracao),
    }
