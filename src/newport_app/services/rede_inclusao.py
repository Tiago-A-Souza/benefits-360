"""Inclusão manual de hospital fora dos principais (etapa 5).

A busca varre a BASE INTEIRA (sem recorte geográfico e sem filtro de
especialidade) e **não grava nada**: nem rascunho, nem CSV de principais. A
inclusão é por seção (subgrupo) e por estudo; fica em `selecao_rede.incluidos`.
"""

from __future__ import annotations

from newport_app.models.draft import (
    IncluidoRedeRascunho,
    RascunhoEstudo,
    SelecaoRedeRascunho,
)
from newport_app.models.responses import (
    BuscaInclusaoResponse,
    ColunaRedeSelecaoItem,
    ResultadoBuscaInclusao,
)
from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
from newport_app.presentation.planos_rede import (
    EstadoCasamentoRede,
    carregar_aliases_rede,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_apresentacao import (
    _CHAVE_ATUAL,
    _colunas_subgrupo,
    _id_linha_rede,
    montar_rede_apresentacao,
)
from newport_app.presentation.rede_consulta import (
    _prestador_casa,
    _titulo_municipio,
    termos_de_busca,
)
from newport_app.presentation.rede_inclusao_manual import (
    ColunaManual,
    celulas_prestador_manual,
    prestador_fora_do_criterio,
)
from newport_app.presentation.rede_matriz_hospital import carregar_base_rede_hospital
from newport_app.presentation.rede_prestador_rotulo import nome_prestador_para_rotulo
from newport_app.presentation.rede_recorte import municipios_permitidos
from newport_app.presentation.rede_visao import (
    localizacoes_subgrupo,
    operadoras_rede_verticalizada,
)
from newport_app.presentation.regras_comerciais import carregar_aliases
from newport_app.services.rede_selecao import incluidos_rede, linha_id_incluido

LIMITE_RESULTADOS = 30
MIN_CARACTERES_BUSCA = 2


class InclusaoRedeInvalida(ValueError):
    """Pedido de busca/inclusão que não pode ser atendido (mensagem pronta para a UI)."""


def _subgrupo(rascunho: RascunhoEstudo, subgrupo_id: str):
    sg = next((s for s in rascunho.subgrupos_atuais if s.id == subgrupo_id), None)
    if sg is None:
        raise InclusaoRedeInvalida("Seção não encontrada neste estudo.")
    return sg


def _ids_cenarios(rascunho: RascunhoEstudo) -> list[str]:
    return [c.id for c in rascunho.cenarios] if rascunho.cenarios else []


def _colunas_da_secao(
    rascunho: RascunhoEstudo, subgrupo_id: str, base, tabela
) -> tuple[list, list[ColunaManual]]:
    """Colunas de plano da seção (as mesmas da tabela) casadas com a base de rede."""
    cols_meta = _colunas_subgrupo(
        rascunho,
        subgrupo_id,
        _ids_cenarios(rascunho),
        seguro_novo=rascunho.formato == "novo",
    )
    aliases = carregar_aliases()
    por_idx = {c.col_idx: c for c in base.colunas}
    manuais: list[ColunaManual] = []
    for cm in cols_meta:
        res = resolver_casamento_rede(
            cm.operadora, cm.plano_nome, base.colunas, tabela=tabela, aliases=aliases
        )
        if res.estado == EstadoCasamentoRede.SEM_REDE or res.col_idx is None:
            manuais.append(ColunaManual(chave=cm.chave, col_idx=None, nao_mapeada=True))
            continue
        col = por_idx.get(res.col_idx)
        manuais.append(
            ColunaManual(
                chave=cm.chave,
                col_idx=res.col_idx,
                operadora_canon=(col.operadora_canon or "") if col else "",
            )
        )
    return cols_meta, manuais


def _ids_visao_calculada_secao(rascunho: RascunhoEstudo, subgrupo_id: str) -> set[str]:
    """Linhas que a seção já tem SEM inclusões manuais (principais do recorte)."""
    doc = montar_rede_apresentacao(
        rascunho,
        _ids_cenarios(rascunho),
        formato=rascunho.formato,
        incluir_manuais=False,
    )
    ids: set[str] = set()
    if doc is None:
        return ids
    for sec in doc.secoes:
        if sec.subgrupo_id != subgrupo_id:
            continue
        for bloco in sec.blocos:
            ids.update(ln.linha_id for ln in bloco.linhas)
    return ids


def _tem_cobertura(celulas: dict[str, str]) -> bool:
    return any((v or "").strip() and v.strip() != "—" for v in celulas.values())


def buscar_para_inclusao(
    rascunho: RascunhoEstudo, subgrupo_id: str, consulta: str
) -> BuscaInclusaoResponse:
    """Busca por nome parcial (sem acento e sem caixa) na base inteira. Só lê."""
    _subgrupo(rascunho, subgrupo_id)
    texto = (consulta or "").strip()
    termos = termos_de_busca(texto)
    if len(texto) < MIN_CARACTERES_BUSCA or not termos:
        raise InclusaoRedeInvalida(
            f"Digite ao menos {MIN_CARACTERES_BUSCA} letras do nome do hospital."
        )
    base = carregar_base_rede_hospital()
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base.colunas)
    cols_meta, colunas = _colunas_da_secao(rascunho, subgrupo_id, base, tabela)
    loc = localizacoes_subgrupo(rascunho, subgrupo_id)
    mun_perm = municipios_permitidos(loc, set(base.municipios))
    visao_ids = _ids_visao_calculada_secao(rascunho, subgrupo_id)
    manuais_ids = {
        linha_id_incluido(i) for i in incluidos_rede(rascunho) if i.subgrupo_id == subgrupo_id
    }

    achados = [p for p in base.prestadores if _prestador_casa(p, termos)]
    itens: list[tuple[tuple, ResultadoBuscaInclusao]] = []
    for p in achados:
        ent = principais.por_prestador_matriz.get(p.chave)
        fora = prestador_fora_do_criterio(p)
        celulas = celulas_prestador_manual(p, ent, colunas, fora_criterio=fora)
        lid = _id_linha_rede(p.prestador, p.chave_municipio, p.chave[2], subgrupo_id=subgrupo_id)
        zona = ((ent.zona if ent else "") or "").strip() or (p.regiao or "").strip()
        fora_recorte = p.chave_municipio not in mun_perm
        item = ResultadoBuscaInclusao(
            prestador=p.prestador,
            prestador_nome=nome_prestador_para_rotulo(p.prestador, p.bairro or ""),
            municipio=p.chave_municipio,
            municipio_titulo=_titulo_municipio(p.chave_municipio),
            bairro=p.chave[2],
            zona=zona,
            celulas={k: v for k, v in celulas.items() if v},
            fora_criterio=fora,
            fora_recorte=fora_recorte,
            verticalizado=bool(operadoras_rede_verticalizada(ent.rede_verticalizada if ent else "")),
            ja_na_tabela=lid in visao_ids,
            incluido_manual=lid in manuais_ids,
            sem_cobertura=not _tem_cobertura(celulas),
        )
        ordem = (item.fora_recorte, item.sem_cobertura, p.prestador, p.chave_municipio, item.bairro)
        itens.append((ordem, item))
    itens.sort(key=lambda t: t[0])
    resultados = [i for _, i in itens[:LIMITE_RESULTADOS]]
    aviso = None
    if not achados:
        aviso = "Nenhum prestador da base corresponde à busca."
    elif len(achados) > LIMITE_RESULTADOS:
        aviso = (
            f"{len(achados)} prestadores encontrados — mostrando os "
            f"{LIMITE_RESULTADOS} primeiros. Refine o nome para ver os demais."
        )
    return BuscaInclusaoResponse(
        subgrupo_id=subgrupo_id,
        consulta=texto,
        colunas=[
            ColunaRedeSelecaoItem(
                chave=cm.chave,
                operadora=cm.operadora,
                plano_nome=nome_plano_documento(cm.plano_nome),
                contrato_atual=cm.chave == _CHAVE_ATUAL,
            )
            for cm in cols_meta
        ],
        resultados=resultados,
        total_encontrado=len(achados),
        limite=LIMITE_RESULTADOS,
        aviso=aviso,
    )


