"""Persistência da seleção de propostas para apresentação (Comparativo)."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo, SelecaoApresentacaoRascunho
from newport_app.models.responses import SalvarSelecaoApresentacaoResponse


class SelecaoApresentacaoInvalidaError(Exception):
    pass


def salvar_selecao_apresentacao(
    rascunho: RascunhoEstudo,
    opcao_ids: list[str],
    *,
    invalidar_confirmacao: bool = True,
) -> SalvarSelecaoApresentacaoResponse:
    validos = {op.id for op in rascunho.opcoes_proposta}
    ordem: list[str] = []
    vistos: set[str] = set()
    for op_id in opcao_ids:
        if op_id not in validos or op_id in vistos:
            continue
        ordem.append(op_id)
        vistos.add(op_id)
    if not ordem and opcao_ids:
        raise SelecaoApresentacaoInvalidaError("Nenhuma proposta válida na seleção.")
    rascunho.selecao_apresentacao = SelecaoApresentacaoRascunho(
        opcao_ids=list(ordem),
        ordem=list(ordem),
    )
    if invalidar_confirmacao:
        rascunho.confirmacao_comparativo = None
    return SalvarSelecaoApresentacaoResponse(opcao_ids=list(ordem), ordem=list(ordem))


def resolver_propostas_apresentacao_snapshot(
    payload: dict,
    solicitadas: list[str] | None = None,
) -> list[str]:
    if solicitadas:
        return list(solicitadas)
    if payload.get("propostas_apresentacao"):
        return list(payload["propostas_apresentacao"])
    comparativo = payload.get("comparativo") or {}
    if comparativo.get("propostas_apresentacao"):
        return list(comparativo["propostas_apresentacao"])
    rascunho = payload.get("rascunho") or {}
    sel = rascunho.get("selecao_apresentacao") or {}
    if sel.get("ordem"):
        return list(sel["ordem"])
    return []


def ordem_apresentacao_rascunho(rascunho: RascunhoEstudo) -> list[str]:
    if rascunho.selecao_apresentacao and rascunho.selecao_apresentacao.ordem:
        return list(rascunho.selecao_apresentacao.ordem)
    if rascunho.selecao_apresentacao and rascunho.selecao_apresentacao.opcao_ids:
        return list(rascunho.selecao_apresentacao.opcao_ids)
    return []
