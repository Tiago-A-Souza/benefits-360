"""Sincronização de cenários do rascunho com opções de proposta (etapa 3/4)."""

from __future__ import annotations

import uuid

from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho, RascunhoEstudo


def _novo_id(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def _cenario_da_opcao(cenarios: list[CenarioRascunho], opcao_id: str) -> CenarioRascunho | None:
    for cenario in cenarios:
        for atrib in cenario.atribuicoes:
            if atrib.opcao_plano_id == opcao_id:
                return cenario
    return None


def subgrupos_com_vidas(rascunho: RascunhoEstudo) -> list[str]:
    """Subgrupos com ao menos uma vida incluída no estudo."""
    com_vidas: set[str] = set()
    for vida in rascunho.vidas:
        if vida.incluida and vida.subgrupo_atual_id:
            com_vidas.add(vida.subgrupo_atual_id)
    return [sg.id for sg in rascunho.subgrupos_atuais if sg.id in com_vidas]


def vidas_incluidas_ids(rascunho: RascunhoEstudo) -> list[str]:
    return [v.id for v in rascunho.vidas if v.incluida]


def _nome_opcao(rascunho: RascunhoEstudo, opcao_id: str) -> str:
    op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    if op and op.plano_nome:
        return op.plano_nome
    return opcao_id


def opcoes_usadas_nos_cenarios(rascunho: RascunhoEstudo) -> list[str]:
    """Opções distintas referenciadas em alguma atribuição, ordem de primeira aparição."""
    usadas: list[str] = []
    vistos: set[str] = set()
    for cenario in rascunho.cenarios:
        for atr in cenario.atribuicoes:
            oid = atr.opcao_plano_id
            if oid and oid not in vistos:
                vistos.add(oid)
                usadas.append(oid)
    return usadas


def propostas_fora_dos_cenarios(rascunho: RascunhoEstudo) -> list[str]:
    """IDs de opções da etapa 3 que não aparecem em nenhuma atribuição de cenário."""
    usadas = set(opcoes_usadas_nos_cenarios(rascunho))
    return [op.id for op in rascunho.opcoes_proposta if op.id not in usadas]


def rotulo_cenario(rascunho: RascunhoEstudo, cenario: CenarioRascunho) -> str:
    """Rótulo da coluna do comparativo — sempre derivado das atribuições atuais.

    Não usa ``cenario.rotulo`` em cache: após misturar cotações o rótulo gravado
    fica stale (ex.: «PRATA» quando a coluna é «PRATA + OURO»).
    """
    escolhidos = {
        atr.opcao_plano_id for atr in cenario.atribuicoes if atr.opcao_plano_id
    }
    # Ordem do catálogo, não das atribuições: reordenar o cenário não pode
    # mudar o rótulo da coluna (FASE 3, teste 6).
    op_ids = [op.id for op in rascunho.opcoes_proposta if op.id in escolhidos]
    for oid in escolhidos:
        if oid not in op_ids:
            op_ids.append(oid)

    if not op_ids:
        return "Cenário sem proposta"
    if len(op_ids) == 1:
        return _nome_opcao(rascunho, op_ids[0])
    return " + ".join(_nome_opcao(rascunho, oid) for oid in op_ids)


def opcao_referencia_cenario(cenario: CenarioRascunho) -> str | None:
    """Opção de referência estável para seleção na UI (primeira atribuição)."""
    for atr in cenario.atribuicoes:
        if atr.opcao_plano_id:
            return atr.opcao_plano_id
    return None


def podar_cenarios_orfaos(rascunho: RascunhoEstudo) -> None:
    """Remove atribuições cuja proposta saiu da seleção; mantém slots ainda vazios."""
    opcoes_ids = {op.id for op in rascunho.opcoes_proposta}
    limpos: list[CenarioRascunho] = []
    for cenario in rascunho.cenarios:
        atribuicoes: list[AtribuicaoRascunho] = []
        for a in cenario.atribuicoes:
            if not a.opcao_plano_id:
                # Slot incompleto (etapa 4 multi) — não é órfão.
                atribuicoes.append(a)
            elif a.opcao_plano_id in opcoes_ids:
                atribuicoes.append(a)
        if atribuicoes:
            limpos.append(cenario.model_copy(update={"atribuicoes": atribuicoes}))
    rascunho.cenarios = limpos


def sincronizar_cenarios_subgrupo_unico(rascunho: RascunhoEstudo) -> None:
    """Um cenário por proposta, todos comparados com o único plano atual."""
    if rascunho.formato == "novo" or len(rascunho.subgrupos_atuais) != 1:
        return

    if not rascunho.opcoes_proposta:
        rascunho.cenarios = []
        return

    sg_id = rascunho.subgrupos_atuais[0].id
    novos: list[CenarioRascunho] = []

    for indice, op in enumerate(rascunho.opcoes_proposta):
        existente = _cenario_da_opcao(rascunho.cenarios, op.id)
        atr_existente = (
            existente.atribuicoes[0] if existente and existente.atribuicoes else None
        )
        novos.append(
            CenarioRascunho(
                id=existente.id if existente else _novo_id("c"),
                rotulo=op.plano_nome or f"Comparativo {indice + 1}",
                atribuicoes=[
                    AtribuicaoRascunho(
                        id=atr_existente.id if atr_existente else _novo_id("a"),
                        alvo_tipo="subgrupo",
                        alvo_id=sg_id,
                        opcao_plano_id=op.id,
                    )
                ],
            )
        )

    rascunho.cenarios = novos


def sincronizar_cenarios_multiplos_subgrupos(rascunho: RascunhoEstudo) -> None:
    """Renovação com vários planos: cenários são montados na etapa 4.

    Não cria nem pré-preenche. A poda de órfãos já rodou em ``sincronizar_cenarios``.
    Estudos gravados (uniforme ou misto) permanecem intactos.
    """
    if rascunho.formato == "novo" or len(rascunho.subgrupos_atuais) <= 1:
        return
    # Intencionalmente vazio — ver docstring.
    return


def sincronizar_cenarios_seguro_novo(rascunho: RascunhoEstudo) -> None:
    """Um cenário por proposta; cada cenário cobre todas as vidas incluídas."""
    if rascunho.formato != "novo":
        return

    if not rascunho.opcoes_proposta:
        rascunho.cenarios = []
        return

    vidas_ids = vidas_incluidas_ids(rascunho)
    if not vidas_ids:
        return

    opcoes_ids = {op.id for op in rascunho.opcoes_proposta}
    novos: list[CenarioRascunho] = []

    for indice, op in enumerate(rascunho.opcoes_proposta):
        existente: CenarioRascunho | None = (
            rascunho.cenarios[indice] if indice < len(rascunho.cenarios) else None
        )
        atribuicoes: list[AtribuicaoRascunho] = []
        for vida_id in vidas_ids:
            atr_existente = None
            if existente:
                atr_existente = next(
                    (
                        a
                        for a in existente.atribuicoes
                        if a.alvo_tipo == "vida" and a.alvo_id == vida_id
                    ),
                    None,
                )
            opcao_celula = op.id
            if (
                atr_existente
                and atr_existente.opcao_plano_id
                and atr_existente.opcao_plano_id in opcoes_ids
            ):
                opcao_celula = atr_existente.opcao_plano_id
            atribuicoes.append(
                AtribuicaoRascunho(
                    id=atr_existente.id if atr_existente else _novo_id("a"),
                    alvo_tipo="vida",
                    alvo_id=vida_id,
                    opcao_plano_id=opcao_celula,
                )
            )

        cenario_novo = CenarioRascunho(
            id=existente.id if existente else _novo_id("c"),
            rotulo=op.plano_nome or f"Comparativo {indice + 1}",
            atribuicoes=atribuicoes,
        )
        novos.append(cenario_novo)

    rascunho.cenarios = novos


def _cenarios_sincronizados_renovacao(rascunho: RascunhoEstudo) -> bool:
    opcoes = rascunho.opcoes_proposta
    if not opcoes or not rascunho.subgrupos_atuais:
        return False

    subgrupos_obrigatorios = set(subgrupos_com_vidas(rascunho))
    if not subgrupos_obrigatorios:
        return False

    opcoes_ids = {op.id for op in opcoes}

    if len(rascunho.subgrupos_atuais) == 1:
        sg_id = rascunho.subgrupos_atuais[0].id
        if len(rascunho.cenarios) != len(opcoes):
            return False
        for cenario in rascunho.cenarios:
            if len(cenario.atribuicoes) != 1:
                return False
            atr = cenario.atribuicoes[0]
            if (
                atr.alvo_tipo != "subgrupo"
                or atr.alvo_id != sg_id
                or atr.opcao_plano_id not in opcoes_ids
            ):
                return False
        return True

    # Multi: o usuário monta N≥1 cenários (não precisa ser 1 por cotação).
    if not rascunho.cenarios:
        return False

    for cenario in rascunho.cenarios:
        atrib_por_sg: dict[str, str] = {}
        for atr in cenario.atribuicoes:
            if atr.alvo_tipo != "subgrupo":
                return False
            if not atr.opcao_plano_id or atr.opcao_plano_id not in opcoes_ids:
                return False
            atrib_por_sg[atr.alvo_id] = atr.opcao_plano_id
        if set(atrib_por_sg.keys()) != subgrupos_obrigatorios:
            return False

    return True


def _cenarios_sincronizados_seguro_novo(rascunho: RascunhoEstudo) -> bool:
    opcoes = rascunho.opcoes_proposta
    if not opcoes:
        return False
    vidas_obrigatorias = set(vidas_incluidas_ids(rascunho))
    if not vidas_obrigatorias:
        return False
    if len(rascunho.cenarios) != len(opcoes):
        return False

    opcoes_ids = {op.id for op in opcoes}
    for cenario in rascunho.cenarios:
        atrib_por_vida: dict[str, str] = {}
        for atr in cenario.atribuicoes:
            if atr.alvo_tipo != "vida":
                return False
            if not atr.opcao_plano_id or atr.opcao_plano_id not in opcoes_ids:
                return False
            atrib_por_vida[atr.alvo_id] = atr.opcao_plano_id
        if set(atrib_por_vida.keys()) != vidas_obrigatorias:
            return False
    return True


def cenarios_sincronizados(rascunho: RascunhoEstudo) -> bool:
    """True quando cada cenário cobre todos os alvos exigidos pelo formato."""
    if rascunho.formato == "novo":
        return _cenarios_sincronizados_seguro_novo(rascunho)
    return _cenarios_sincronizados_renovacao(rascunho)


def sincronizar_cenarios(rascunho: RascunhoEstudo) -> RascunhoEstudo:
    """Poda órfãos; sync automático só em seguro novo e renovação de 1 plano.

    Renovação com vários planos: cenários vêm da etapa 4 (não são gerados aqui).
    """
    podar_cenarios_orfaos(rascunho)
    if rascunho.formato == "novo":
        sincronizar_cenarios_seguro_novo(rascunho)
    elif len(rascunho.subgrupos_atuais) == 1:
        sincronizar_cenarios_subgrupo_unico(rascunho)
    elif len(rascunho.subgrupos_atuais) > 1:
        sincronizar_cenarios_multiplos_subgrupos(rascunho)
    return rascunho


def garantir_cenarios_uniformes_multi(rascunho: RascunhoEstudo) -> None:
    """Fixtures/testes: um cenário por proposta, mesma cotação em todos os planos.

    Não usado pelo sync de produção (etapa 4 monta à mão).
    """
    if rascunho.formato == "novo" or len(rascunho.subgrupos_atuais) <= 1:
        return
    if not rascunho.opcoes_proposta:
        rascunho.cenarios = []
        return
    subgrupos_ids = subgrupos_com_vidas(rascunho)
    if not subgrupos_ids:
        return
    novos: list[CenarioRascunho] = []
    for indice, op in enumerate(rascunho.opcoes_proposta):
        existente = rascunho.cenarios[indice] if indice < len(rascunho.cenarios) else None
        atribuicoes = [
            AtribuicaoRascunho(
                id=_novo_id("a"),
                alvo_tipo="subgrupo",
                alvo_id=sg_id,
                opcao_plano_id=op.id,
            )
            for sg_id in subgrupos_ids
        ]
        cenario_novo = CenarioRascunho(
            id=existente.id if existente else _novo_id("c"),
            rotulo=None,
            atribuicoes=atribuicoes,
        )
        novos.append(
            cenario_novo.model_copy(
                update={"rotulo": rotulo_cenario(rascunho, cenario_novo)}
            )
        )
    rascunho.cenarios = novos
