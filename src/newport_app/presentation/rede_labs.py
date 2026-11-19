"""Visão de laboratórios do estudo — recorte, marcas e cobertura binária."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from newport_app.models.presentation import (
    BlocoLabsApresentacao,
    ColunaRedeApresentacao,
    LinhaLabApresentacao,
)
from newport_app.presentation.laboratorios_principais import (
    BaseLaboratoriosPrincipais,
    casar_unidades_marca,
)
from newport_app.presentation.planos_rede import (
    ColunaRede,
    EstadoCasamentoRede,
    TabelaPlanosRedeAliases,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_matriz_laboratorio import (
    BaseRedeLaboratorio,
    PrestadorRedeLaboratorio,
)
from newport_app.presentation.rede_recorte import (
    ModoRecorteGeografico,
    municipios_permitidos,
)
from newport_app.presentation.rede_visao import EstadoMapeamentoPlanoRede
from newport_app.presentation.regras_comerciais import carregar_aliases


@dataclass(frozen=True)
class ColunaLabCasada:
    operadora: str
    plano_nome: str
    estado: EstadoMapeamentoPlanoRede
    col_idx: int | None
    rotulo_coluna: str | None


def casar_planos_laboratorio(
    planos: Iterable[tuple[str, str]],
    colunas: Iterable[ColunaRede],
    tabela: TabelaPlanosRedeAliases,
) -> tuple[ColunaLabCasada, ...]:
    """Mesmo casamento da rede hospitalar — as 189 colunas são idênticas."""
    aliases = carregar_aliases()
    cols = tuple(colunas)
    saida: list[ColunaLabCasada] = []
    for operadora_raw, plano_nome in planos:
        res = resolver_casamento_rede(
            operadora_raw,
            plano_nome,
            cols,
            tabela=tabela,
            aliases=aliases,
        )
        if res.estado == EstadoCasamentoRede.SEM_REDE:
            saida.append(
                ColunaLabCasada(
                    operadora=operadora_raw,
                    plano_nome=plano_nome,
                    estado=EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA,
                    col_idx=None,
                    rotulo_coluna=None,
                )
            )
            continue
        estado = (
            EstadoMapeamentoPlanoRede.ALIAS
            if res.estado == EstadoCasamentoRede.ALIAS
            else EstadoMapeamentoPlanoRede.REGRA
        )
        saida.append(
            ColunaLabCasada(
                operadora=operadora_raw,
                plano_nome=plano_nome,
                estado=estado,
                col_idx=res.col_idx,
                rotulo_coluna=res.rotulo_coluna,
            )
        )
    return tuple(saida)


def recortar_laboratorios(
    base: BaseRedeLaboratorio,
    localizacoes: set[tuple[str, str]],
    *,
    modo: ModoRecorteGeografico | None = None,
) -> tuple[frozenset[str], tuple[PrestadorRedeLaboratorio, ...]]:
    """Município das vidas + capital da UF, igual ao hospital. Sem filtro de especialidade."""
    mun_perm = municipios_permitidos(
        localizacoes, set(base.municipios), modo=modo
    )
    prestadores = tuple(
        p for p in base.prestadores if p.chave_municipio in mun_perm
    )
    return frozenset(mun_perm), prestadores


MARCA_COBERTURA = "✓"


def _celula_preenchida(valor: str | None) -> bool:
    return bool(valor and str(valor).strip())


def fatiar_bloco_labs(
    bloco: BlocoLabsApresentacao | None,
    colunas: list[ColunaRedeApresentacao],
) -> BlocoLabsApresentacao | None:
    if bloco is None or not bloco.linhas:
        return None
    chaves = [c.chave for c in colunas]
    linhas: list[LinhaLabApresentacao] = []
    for ln in bloco.linhas:
        celulas = {ch: ln.celulas.get(ch, "") for ch in chaves}
        linhas.append(LinhaLabApresentacao(marca=ln.marca, celulas=celulas))
    contagem = {ch: 0 for ch in chaves}
    for ln in linhas:
        for ch in chaves:
            val = ln.celulas.get(ch, "")
            if val and val != "—":
                contagem[ch] += 1
    return BlocoLabsApresentacao(linhas=linhas, contagem_por_coluna=contagem)


def montar_bloco_labs(
    colunas: list[ColunaRedeApresentacao],
    *,
    localizacoes: set[tuple[str, str]],
    base: BaseRedeLaboratorio,
    marcas: BaseLaboratoriosPrincipais,
    tabela: TabelaPlanosRedeAliases,
    modo_recorte: ModoRecorteGeografico | None = None,
) -> BlocoLabsApresentacao | None:
    """Uma linha por marca do CSV, na ordem do arquivo. None se nenhuma marca no recorte."""
    if not localizacoes or not colunas:
        return None
    _mun, no_recorte = recortar_laboratorios(
        base, localizacoes, modo=modo_recorte
    )
    if not no_recorte:
        return None
    pares = casar_unidades_marca(no_recorte, marcas.marcas)
    por_marca: dict[str, list] = defaultdict(list)
    for u in pares:
        por_marca[u.marca].append(u.prestador)
    casadas = casar_planos_laboratorio(
        [(c.operadora, c.plano_nome) for c in colunas],
        base.colunas,
        tabela,
    )
    col_casada = {
        (c.operadora, c.plano_nome): c for c in casadas
    }
    linhas: list[LinhaLabApresentacao] = []
    for marca in marcas.marcas:
        if not marca.ativo:
            continue
        unidades = por_marca.get(marca.marca, [])
        if not unidades:
            continue
        celulas: dict[str, str] = {}
        for col in colunas:
            info = col_casada.get((col.operadora, col.plano_nome))
            if col.rede_nao_mapeada or info is None or info.col_idx is None:
                celulas[col.chave] = "—"
                continue
            cobre = any(
                _celula_preenchida(u.celulas.get(info.col_idx)) for u in unidades
            )
            celulas[col.chave] = MARCA_COBERTURA if cobre else ""
        linhas.append(LinhaLabApresentacao(marca=marca.marca, celulas=celulas))
    if not linhas:
        return None
    contagem = {c.chave: 0 for c in colunas}
    for ln in linhas:
        for c in colunas:
            val = ln.celulas.get(c.chave, "")
            if val and val != "—":
                contagem[c.chave] += 1
    return BlocoLabsApresentacao(linhas=linhas, contagem_por_coluna=contagem)
