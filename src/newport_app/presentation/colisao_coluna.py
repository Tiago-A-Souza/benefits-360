"""Identidade da coluna (`coluna_id` = cenário) e rede contra colisão.

A apresentação identifica coluna por `chave_de_coluna` — desde a FASE 4, o
`cenario_id`. A opção de referência (`opcao_id`) continua no comparativo para
metadado da cotação; não é mais a chave. `APP-COL-001` permanece: se a chave
voltar a colapsar duas colunas, o alerta dispara.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import PendenciaItem, ResultadoPropostaComparativo

CODIGO_COLISAO_COLUNA = "APP-COL-001"


def chave_de_coluna(prop: ResultadoPropostaComparativo) -> str:
    """Identidade da coluna = cenário (`coluna_id`).

    Não entra no payload do comparativo — `cenario_id` já está lá. Quem colapsa
    as colunas e quem detecta a colisão leem daqui. Com esta chave a colisão
    da opção de referência some; o alerta `APP-COL-001` fica como rede.
    """
    return prop.cenario_id


def coluna_bate(col, key: str) -> bool:
    """A célula pertence à coluna `key` (`coluna_id` ou `opcao_id` legado)."""
    cid = getattr(col, "coluna_id", None) or ""
    return key == cid or key == getattr(col, "opcao_id", None)


def id_coluna_vm(prop) -> str:
    """Chave da coluna no ViewModel — `coluna_id`, com fallback ao `opcao_id`."""
    cid = getattr(prop, "coluna_id", None)
    if cid:
        return cid
    return prop.opcao_id


def resolver_colunas_selecionadas(
    ids_gravados: list[str],
    propostas: list[ResultadoPropostaComparativo],
) -> list[str]:
    """Resolve seleção gravada (opcao_id ou cenario_id) para `coluna_id`.

    Os 49 estudos com `selecao_apresentacao.opcao_ids` continuam abrindo:
    um `opcao_id` vira todas as colunas cuja opção de referência é aquela —
    o mesmo espírito do fallback da FASE 1. Sem migração do JSON gravado.
    """
    calculadas = [p for p in propostas if p.calculo_realizado]
    ids_coluna = {chave_de_coluna(p) for p in calculadas}
    if not ids_gravados:
        return [chave_de_coluna(p) for p in calculadas]

    out: list[str] = []
    vistos: set[str] = set()

    def _add(cid: str) -> None:
        if cid in vistos:
            return
        vistos.add(cid)
        out.append(cid)

    for gravado in ids_gravados:
        if gravado in ids_coluna:
            _add(gravado)
            continue
        for prop in calculadas:
            if prop.opcao_id == gravado:
                _add(chave_de_coluna(prop))
    return out


def colisoes_de_chave_de_coluna(
    propostas: list[ResultadoPropostaComparativo],
) -> dict[str, list[str]]:
    """chave de coluna repetida → ids dos cenários que a compartilham, em ordem."""
    por_chave: dict[str, list[str]] = {}
    for prop in propostas:
        if not prop.calculo_realizado:
            continue
        por_chave.setdefault(chave_de_coluna(prop), []).append(prop.cenario_id)
    return {chave: cens for chave, cens in por_chave.items() if len(cens) > 1}


def pendencias_colisao_de_coluna(
    rascunho: RascunhoEstudo,
    propostas: list[ResultadoPropostaComparativo],
) -> list[PendenciaItem]:
    colisoes = colisoes_de_chave_de_coluna(propostas)
    if not colisoes:
        return []

    rotulos = {p.cenario_id: p.plano_nome for p in propostas}
    nomes_opcao = {op.id: (op.plano_nome or op.id) for op in rascunho.opcoes_proposta}

    partes: list[str] = []
    for chave, cenarios in colisoes.items():
        nomes = [f"«{rotulos.get(c, c)}»" for c in cenarios]
        envolvidos = (
            " e ".join(nomes)
            if len(nomes) == 2
            else ", ".join(nomes[:-1]) + " e " + nomes[-1]
        )
        partes.append(
            f"Os cenários {envolvidos} começam pelo mesmo plano "
            f"«{nomes_opcao.get(chave, chave)}»"
        )

    quantidade = sum(len(c) for c in colisoes.values())
    return [
        PendenciaItem(
            tipo="alerta",
            titulo=(
                "Cenários que compartilham o primeiro plano"
                if len(colisoes) == 1
                else f"{len(colisoes)} planos iniciais repetidos entre cenários"
            ),
            descricao=(
                " · ".join(partes)
                + ". A comparação na tela está completa, mas o documento gerado "
                "mostrará apenas uma dessas colunas."
            ),
            acao_sugerida=(
                "Para ter as duas colunas no documento, reordene as atribuições de "
                "um dos cenários para que comecem por planos diferentes, ou gere um "
                "documento por cenário."
            ),
            codigo=CODIGO_COLISAO_COLUNA,
            etapa=5,
            quantidade=quantidade,
        )
    ]
