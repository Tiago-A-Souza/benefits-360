"""Inventário do que se perde ao tirar planos do comparativo — FASE 0 e FASE 1.

Fonte única dos dois caminhos que removem plano: a re-aplicação de um PDF
(`cotacao_pdf/apply.py`) e a seleção por grupo (`services/selecao_grupo.py`).
Não muta o rascunho — roda antes de qualquer escrita, para o operador poder
desistir.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses_remocao import (
    AtribuicaoDesfeita,
    CenarioIncompleto,
    ImpactoRemocao,
)
from newport_app.rascunho.cenarios_sync import rotulo_cenario, subgrupos_com_vidas


def rotulo_subgrupo(rascunho: RascunhoEstudo, alvo_id: str) -> str:
    sg = next((s for s in rascunho.subgrupos_atuais if s.id == alvo_id), None)
    return sg.plano_nome if sg and sg.plano_nome else alvo_id


def montar_impacto_remocao(
    rascunho: RascunhoEstudo,
    ids_saindo: set[str],
) -> ImpactoRemocao:
    """Quais planos saem, quais atribuições se desfazem e quais cenários mutilam.

    Um cenário é dado como incompleto pela mesma regra do B-06: todo subgrupo com
    vidas incluídas precisa de atribuição.
    """
    if not ids_saindo:
        return ImpactoRemocao()

    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    planos = [(por_id[oid].plano_nome or oid) for oid in ids_saindo if oid in por_id]

    desfeitas: list[AtribuicaoDesfeita] = []
    incompletos: list[CenarioIncompleto] = []
    obrigatorios = subgrupos_com_vidas(rascunho)

    for cenario in rascunho.cenarios:
        rotulo = rotulo_cenario(rascunho, cenario)
        perdidas = [a for a in cenario.atribuicoes if a.opcao_plano_id in ids_saindo]
        for a in perdidas:
            desfeitas.append(
                AtribuicaoDesfeita(
                    cenario_id=cenario.id,
                    cenario_rotulo=rotulo,
                    alvo_id=a.alvo_id,
                    alvo_rotulo=rotulo_subgrupo(rascunho, a.alvo_id),
                    plano=(por_id[a.opcao_plano_id].plano_nome or a.opcao_plano_id)
                    if a.opcao_plano_id in por_id
                    else (a.opcao_plano_id or ""),
                )
            )
        if not perdidas:
            continue
        atendidos = {
            a.alvo_id
            for a in cenario.atribuicoes
            if a.opcao_plano_id and a.opcao_plano_id not in ids_saindo
        }
        orfaos = [sg for sg in obrigatorios if sg not in atendidos]
        if orfaos:
            incompletos.append(
                CenarioIncompleto(
                    cenario_id=cenario.id,
                    cenario_rotulo=rotulo,
                    alvos_sem_atribuicao=[
                        rotulo_subgrupo(rascunho, sg) for sg in orfaos
                    ],
                    ficou_vazio=not atendidos,
                )
            )

    return ImpactoRemocao(
        planos_removidos=sorted(planos),
        atribuicoes_desfeitas=desfeitas,
        cenarios_incompletos=incompletos,
    )
