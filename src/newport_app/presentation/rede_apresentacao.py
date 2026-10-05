"""Montagem da aba rede — seções por subgrupo, colunas do cenário."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    ColunaRedeApresentacao,
    LinhaRedeApresentacao,
    PaginaRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA
from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
from newport_app.presentation.planos_rede import carregar_aliases_rede
from newport_app.presentation.rede_codigos import formatar_cobertura_abreviada
from newport_app.presentation.rede_matriz_hospital import (
    CAMINHO_XLSX_PADRAO,
    carregar_base_rede_hospital,
)
from newport_app.presentation.rede_recorte import parse_municipio_base
from newport_app.presentation.rede_visao import (
    EstadoMapeamentoPlanoRede,
    localizacoes_subgrupo,
    montar_visao_rede_estudo,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_CHAVE_ATUAL = "rede-atual"
_CAPITAIS_COM_ZONA = frozenset({"SP.SAO PAULO", "RJ.RIO DE JANEIRO"})


def _cenario_das_propostas(rascunho: RascunhoEstudo, propostas_ids: list[str]):
    sel = set(propostas_ids)
    for cen in rascunho.cenarios:
        if any(
            atr.opcao_plano_id in sel
            for atr in cen.atribuicoes
            if atr.opcao_plano_id
        ):
            return cen
    return rascunho.cenarios[0] if rascunho.cenarios else None


def _colunas_subgrupo(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    propostas_ids: list[str],
    *,
    seguro_novo: bool,
) -> list[ColunaRedeApresentacao]:
    sg = next(s for s in rascunho.subgrupos_atuais if s.id == subgrupo_id)
    cols: list[ColunaRedeApresentacao] = []
    if not seguro_novo:
        cols.append(
            ColunaRedeApresentacao(
                chave=_CHAVE_ATUAL,
                operadora=sg.operadora,
                plano_nome=sg.plano_nome,
            )
        )
    cenario = _cenario_das_propostas(rascunho, propostas_ids)
    opcao_id = None
    if cenario is not None:
        for atr in cenario.atribuicoes:
            if atr.alvo_tipo == "subgrupo" and atr.alvo_id == subgrupo_id:
                opcao_id = atr.opcao_plano_id
                break
    if opcao_id and opcao_id in propostas_ids:
        op = next(o for o in rascunho.opcoes_proposta if o.id == opcao_id)
        cols.append(
            ColunaRedeApresentacao(
                chave=opcao_id,
                operadora=op.operadora,
                plano_nome=op.plano_nome,
            )
        )
    return cols


def _titulo_bloco(chave_municipio: str, zona: str) -> str:
    uf, cidade = parse_municipio_base(chave_municipio)
    cidade_titulo = cidade.title()
    if chave_municipio in _CAPITAIS_COM_ZONA and zona:
        return f"{cidade_titulo} · {uf} · {zona}"
    return f"{cidade_titulo} · {uf}"


def _ordenar_blocos(chaves: list[tuple[str, str]]) -> list[tuple[str, str]]:
    def key(item: tuple[str, str]) -> tuple:
        mun, zona = item
        uf, _ = parse_municipio_base(mun)
        cap = 0 if mun in _CAPITAIS_COM_ZONA else 1
        return (cap, uf, mun, normalizar_cabecalho(zona))

    return sorted(set(chaves), key=key)


def _montar_secao(
    rascunho: RascunhoEstudo,
    subgrupo_id: str,
    propostas_ids: list[str],
    *,
    seguro_novo: bool,
    base,
    principais,
    tabela,
) -> SecaoRedeApresentacao | None:
    cols_meta = _colunas_subgrupo(
        rascunho, subgrupo_id, propostas_ids, seguro_novo=seguro_novo
    )
    if not cols_meta:
        return None
    planos_vm = [(c.operadora, c.plano_nome) for c in cols_meta]
    loc = localizacoes_subgrupo(rascunho, subgrupo_id)
    visao = montar_visao_rede_estudo(
        rascunho,
        base,
        principais,
        tabela,
        planos=planos_vm,
        localizacoes=loc,
    )
    planos_vis = {f"{p.operadora}\0{p.plano_nome}": p for p in visao.planos}
    colunas_doc: list[ColunaRedeApresentacao] = []
    for cm in cols_meta:
        pl = planos_vis.get(f"{cm.operadora}\0{cm.plano_nome}")
        nao_map = (
            pl is not None
            and pl.estado_mapeamento == EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA
        )
        colunas_doc.append(cm.model_copy(update={"rede_nao_mapeada": nao_map}))

    linhas_map: dict[tuple[str, str, str], LinhaRedeApresentacao] = {}
    for cm in cols_meta:
        pl = planos_vis.get(f"{cm.operadora}\0{cm.plano_nome}")
        if pl is None:
            continue
        for pr in pl.prestadores:
            if not pr.principal:
                continue
            k = (pr.prestador, pr.chave_municipio, pr.bairro)
            if k not in linhas_map:
                linhas_map[k] = LinhaRedeApresentacao(
                    prestador=pr.prestador,
                    chave_municipio=pr.chave_municipio,
                    bairro=pr.bairro,
                    zona=pr.zona,
                )
            celulas = dict(linhas_map[k].celulas)
            if pl.estado_mapeamento == EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA:
                celulas[cm.chave] = "—"
            else:
                celulas[cm.chave] = formatar_cobertura_abreviada(
                    pr.valor_celula, coberto=pr.coberto
                )
            linhas_map[k] = linhas_map[k].model_copy(update={"celulas": celulas})

    blocos_keys: list[tuple[str, str]] = []
    for ln in linhas_map.values():
        z = ln.zona if ln.chave_municipio in _CAPITAIS_COM_ZONA else ""
        blocos_keys.append((ln.chave_municipio, z))

    blocos_out: list[BlocoRedeApresentacao] = []
    for mun, zona in _ordenar_blocos(blocos_keys):
        if mun in _CAPITAIS_COM_ZONA:
            linhas_bloco = [
                ln for ln in linhas_map.values() if ln.chave_municipio == mun and ln.zona == zona
            ]
        else:
            linhas_bloco = [ln for ln in linhas_map.values() if ln.chave_municipio == mun]
        linhas_bloco.sort(key=lambda x: (x.prestador, x.bairro))
        contagem = {cm.chave: 0 for cm in cols_meta}
        for ln in linhas_bloco:
            for cm in cols_meta:
                if ln.celulas.get(cm.chave):
                    contagem[cm.chave] += 1
        blocos_out.append(
            BlocoRedeApresentacao(
                titulo=_titulo_bloco(mun, zona),
                linhas=linhas_bloco,
                contagem_por_coluna=contagem,
            )
        )

    sg = next(s for s in rascunho.subgrupos_atuais if s.id == subgrupo_id)
    paginas: list[PaginaRedeApresentacao] = []
    for i in range(0, len(colunas_doc), MAX_PROPOSTAS_POR_PAGINA):
        fatia = colunas_doc[i : i + MAX_PROPOSTAS_POR_PAGINA]
        paginas.append(PaginaRedeApresentacao(colunas=fatia, blocos=blocos_out))
    if not paginas:
        paginas = [PaginaRedeApresentacao(colunas=colunas_doc, blocos=blocos_out)]

    return SecaoRedeApresentacao(
        subgrupo_id=subgrupo_id,
        rotulo=f"Comparativo — {sg.plano_nome}",
        colunas=colunas_doc,
        blocos=blocos_out,
        paginas=paginas,
        total_linhas=len(linhas_map),
    )


def montar_rede_apresentacao(
    rascunho: RascunhoEstudo,
    propostas_ids: list[str],
    *,
    formato: str = "renovacao",
) -> RedeApresentacaoDocumento | None:
    if not CAMINHO_XLSX_PADRAO.is_file():
        return None
    if not rascunho.subgrupos_atuais:
        return None
    seguro_novo = formato == "novo"
    base = carregar_base_rede_hospital()
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base.colunas)
    secoes: list[SecaoRedeApresentacao] = []
    vistos: set[str] = set()
    for sg in rascunho.subgrupos_atuais:
        if sg.id in vistos:
            continue
        vistos.add(sg.id)
        sec = _montar_secao(
            rascunho,
            sg.id,
            propostas_ids,
            seguro_novo=seguro_novo,
            base=base,
            principais=principais,
            tabela=tabela,
        )
        if sec is not None:
            secoes.append(sec)
    if not secoes:
        return None
    mtime = os.path.getmtime(CAMINHO_XLSX_PADRAO)
    atualizado = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%d/%m/%Y")
    return RedeApresentacaoDocumento(data_base_rede=atualizado, secoes=secoes)
