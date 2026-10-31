"""Inclusão manual de hospital fora dos principais (etapa 5).

A busca varre a BASE INTEIRA (sem recorte geográfico e sem filtro de
especialidade) e **não grava nada**: nem rascunho, nem CSV de principais. A
inclusão vale para o ESTUDO (todas as seções) e fica em `selecao_rede.incluidos`.
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
from newport_app.services.rede_selecao import (
    chave_incluido,
    incluidos_rede,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

LIMITE_RESULTADOS = 30
MIN_CARACTERES_BUSCA = 2


class InclusaoRedeInvalida(ValueError):
    """Pedido de busca/inclusão que não pode ser atendido (mensagem pronta para a UI)."""


def _ids_cenarios(rascunho: RascunhoEstudo) -> list[str]:
    return [c.id for c in rascunho.cenarios] if rascunho.cenarios else []


def _secoes_com_tabela(rascunho: RascunhoEstudo) -> list:
    """Seções que têm localização dos beneficiários (as únicas com tabela de rede)."""
    vistos: set[str] = set()
    out = []
    for sg in rascunho.subgrupos_atuais:
        if sg.id in vistos:
            continue
        vistos.add(sg.id)
        if localizacoes_subgrupo(rascunho, sg.id):
            out.append(sg)
    return out


def _rotulo_secao(sg) -> str:
    return f"Comparativo — {sg.plano_nome}"


def _chave_plano(operadora: str, plano_nome: str) -> str:
    return f"plano:{normalizar_cabecalho(operadora)}:{normalizar_cabecalho(plano_nome)}"


def _colunas_do_estudo(
    rascunho: RascunhoEstudo, base, tabela
) -> tuple[list[ColunaRedeSelecaoItem], list[ColunaManual]]:
    """Um item por plano DISTINTO do estudo (contrato atual de cada seção + propostas)."""
    aliases = carregar_aliases()
    por_idx = {c.col_idx: c for c in base.colunas}
    itens: dict[str, ColunaRedeSelecaoItem] = {}
    manuais: dict[str, ColunaManual] = {}
    vistos_sg: set[str] = set()
    for sg in rascunho.subgrupos_atuais:
        if sg.id in vistos_sg:
            continue
        vistos_sg.add(sg.id)
        cols_meta = _colunas_subgrupo(
            rascunho, sg.id, _ids_cenarios(rascunho), seguro_novo=rascunho.formato == "novo"
        )
        for cm in cols_meta:
            chave = _chave_plano(cm.operadora, cm.plano_nome)
            atual = cm.chave == _CHAVE_ATUAL
            if chave in itens:
                if atual and not itens[chave].contrato_atual:
                    itens[chave] = itens[chave].model_copy(update={"contrato_atual": True})
                continue
            itens[chave] = ColunaRedeSelecaoItem(
                chave=chave,
                operadora=cm.operadora,
                plano_nome=nome_plano_documento(cm.plano_nome),
                contrato_atual=atual,
            )
            res = resolver_casamento_rede(
                cm.operadora, cm.plano_nome, base.colunas, tabela=tabela, aliases=aliases
            )
            if res.estado == EstadoCasamentoRede.SEM_REDE or res.col_idx is None:
                manuais[chave] = ColunaManual(chave=chave, col_idx=None, nao_mapeada=True)
            else:
                col = por_idx.get(res.col_idx)
                manuais[chave] = ColunaManual(
                    chave=chave,
                    col_idx=res.col_idx,
                    operadora_canon=(col.operadora_canon or "") if col else "",
                )
    ordem = sorted(itens, key=lambda k: (not itens[k].contrato_atual,))
    return [itens[k] for k in ordem], [manuais[k] for k in ordem]


def _visao_calculada(rascunho: RascunhoEstudo) -> dict[str, set[str]]:
    """Linhas que cada seção já tem SEM inclusões manuais (principais do recorte)."""
    doc = montar_rede_apresentacao(
        rascunho,
        _ids_cenarios(rascunho),
        formato=rascunho.formato,
        incluir_manuais=False,
    )
    por_secao: dict[str, set[str]] = {}
    if doc is None:
        return por_secao
    for sec in doc.secoes:
        ids = por_secao.setdefault(sec.subgrupo_id, set())
        for bloco in sec.blocos:
            ids.update(ln.linha_id for ln in bloco.linhas)
    return por_secao


def _tem_cobertura(celulas: dict[str, str]) -> bool:
    return any((v or "").strip() and v.strip() != "—" for v in celulas.values())


def _situacao_por_secao(
    p, secoes: list, visao: dict[str, set[str]], manual: bool
) -> tuple[list[str], list[str]]:
    """(seções onde já está, seções onde entraria) para o prestador `p`."""
    ja: list[str] = []
    entra: list[str] = []
    for sg in secoes:
        lid = _id_linha_rede(p.prestador, p.chave_municipio, p.chave[2], subgrupo_id=sg.id)
        if manual or lid in visao.get(sg.id, set()):
            ja.append(_rotulo_secao(sg))
        else:
            entra.append(_rotulo_secao(sg))
    return ja, entra


def buscar_para_inclusao(rascunho: RascunhoEstudo, consulta: str) -> BuscaInclusaoResponse:
    """Busca por nome parcial (sem acento e sem caixa) na base inteira. Só lê."""
    texto = (consulta or "").strip()
    termos = termos_de_busca(texto)
    if len(texto) < MIN_CARACTERES_BUSCA or not termos:
        raise InclusaoRedeInvalida(
            f"Digite ao menos {MIN_CARACTERES_BUSCA} letras do nome do hospital."
        )
    base = carregar_base_rede_hospital()
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base.colunas)
    cols_resp, colunas = _colunas_do_estudo(rascunho, base, tabela)
    secoes = _secoes_com_tabela(rascunho)
    mun_perm: set[str] = set()
    for sg in secoes:
        mun_perm |= set(
            municipios_permitidos(localizacoes_subgrupo(rascunho, sg.id), set(base.municipios))
        )
    visao = _visao_calculada(rascunho)
    manuais_chaves = {chave_incluido(i) for i in incluidos_rede(rascunho)}

    achados = [p for p in base.prestadores if _prestador_casa(p, termos)]
    itens: list[tuple[tuple, ResultadoBuscaInclusao]] = []
    for p in achados:
        ent = principais.por_prestador_matriz.get(p.chave)
        fora = prestador_fora_do_criterio(p)
        celulas = celulas_prestador_manual(p, ent, colunas, fora_criterio=fora)
        zona = ((ent.zona if ent else "") or "").strip() or (p.regiao or "").strip()
        incluido = p.chave in manuais_chaves
        ja, entra = _situacao_por_secao(p, secoes, visao, incluido)
        item = ResultadoBuscaInclusao(
            prestador=p.prestador,
            prestador_nome=nome_prestador_para_rotulo(p.prestador, p.bairro or ""),
            municipio=p.chave_municipio,
            municipio_titulo=_titulo_municipio(p.chave_municipio),
            bairro=p.chave[2],
            zona=zona,
            celulas={k: v for k, v in celulas.items() if v},
            fora_criterio=fora,
            fora_recorte=p.chave_municipio not in mun_perm,
            verticalizado=bool(operadoras_rede_verticalizada(ent.rede_verticalizada if ent else "")),
            ja_na_tabela=bool(secoes) and not entra and not incluido,
            incluido_manual=incluido,
            sem_cobertura=not _tem_cobertura(celulas),
            secoes_ja_presentes=ja,
            secoes_a_incluir=entra,
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
        consulta=texto,
        colunas=cols_resp,
        resultados=resultados,
        total_encontrado=len(achados),
        limite=LIMITE_RESULTADOS,
        aviso=aviso,
    )


def incluir_manual(
    rascunho: RascunhoEstudo,
    prestador: str,
    municipio: str,
    bairro: str = "",
) -> IncluidoRedeRascunho:
    """Acrescenta o prestador ao estudo. Nunca toca o CSV de principais.

    Sem recusa por falta de cobertura: o corretor inclui o hospital que o cliente
    pediu, cubra ou não algum plano — as colunas dizem quem tem acesso.
    """
    secoes = _secoes_com_tabela(rascunho)
    if not secoes:
        raise InclusaoRedeInvalida(
            "Nenhuma seção deste estudo tem localização dos beneficiários; não há tabela para incluir."
        )
    base = carregar_base_rede_hospital()
    alvo = next(
        (p for p in base.prestadores if p.chave == (prestador, municipio, bairro)), None
    )
    if alvo is None:
        raise InclusaoRedeInvalida("Prestador não encontrado na base de rede.")
    inc = IncluidoRedeRascunho(prestador=prestador, municipio=municipio, bairro=bairro)
    if any(chave_incluido(i) == chave_incluido(inc) for i in incluidos_rede(rascunho)):
        raise InclusaoRedeInvalida("Este hospital já foi incluído manualmente.")
    _, entra = _situacao_por_secao(alvo, secoes, _visao_calculada(rascunho), False)
    if not entra:
        raise InclusaoRedeInvalida("Este hospital já está na tabela de todas as seções.")
    atual = rascunho.selecao_rede
    rascunho.selecao_rede = SelecaoRedeRascunho(
        excluidos=list(atual.excluidos) if atual else [],
        incluidos=[*incluidos_rede(rascunho), inc],
        revisada=atual.revisada if atual else False,
    )
    return inc


def remover_inclusao(
    rascunho: RascunhoEstudo,
    prestador: str,
    municipio: str,
    bairro: str = "",
) -> bool:
    """Desfaz a inclusão manual (em todas as seções). Devolve False se não existia."""
    alvo = IncluidoRedeRascunho(prestador=prestador, municipio=municipio, bairro=bairro)
    atual = rascunho.selecao_rede
    restantes = [i for i in incluidos_rede(rascunho) if chave_incluido(i) != chave_incluido(alvo)]
    if atual is None or len(restantes) == len(atual.incluidos):
        return False
    lids = {
        _id_linha_rede(prestador, municipio, bairro, subgrupo_id=sg.id)
        for sg in rascunho.subgrupos_atuais
    }
    excl = [i for i in atual.excluidos if i not in lids]
    if not excl and not restantes and not atual.revisada:
        rascunho.selecao_rede = None
    else:
        rascunho.selecao_rede = SelecaoRedeRascunho(
            excluidos=excl, incluidos=restantes, revisada=atual.revisada
        )
    return True