def incluir_manual(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    prestador: str,
    municipio: str,
    bairro: str = "",
) -> IncluidoRedeRascunho:
    """Acrescenta o prestador à seção. Por estudo: nunca toca o CSV de principais."""
    _subgrupo(rascunho, subgrupo_id)
    if not localizacoes_subgrupo(rascunho, subgrupo_id):
        raise InclusaoRedeInvalida(
            "Esta seção não tem localização dos beneficiários; não há tabela para incluir."
        )
    base = carregar_base_rede_hospital()
    alvo = next(
        (p for p in base.prestadores if p.chave == (prestador, municipio, bairro)), None
    )
    if alvo is None:
        raise InclusaoRedeInvalida("Prestador não encontrado na base de rede.")
    inc = IncluidoRedeRascunho(
        subgrupo_id=subgrupo_id, prestador=prestador, municipio=municipio, bairro=bairro
    )
    lid = linha_id_incluido(inc)
    if any(linha_id_incluido(i) == lid for i in incluidos_rede(rascunho)):
        raise InclusaoRedeInvalida("Este prestador já foi incluído manualmente nesta seção.")
    if lid in _ids_visao_calculada_secao(rascunho, subgrupo_id):
        raise InclusaoRedeInvalida("Este prestador já está na tabela desta seção.")
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base.colunas)
    _, colunas = _colunas_da_secao(rascunho, subgrupo_id, base, tabela)
    ent = principais.por_prestador_matriz.get(alvo.chave)
    celulas = celulas_prestador_manual(
        alvo, ent, colunas, fora_criterio=prestador_fora_do_criterio(alvo)
    )
    if not _tem_cobertura(celulas):
        raise InclusaoRedeInvalida(
            "Nenhum plano desta seção cobre este hospital."
        )
    atual = rascunho.selecao_rede
    rascunho.selecao_rede = SelecaoRedeRascunho(
        excluidos=list(atual.excluidos) if atual else [],
        incluidos=[*incluidos_rede(rascunho), inc],
        revisada=atual.revisada if atual else False,
    )
    return inc


def remover_inclusao(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    prestador: str,
    municipio: str,
    bairro: str = "",
) -> bool:
    """Desfaz a inclusão manual. Devolve False se ela não existia."""
    alvo = IncluidoRedeRascunho(
        subgrupo_id=subgrupo_id, prestador=prestador, municipio=municipio, bairro=bairro
    )
    lid = linha_id_incluido(alvo)
    atual = rascunho.selecao_rede
    restantes = [i for i in incluidos_rede(rascunho) if linha_id_incluido(i) != lid]
    if atual is None or len(restantes) == len(atual.incluidos):
        return False
    excl = [i for i in atual.excluidos if i != lid]
    if not excl and not restantes and not atual.revisada:
        rascunho.selecao_rede = None
    else:
        rascunho.selecao_rede = SelecaoRedeRascunho(
            excluidos=excl, incluidos=restantes, revisada=atual.revisada
        )
    return True
