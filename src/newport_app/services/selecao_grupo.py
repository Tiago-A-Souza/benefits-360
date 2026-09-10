"""Seleção de planos por grupo de beneficiários — FASE 1.

Grava a escolha de um subgrupo sem tocar na dos outros, e mantém
`opcoes_proposta` coerente como a união das seleções efetivas.

A poda da união reusa a porta da FASE 0: se tirar um plano derrubar atribuição
de cenário, o serviço recusa com o inventário e só executa com confirmação
explícita. Nenhum plano sai em silêncio, por nenhum dos dois caminhos.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses_remocao import ImpactoRemocao
from newport_app.models.responses_selecao_grupo import (
    GrupoSelecaoPlanos,
    PlanoDoGrupo,
    SelecaoPlanosGrupoResponse,
)
from newport_app.rascunho.cenarios_sync import podar_cenarios_orfaos, subgrupos_com_vidas
from newport_app.rascunho.impacto_remocao import montar_impacto_remocao
from newport_app.rascunho.selecao_grupo import (
    definir_selecao_do_subgrupo,
    opcoes_do_subgrupo,
    sanear_selecao_por_grupo,
    tem_selecao_propria,
    uniao_das_selecoes,
)
from newport_app.services.matriz_estimativa import montar_matriz_estimativa
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual


class SubgrupoDesconhecidoError(Exception):
    pass


class SelecaoRemocaoExigeConfirmacaoError(Exception):
    """A união deixaria planos fora de todos os grupos, e isso mutila cenário."""

    def __init__(self, mensagem: str, impacto: ImpactoRemocao) -> None:
        super().__init__(mensagem)
        self.impacto = impacto


def _formatar_reais(centavos: int | None) -> str | None:
    if centavos is None:
        return None
    neg = centavos < 0
    v = abs(centavos)
    inteiro = f"{v // 100:,}".replace(",", ".")
    return f"{'-' if neg else ''}R$ {inteiro},{v % 100:02d}"


def _ids_podados(rascunho: RascunhoEstudo) -> set[str]:
    """Planos do catálogo que ficaram fora de todas as seleções efetivas."""
    return {op.id for op in rascunho.opcoes_proposta} - set(uniao_das_selecoes(rascunho))


def montar_selecao_por_grupo(rascunho: RascunhoEstudo) -> SelecaoPlanosGrupoResponse:
    """Um grupo por plano vigente com vidas, cada um com o catálogo inteiro.

    Todos os planos aparecem em todos os grupos, com valores recalculados para as
    vidas daquele grupo — o que muda de grupo para grupo é quais estão marcados.
    A estimativa vem de `montar_matriz_estimativa`, a mesma que alimenta o
    dropdown da etapa 4; não há segundo cálculo.
    """
    resumo = montar_resumo_plano_atual(rascunho)
    matriz = montar_matriz_estimativa(rascunho)
    celulas = {(c.opcao_id, c.subgrupo_id): c for c in matriz.celulas}
    com_vidas = set(subgrupos_com_vidas(rascunho))

    grupos: list[GrupoSelecaoPlanos] = []
    for item in resumo.planos:
        if item.subgrupo_id not in com_vidas:
            continue
        escolhidos = set(opcoes_do_subgrupo(rascunho, item.subgrupo_id))
        planos: list[PlanoDoGrupo] = []
        for opcao in rascunho.opcoes_proposta:
            celula = celulas.get((opcao.id, item.subgrupo_id))
            estimado = celula.estimado_centavos if celula else None
            diff = celula.diff_centavos if celula else None
            planos.append(
                PlanoDoGrupo(
                    opcao_id=opcao.id,
                    plano_nome=opcao.plano_nome,
                    operadora=opcao.operadora,
                    acomodacao=opcao.acomodacao,
                    estimado_centavos=estimado,
                    estimado_reais=_formatar_reais(estimado),
                    diff_centavos=diff,
                    diff_reais=_formatar_reais(diff),
                    escolhido=opcao.id in escolhidos,
                )
            )
        grupos.append(
            GrupoSelecaoPlanos(
                subgrupo_id=item.subgrupo_id,
                plano_nome=item.plano_nome,
                operadora=item.operadora,
                quantidade_beneficiarios=item.quantidade_beneficiarios,
                referencia_reais=item.referencia_comparativo_reais,
                referencia_rotulo=item.referencia_comparativo,
                selecao_propria=tem_selecao_propria(rascunho, item.subgrupo_id),
                escolhidos=len(escolhidos),
                planos=planos,
            )
        )

    return SelecaoPlanosGrupoResponse(
        grupos=grupos,
        total_catalogo=len(rascunho.opcoes_proposta),
    )


def aplicar_selecao_do_grupo(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    opcao_ids: list[str],
    *,
    confirmar_remocoes: bool = False,
) -> ImpactoRemocao:
    """Grava a seleção do grupo e devolve o que a união tirou do catálogo.

    Muta o rascunho só depois de decidir: se a poda exige confirmação e ela não
    veio, levanta antes de escrever qualquer coisa.
    """
    if not any(sg.id == subgrupo_id for sg in rascunho.subgrupos_atuais):
        raise SubgrupoDesconhecidoError(subgrupo_id)

    ensaio = rascunho.model_copy(deep=True)
    definir_selecao_do_subgrupo(ensaio, subgrupo_id, opcao_ids)
    saindo = _ids_podados(ensaio)
    impacto = montar_impacto_remocao(ensaio, saindo)

    if impacto.exige_confirmacao and not confirmar_remocoes:
        raise SelecaoRemocaoExigeConfirmacaoError(
            "Esta seleção deixa planos fora de todos os grupos, e eles estão em uso na etapa 4.",
            impacto,
        )

    definir_selecao_do_subgrupo(rascunho, subgrupo_id, opcao_ids)
    if saindo:
        rascunho.opcoes_proposta = [
            op for op in rascunho.opcoes_proposta if op.id not in saindo
        ]
        podar_cenarios_orfaos(rascunho)
        sanear_selecao_por_grupo(rascunho)
    return impacto
