"""Montagem da etapa 5 — dados para a UI de seleção de rede."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    BlocoRedeSelecaoItem,
    ColunaRedeSelecaoItem,
    LinhaRedeSelecaoItem,
    RedeSelecaoResponse,
    SecaoRedeSelecaoItem,
)
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_codigos import sigla_zona_capital
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.presentation.rede_prestador_rotulo import nome_prestador_para_rotulo
from newport_app.services.rede_selecao import excluidos_rede

_CAPITAIS_COM_ZONA = frozenset({"SP.SAO PAULO", "RJ.RIO DE JANEIRO"})
_CHAVE_ATUAL = "rede-atual"


def _prestador_nome_ui(prestador: str, bairro: str, chave_municipio: str, zona: str) -> str:
    nome = nome_prestador_para_rotulo(prestador, bairro or "")
    if chave_municipio in _CAPITAIS_COM_ZONA:
        sigla = sigla_zona_capital(zona or "")
        if sigla:
            nome = f"{sigla} {nome}".strip()
    return nome


def _ids_cenarios_rede(rascunho: RascunhoEstudo) -> list[str]:
    if rascunho.cenarios:
        return [c.id for c in rascunho.cenarios]
    return []


def montar_rede_selecao_ui(rascunho: RascunhoEstudo) -> RedeSelecaoResponse:
    excl = excluidos_rede(rascunho)
    sel = rascunho.selecao_rede
    propostas = _ids_cenarios_rede(rascunho)
    doc = montar_rede_apresentacao(rascunho, propostas, formato=rascunho.formato)
    if doc is None:
        return RedeSelecaoResponse(
            revisada=bool(sel and sel.revisada),
            excluidos=sorted(excl),
        )
    secoes: list[SecaoRedeSelecaoItem] = []
    for sec in doc.secoes:
        colunas = [
            ColunaRedeSelecaoItem(
                chave=c.chave,
                operadora=c.operadora,
                plano_nome=nome_plano_documento(c.plano_nome),
                contrato_atual=c.chave == _CHAVE_ATUAL,
            )
            for c in sec.colunas
        ]
        blocos: list[BlocoRedeSelecaoItem] = []
        for bloco in sec.blocos:
            linhas = [
                LinhaRedeSelecaoItem(
                    linha_id=ln.linha_id,
                    prestador=ln.prestador,
                    municipio=ln.chave_municipio,
                    bairro=ln.bairro or "",
                    zona=ln.zona or "",
                    prestador_nome=_prestador_nome_ui(
                        ln.prestador, ln.bairro or "", ln.chave_municipio, ln.zona or ""
                    ),
                    incluido=ln.linha_id not in excl,
                    celulas=dict(ln.celulas),
                )
                for ln in bloco.linhas
            ]
            blocos.append(BlocoRedeSelecaoItem(titulo=bloco.titulo, linhas=linhas))
        secoes.append(
            SecaoRedeSelecaoItem(
                rotulo=sec.rotulo,
                sem_localizacao=sec.sem_localizacao_beneficiarios,
                colunas=colunas,
                blocos=blocos,
            )
        )
    return RedeSelecaoResponse(
        aviso_sem_localizacao=doc.aviso_sem_localizacao,
        revisada=bool(sel and sel.revisada),
        excluidos=sorted(excl),
        secoes=secoes,
    )


def todos_ids_linha_rede(rascunho: RascunhoEstudo) -> set[str]:
    ui = montar_rede_selecao_ui(rascunho)
    ids: set[str] = set()
    for sec in ui.secoes:
        for bloco in sec.blocos:
            for ln in bloco.linhas:
                ids.add(ln.linha_id)
    return ids
