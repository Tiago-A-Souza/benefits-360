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


def _nome_opcao(rascunho: RascunhoEstudo, opcao_id: str) -> str:
    op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    if op and op.plano_nome:
        return op.plano_nome
    return opcao_id


def rotulo_cenario(rascunho: RascunhoEstudo, cenario: CenarioRascunho) -> str:
    """Rótulo da coluna do comparativo — único ou pacote misto."""
    if cenario.rotulo:
        return cenario.rotulo

    op_ids: list[str] = []
    vistos: set[str] = set()
    for atr in cenario.atribuicoes:
        if not atr.opcao_plano_id or atr.opcao_plano_id in vistos:
            continue
        vistos.add(atr.opcao_plano_id)
        op_ids.append(atr.opcao_plano_id)

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
    """Remove cenários/atribuições que não correspondem mais a opções do comparativo."""
    opcoes_ids = {op.id for op in rascunho.opcoes_proposta}
    limpos: list[CenarioRascunho] = []
    for cenario in rascunho.cenarios:
        atribuicoes = [
            a for a in cenario.atribuicoes if a.opcao_plano_id in opcoes_ids
        ]
        if atribuicoes:
            limpos.append(cenario.model_copy(update={"atribuicoes": atribuicoes}))
    rascunho.cenarios = limpos


def sincronizar_cenarios_subgrupo_unico(rascunho: RascunhoEstudo) -> None:
    """Um cenário por proposta, todos comparados com o único plano atual."""
    if len(rascunho.subgrupos_atuais) != 1:
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
    """Um cenário por proposta; cada cenário cobre todos os subgrupos com vidas."""
    if len(rascunho.subgrupos_atuais) <= 1:
        return

    if not rascunho.opcoes_proposta:
        rascunho.cenarios = []
        return

    subgrupos_ids = subgrupos_com_vidas(rascunho)
    if not subgrupos_ids:
        return

    opcoes_ids = {op.id for op in rascunho.opcoes_proposta}
    novos: list[CenarioRascunho] = []

    for indice, op in enumerate(rascunho.opcoes_proposta):
        existente: CenarioRascunho | None = (
            rascunho.cenarios[indice] if indice < len(rascunho.cenarios) else None
        )

        atribuicoes: list[AtribuicaoRascunho] = []
        for sg_id in subgrupos_ids:
            atr_existente = None
            if existente:
                atr_existente = next(
                    (a for a in existente.atribuicoes if a.alvo_id == sg_id),
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
                    alvo_tipo="subgrupo",
                    alvo_id=sg_id,
                    opcao_plano_id=opcao_celula,
                )
            )

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


def cenarios_sincronizados(rascunho: RascunhoEstudo) -> bool:
    """True quando cada cenário cobre todos os subgrupos com vidas."""
    opcoes = rascunho.opcoes_proposta
    if not opcoes:
        return False
    if not rascunho.subgrupos_atuais:
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
            if atr.alvo_id != sg_id or atr.opcao_plano_id not in opcoes_ids:
                return False
        return True

    if len(rascunho.cenarios) != len(opcoes):
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


def sincronizar_cenarios(rascunho: RascunhoEstudo) -> RascunhoEstudo:
    """Poda órfãos; recria cenários automaticamente conforme planos atuais."""
    podar_cenarios_orfaos(rascunho)
    if len(rascunho.subgrupos_atuais) == 1:
        sincronizar_cenarios_subgrupo_unico(rascunho)
    elif len(rascunho.subgrupos_atuais) > 1:
        sincronizar_cenarios_multiplos_subgrupos(rascunho)
    return rascunho
