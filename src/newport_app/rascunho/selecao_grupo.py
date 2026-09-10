"""Seleção de planos por grupo de beneficiários — FASE 1.

A regra central é de **leitura**: subgrupo sem entrada própria vale como «todo o
catálogo». Isso não é valor por omissão — nada é gravado no rascunho para
significar «todos». É o que mantém os estudos antigos, que nunca tiveram este
campo, funcionando sem migração de dados.
"""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo, SelecaoPlanosGrupoRascunho


def catalogo_ids(rascunho: RascunhoEstudo) -> list[str]:
    return [op.id for op in rascunho.opcoes_proposta]


def tem_selecao_propria(rascunho: RascunhoEstudo, subgrupo_id: str) -> bool:
    """Distingue «sem entrada» (herda o catálogo) de «entrada vazia» (nenhum plano)."""
    return any(s.subgrupo_id == subgrupo_id for s in rascunho.selecao_planos_por_grupo)


def opcoes_do_subgrupo(rascunho: RascunhoEstudo, subgrupo_id: str) -> list[str]:
    """Planos que competem com este vigente, na ordem do catálogo.

    Sem entrada própria: o catálogo inteiro. Com entrada: só os ids que ainda
    existem no catálogo, para o retorno nunca apontar plano removido.
    """
    for sel in rascunho.selecao_planos_por_grupo:
        if sel.subgrupo_id == subgrupo_id:
            escolhidos = set(sel.opcao_ids)
            return [oid for oid in catalogo_ids(rascunho) if oid in escolhidos]
    return catalogo_ids(rascunho)


def selecao_efetiva(rascunho: RascunhoEstudo) -> dict[str, list[str]]:
    """Seleção de cada subgrupo com vidas, já com o fallback aplicado."""
    from newport_app.rascunho.cenarios_sync import subgrupos_com_vidas

    return {sg: opcoes_do_subgrupo(rascunho, sg) for sg in subgrupos_com_vidas(rascunho)}


def ids_do_pdf_no_grupo(
    rascunho: RascunhoEstudo, subgrupo_id: str, extracao_id: str
) -> set[str]:
    """Opções deste PDF que o grupo já escolheu (ids do catálogo)."""
    if not tem_selecao_propria(rascunho, subgrupo_id):
        return set()
    escolhidos = set(opcoes_do_subgrupo(rascunho, subgrupo_id))
    return {
        op.id
        for op in rascunho.opcoes_proposta
        if op.extracao_id == extracao_id and op.id in escolhidos
    }


def ids_extracao_protegidos_por_outros_grupos(
    rascunho: RascunhoEstudo, extracao_id: str, subgrupo_alvo: str
) -> set[str]:
    """Opções deste PDF que outros grupos já escolheram — a re-aplicação não pode tirá-las."""
    from newport_app.rascunho.cenarios_sync import subgrupos_com_vidas

    protegidos: set[str] = set()
    for sg in subgrupos_com_vidas(rascunho):
        if sg == subgrupo_alvo:
            continue
        ids_catalogo = ids_do_pdf_no_grupo(rascunho, sg, extracao_id)
        if not ids_catalogo:
            continue
        for op in rascunho.opcoes_proposta:
            if op.id in ids_catalogo and op.extracao_opcao_id:
                protegidos.add(op.extracao_opcao_id)
    return protegidos


def atribui_planos_do_pdf_ao_grupo(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    extracao_id: str,
    opcao_ids: list[str],
) -> None:
    """Grava a escolha deste PDF neste grupo, sem copiar para os outros.

    Outros grupos ainda sem entrada própria ganham entrada vazia: senão o
    fallback de leitura herdaria o catálogo e a escolha do primeiro grupo
    apareceria no segundo. Estudos antigos, que nunca passaram por este
    caminho, continuam herdando — nada é gravado só por abrir o rascunho.
    """
    from newport_app.rascunho.cenarios_sync import subgrupos_com_vidas

    if len(subgrupos_com_vidas(rascunho)) <= 1:
        return

    for sg in subgrupos_com_vidas(rascunho):
        if sg != subgrupo_id and not tem_selecao_propria(rascunho, sg):
            definir_selecao_do_subgrupo(rascunho, sg, [])

    ids_deste_pdf = {
        op.id for op in rascunho.opcoes_proposta if op.extracao_id == extracao_id
    }
    if tem_selecao_propria(rascunho, subgrupo_id):
        manter = [
            oid
            for oid in opcoes_do_subgrupo(rascunho, subgrupo_id)
            if oid not in ids_deste_pdf
        ]
    else:
        manter = []
    definir_selecao_do_subgrupo(rascunho, subgrupo_id, manter + list(opcao_ids))


def uniao_das_selecoes(rascunho: RascunhoEstudo) -> list[str]:
    """União das seleções efetivas, sem duplicata, na ordem do catálogo.

    Como subgrupo sem entrada contribui com o catálogo inteiro, a união só é
    menor que o catálogo quando **todos** os subgrupos com vidas têm entrada
    própria e algum plano ficou fora de todas.
    """
    efetiva = selecao_efetiva(rascunho)
    if not efetiva:
        return catalogo_ids(rascunho)
    escolhidos: set[str] = set()
    for ids in efetiva.values():
        escolhidos.update(ids)
    return [oid for oid in catalogo_ids(rascunho) if oid in escolhidos]


def definir_selecao_do_subgrupo(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    opcao_ids: list[str],
) -> None:
    """Grava a seleção de um subgrupo sem tocar na dos outros."""
    validos = [oid for oid in catalogo_ids(rascunho) if oid in set(opcao_ids)]
    for sel in rascunho.selecao_planos_por_grupo:
        if sel.subgrupo_id == subgrupo_id:
            sel.opcao_ids = validos
            return
    rascunho.selecao_planos_por_grupo.append(
        SelecaoPlanosGrupoRascunho(subgrupo_id=subgrupo_id, opcao_ids=validos)
    )


def sanear_selecao_por_grupo(rascunho: RascunhoEstudo) -> None:
    """Descarta referências a plano que saiu do catálogo e a subgrupo inexistente.

    Espelha `podar_cenarios_orfaos`: mantém o campo coerente sem apagar plano
    nenhum por conta própria.
    """
    catalogo = set(catalogo_ids(rascunho))
    subgrupos = {sg.id for sg in rascunho.subgrupos_atuais}
    saneadas: list[SelecaoPlanosGrupoRascunho] = []
    for sel in rascunho.selecao_planos_por_grupo:
        if sel.subgrupo_id not in subgrupos:
            continue
        saneadas.append(
            sel.model_copy(
                update={"opcao_ids": [oid for oid in sel.opcao_ids if oid in catalogo]}
            )
        )
    rascunho.selecao_planos_por_grupo = saneadas
