"""Montagem da aba rede — seções por subgrupo, colunas do cenário."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone

from newport_app.models.draft import CenarioRascunho, RascunhoEstudo
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
from newport_app.presentation.rede_codigos import (
    formatar_cobertura_abreviada,
    sigla_zona_capital,
)
from newport_app.presentation.rede_matriz_hospital import (
    CAMINHO_XLSX_PADRAO,
    carregar_base_rede_hospital,
)
from newport_app.presentation.rede_recorte import parse_municipio_base
from newport_app.presentation.rede_avisos import AVISO_REDE_SEM_LOCALIZACAO
from newport_app.presentation.rede_visao import (
    EstadoMapeamentoPlanoRede,
    estudo_tem_localizacao_rede,
    localizacoes_subgrupo,
    montar_visao_rede_estudo,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_CHAVE_ATUAL = "rede-atual"
_CAPITAIS_COM_ZONA = frozenset({"SP.SAO PAULO", "RJ.RIO DE JANEIRO"})


def _id_linha_rede(
    prestador: str,
    chave_municipio: str,
    bairro: str,
    *,
    subgrupo_id: str = "",
) -> str:
    """Chave estável da seleção: prestador + município + bairro, no escopo do subgrupo."""
    bruto = f"{subgrupo_id}\0{prestador}\0{chave_municipio}\0{bairro}"
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()[:16]


def _chave_coluna_proposta(operadora: str, plano_nome: str) -> str:
    """Uma coluna por plano distinto — vários cenários com o mesmo plano colapsam."""
    return (
        f"prop:{normalizar_cabecalho(operadora)}:"
        f"{normalizar_cabecalho(plano_nome)}"
    )


def _paginas_colunas_rede(
    colunas_doc: list[ColunaRedeApresentacao],
    blocos_out: list[BlocoRedeApresentacao],
) -> list[PaginaRedeApresentacao]:
    """Contrato atual em toda fatia; MAX_PROPOSTAS_POR_PAGINA só nas propostas."""
    atual = [c for c in colunas_doc if c.chave == _CHAVE_ATUAL]
    propostas = [c for c in colunas_doc if c.chave != _CHAVE_ATUAL]
    if not propostas:
        return [PaginaRedeApresentacao(colunas=colunas_doc, blocos=blocos_out)]
    paginas: list[PaginaRedeApresentacao] = []
    for i in range(0, len(propostas), MAX_PROPOSTAS_POR_PAGINA):
        fatia = [*atual, *propostas[i : i + MAX_PROPOSTAS_POR_PAGINA]]
        paginas.append(PaginaRedeApresentacao(colunas=fatia, blocos=blocos_out))
    return paginas


def _valor_conta_cobertura(val: str | None) -> bool:
    if not val or not str(val).strip():
        return False
    return str(val).strip() != "—"


def linha_tem_cobertura_na_secao(
    ln: LinhaRedeApresentacao,
    colunas: list[ColunaRedeApresentacao],
) -> bool:
    """True se alguma coluna da seção (contrato atual ou proposta) tem cobertura."""
    return any(
        _valor_conta_cobertura(ln.celulas.get(c.chave)) for c in colunas
    )


def contagem_coberturas_bloco(
    linhas: list[LinhaRedeApresentacao],
    colunas: list[ColunaRedeApresentacao],
) -> dict[str, int]:
    """Conta células com código visível — mesma regra do renderer HTML."""
    contagem = {c.chave: 0 for c in colunas}
    for ln in linhas:
        for cm in colunas:
            if _valor_conta_cobertura(ln.celulas.get(cm.chave)):
                contagem[cm.chave] += 1
    return contagem


def _cenarios_da_selecao(
    rascunho: RascunhoEstudo, selecao: list[str]
) -> list[CenarioRascunho]:
    """Colunas da apresentação usam `cenario_id` (FASE 4); aceita `opcao_id` legado."""
    if not rascunho.cenarios:
        return []
    if not selecao:
        return [rascunho.cenarios[0]]
    ids_cenario = {c.id for c in rascunho.cenarios}
    ids_opcao = {o.id for o in rascunho.opcoes_proposta}
    out: list[CenarioRascunho] = []
    vistos: set[str] = set()
    for item in selecao:
        if item in ids_cenario and item not in vistos:
            out.append(next(c for c in rascunho.cenarios if c.id == item))
            vistos.add(item)
    for item in selecao:
        if item not in ids_opcao:
            continue
        for cen in rascunho.cenarios:
            if cen.id in vistos:
                continue
            if any(
                atr.opcao_plano_id == item
                for atr in cen.atribuicoes
                if atr.opcao_plano_id
            ):
                out.append(cen)
                vistos.add(cen.id)
                break
    return out


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
    planos_vistos: set[tuple[str, str]] = set()
    for cen in _cenarios_da_selecao(rascunho, propostas_ids):
        opcao_id = None
        for atr in cen.atribuicoes:
            if atr.alvo_tipo == "subgrupo" and atr.alvo_id == subgrupo_id:
                opcao_id = atr.opcao_plano_id
                break
        if not opcao_id:
            continue
        op = next(o for o in rascunho.opcoes_proposta if o.id == opcao_id)
        ch_plano = (op.operadora, op.plano_nome)
        if ch_plano in planos_vistos:
            continue
        planos_vistos.add(ch_plano)
        cols.append(
            ColunaRedeApresentacao(
                chave=_chave_coluna_proposta(op.operadora, op.plano_nome),
                operadora=op.operadora,
                plano_nome=op.plano_nome,
            )
        )
    return cols


def _titulo_bloco(chave_municipio: str) -> str:
    uf, cidade = parse_municipio_base(chave_municipio)
    return f"{cidade.title()} · {uf}"


def _ordenar_municipios(municipios: list[str]) -> list[str]:
    def key(mun: str) -> tuple:
        uf, _ = parse_municipio_base(mun)
        cap = 0 if mun in _CAPITAIS_COM_ZONA else 1
        return (cap, uf, mun)

    return sorted(set(municipios), key=key)


def _ordem_linha_capital(ln: LinhaRedeApresentacao) -> tuple:
    sigla = sigla_zona_capital(ln.zona) if ln.chave_municipio in _CAPITAIS_COM_ZONA else ""
    return (sigla, ln.prestador, ln.bairro)


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
    if not loc:
        sg = next(s for s in rascunho.subgrupos_atuais if s.id == subgrupo_id)
        colunas_doc = list(cols_meta)
        paginas = _paginas_colunas_rede(colunas_doc, [])
        return SecaoRedeApresentacao(
            subgrupo_id=subgrupo_id,
            rotulo=f"Comparativo — {sg.plano_nome}",
            colunas=colunas_doc,
            blocos=[],
            paginas=paginas,
            total_linhas=0,
            sem_localizacao_beneficiarios=True,
        )
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
                    linha_id=_id_linha_rede(
                        pr.prestador,
                        pr.chave_municipio,
                        pr.bairro,
                        subgrupo_id=subgrupo_id,
                    ),
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

    blocos_out: list[BlocoRedeApresentacao] = []
    for mun in _ordenar_municipios(
        [ln.chave_municipio for ln in linhas_map.values()]
    ):
        linhas_bloco = [
            ln
            for ln in linhas_map.values()
            if ln.chave_municipio == mun
            and linha_tem_cobertura_na_secao(ln, cols_meta)
        ]
        if not linhas_bloco:
            continue
        linhas_bloco.sort(key=_ordem_linha_capital)
        contagem = contagem_coberturas_bloco(linhas_bloco, cols_meta)
        blocos_out.append(
            BlocoRedeApresentacao(
                titulo=_titulo_bloco(mun),
                linhas=linhas_bloco,
                contagem_por_coluna=contagem,
            )
        )

    sg = next(s for s in rascunho.subgrupos_atuais if s.id == subgrupo_id)
    paginas = _paginas_colunas_rede(colunas_doc, blocos_out)
    total_visiveis = sum(len(b.linhas) for b in blocos_out)

    return SecaoRedeApresentacao(
        subgrupo_id=subgrupo_id,
        rotulo=f"Comparativo — {sg.plano_nome}",
        colunas=colunas_doc,
        blocos=blocos_out,
        paginas=paginas,
        total_linhas=total_visiveis,
    )


def montar_rede_apresentacao(
    rascunho: RascunhoEstudo,
    propostas_ids: list[str],
    *,
    formato: str = "renovacao",
    excluidos: set[str] | None = None,
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
    aviso = None if estudo_tem_localizacao_rede(rascunho) else AVISO_REDE_SEM_LOCALIZACAO
    doc = RedeApresentacaoDocumento(
        data_base_rede=atualizado,
        secoes=secoes,
        aviso_sem_localizacao=aviso,
    )
    if excluidos:
        from newport_app.services.rede_selecao import aplicar_exclusoes_rede_documento

        doc = aplicar_exclusoes_rede_documento(doc, excluidos)
    return doc
