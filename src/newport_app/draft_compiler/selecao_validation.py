"""A cotação atribuída a um grupo tem de estar entre as escolhidas para ele.

Antes da FASE 1 nada verificava isso: `APP-STR-002` e `B-05` só exigem que a
opção exista no catálogo do estudo. Era o que deixava um plano caro para as
vidas de um grupo ser atribuído a ele sem nenhum obstáculo.

Vive no compilador, não em `validar_estrutura`: bloquear no salvamento tornaria
impossível **mudar a seleção** de um grupo depois que o cenário já existe, que é
exatamente a situação em que o operador precisa ser avisado. Aqui ele salva,
vê o bloqueio e decide — o sistema não escolhe outro plano por ele.
"""

from __future__ import annotations

from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import RascunhoEstudo
from newport_app.rascunho.cenarios_sync import rotulo_cenario
from newport_app.rascunho.selecao_grupo import opcoes_do_subgrupo, tem_selecao_propria


def validar_atribuicoes_na_selecao(rascunho: RascunhoEstudo) -> list[ErroCompilacao]:
    """Atribuição a plano que não foi escolhido para aquele grupo bloqueia.

    Grupo sem seleção própria vale como catálogo inteiro, então nele qualquer
    plano do catálogo passa — é o que mantém os estudos anteriores à FASE 1
    compilando sem tocar em nada.
    """
    erros: list[ErroCompilacao] = []
    subgrupos = {sg.id: sg for sg in rascunho.subgrupos_atuais}
    opcoes = {op.id: op for op in rascunho.opcoes_proposta}
    permitidos: dict[str, set[str]] = {}

    for idx_c, cenario in enumerate(rascunho.cenarios):
        for idx_a, atrib in enumerate(cenario.atribuicoes):
            if atrib.alvo_tipo != "subgrupo" or not atrib.opcao_plano_id:
                continue
            subgrupo = subgrupos.get(atrib.alvo_id)
            if subgrupo is None:
                continue  # inexistente já é APP-STR-002; não duplicamos o erro
            if not tem_selecao_propria(rascunho, atrib.alvo_id):
                continue
            if atrib.alvo_id not in permitidos:
                permitidos[atrib.alvo_id] = set(
                    opcoes_do_subgrupo(rascunho, atrib.alvo_id)
                )
            if atrib.opcao_plano_id in permitidos[atrib.alvo_id]:
                continue

            opcao = opcoes.get(atrib.opcao_plano_id)
            nome_plano = (
                opcao.plano_nome if opcao and opcao.plano_nome else atrib.opcao_plano_id
            )
            nome_grupo = subgrupo.plano_nome or subgrupo.id
            erros.append(
                ErroCompilacao(
                    codigo="APP-GRP-001",
                    caminho=f"/cenarios/{idx_c}/atribuicoes/{idx_a}/opcao_plano_id",
                    mensagem=(
                        f"No cenário «{rotulo_cenario(rascunho, cenario)}», o grupo "
                        f"«{nome_grupo}» recebeu «{nome_plano}», que não está entre os "
                        f"planos escolhidos para ele na etapa 3. Escolha um dos planos "
                        f"do grupo ou inclua este na seleção dele."
                    ),
                    severidade="bloqueante",
                )
            )

    return erros
