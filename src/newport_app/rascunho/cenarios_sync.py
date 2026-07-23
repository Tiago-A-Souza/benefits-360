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


def cenarios_sincronizados(rascunho: RascunhoEstudo) -> bool:
    """True quando cada proposta tem cenário/atribuição válida com plano atual."""
    opcoes = rascunho.opcoes_proposta
    if not opcoes:
        return False
    if not rascunho.subgrupos_atuais:
        return False

    mapa_opcao_subgrupo: dict[str, str] = {}
    for cenario in rascunho.cenarios:
        for atrib in cenario.atribuicoes:
            if atrib.opcao_plano_id:
                mapa_opcao_subgrupo[atrib.opcao_plano_id] = atrib.alvo_id

    subgrupos_ids = {sg.id for sg in rascunho.subgrupos_atuais}

    if len(rascunho.subgrupos_atuais) == 1:
        sg_id = rascunho.subgrupos_atuais[0].id
        if len(rascunho.cenarios) != len(opcoes):
            return False
        return all(mapa_opcao_subgrupo.get(op.id) == sg_id for op in opcoes)

    return all(
        mapa_opcao_subgrupo.get(op.id) in subgrupos_ids for op in opcoes
    )


def sincronizar_cenarios(rascunho: RascunhoEstudo) -> RascunhoEstudo:
    """Poda órfãos; com um plano atual, recria cenários automaticamente."""
    podar_cenarios_orfaos(rascunho)
    if len(rascunho.subgrupos_atuais) == 1:
        sincronizar_cenarios_subgrupo_unico(rascunho)
    return rascunho
