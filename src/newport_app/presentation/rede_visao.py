"""Visão de rede por estudo — filtro, recorte, principais e cobertura por plano."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from newport_app.models.draft import RascunhoEstudo
from newport_app.presentation.hospitais_principais import BaseHospitaisPrincipais
from newport_app.presentation.planos_rede import (
    EstadoCasamentoRede,
    TabelaPlanosRedeAliases,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_especialidade import (
    celula_passa_filtro_especialidade,
    prestador_passa_filtro_especialidade,
)
from newport_app.presentation.rede_matriz_hospital import BaseRedeHospital
from newport_app.presentation.rede_recorte import (
    ModoRecorteGeografico,
    municipios_permitidos,
)
from newport_app.presentation.regras_comerciais import carregar_aliases
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_REDE_VERTICAL_OPERADORAS: tuple[tuple[str, str], ...] = (
    ("HAPVIDA", "Hapvida"),
    ("NOTREDAME", "NotreDame"),
    ("GNDI", "NotreDame"),
    ("AMIL", "Amil"),
    ("D OR", "Amil"),
    ("DOR", "Amil"),
    ("UNIMED", "Seguros Unimed"),
    ("KORA", "Hapvida"),
    ("SULAMERICA", "SulAmérica"),
    ("SUL AMERICA", "SulAmérica"),
    ("BRADESCO", "Bradesco"),
    ("PORTO", "Porto Seguro"),
    ("ALICE", "Alice"),
)


class EstadoMapeamentoPlanoRede(StrEnum):
    ALIAS = "alias"
    REGRA = "regra"
    REDE_NAO_MAPEADA = "rede_nao_mapeada"


@dataclass(frozen=True)
class PrestadorVisaoRede:
    prestador: str
    chave_municipio: str
    bairro: str
    zona: str
    principal: bool
    coberto: bool
    rede_verticalizada: str
    valor_celula: str | None


@dataclass(frozen=True)
class PlanoVisaoRede:
    operadora: str
    plano_nome: str
    estado_mapeamento: EstadoMapeamentoPlanoRede
    rotulo_coluna: str | None
    col_idx: int | None
    prestadores: tuple[PrestadorVisaoRede, ...]


@dataclass(frozen=True)
class VisaoRedeEstudo:
    total_prestadores_base: int
    apos_recorte_geografico: int
    apos_filtro_especialidade: int
    municipios_permitidos: frozenset[str]
    planos: tuple[PlanoVisaoRede, ...]


def operadoras_rede_verticalizada(rede_verticalizada: str) -> frozenset[str]:
    if not rede_verticalizada or not rede_verticalizada.strip():
        return frozenset()
    norm = normalizar_cabecalho(rede_verticalizada)
    ops: set[str] = set()
    for pedaco, canon in _REDE_VERTICAL_OPERADORAS:
        if pedaco in norm:
            ops.add(canon)
    return frozenset(ops)


def estudo_tem_localizacao_rede(rascunho: RascunhoEstudo) -> bool:
    """True se alguma vida incluída tem UF e cidade para recorte geográfico."""
    return bool(_localizacoes_rascunho(rascunho))


def _localizacoes_rascunho(rascunho: RascunhoEstudo) -> set[tuple[str, str]]:
    loc: set[tuple[str, str]] = set()
    for vida in rascunho.vidas:
        if not vida.incluida:
            continue
        if vida.uf and vida.cidade:
            loc.add((vida.uf.strip().upper(), vida.cidade))
    return loc


def localizacoes_subgrupo(
    rascunho: RascunhoEstudo, subgrupo_id: str
) -> set[tuple[str, str]]:
    loc: set[tuple[str, str]] = set()
    for vida in rascunho.vidas:
        if not vida.incluida or vida.subgrupo_atual_id != subgrupo_id:
            continue
        if vida.uf and vida.cidade:
            loc.add((vida.uf.strip().upper(), vida.cidade))
    return loc


def _filtrar_por_geografia(
    base: BaseRedeHospital,
    localizacoes: set[tuple[str, str]],
    *,
    modo: ModoRecorteGeografico | None = None,
) -> tuple[frozenset[str], tuple]:
    mun_perm = municipios_permitidos(
        localizacoes, set(base.municipios), modo=modo
    )
    prestadores = tuple(p for p in base.prestadores if p.chave_municipio in mun_perm)
    return frozenset(mun_perm), prestadores


def _filtrar_por_especialidade(prestadores: tuple) -> tuple:
    return tuple(
        p for p in prestadores if prestador_passa_filtro_especialidade(p.celulas)
    )


def _coberto_na_coluna(
    prestador,
    col_idx: int,
    operadora_col: str,
    *,
    entrada_principal,
) -> tuple[bool, str | None]:
    valor = prestador.celulas.get(col_idx)
    if not celula_passa_filtro_especialidade(valor):
        return False, None
    ops_vert = operadoras_rede_verticalizada(
        entrada_principal.rede_verticalizada if entrada_principal else ""
    )
    if ops_vert and operadora_col not in ops_vert:
        return False, valor
    return True, valor


def montar_visao_rede_estudo(
    rascunho: RascunhoEstudo,
    base: BaseRedeHospital,
    principais: BaseHospitaisPrincipais,
    tabela_planos: TabelaPlanosRedeAliases,
    *,
    modo_recorte: ModoRecorteGeografico | None = None,
    planos: list[tuple[str, str]] | None = None,
    localizacoes: set[tuple[str, str]] | None = None,
) -> VisaoRedeEstudo:
    """Monta prestadores filtrados e cobertura por plano do cenário."""
    aliases = carregar_aliases()
    if localizacoes is None:
        localizacoes = _localizacoes_rascunho(rascunho)
    mun_perm, pos_geo = _filtrar_por_geografia(
        base, localizacoes, modo=modo_recorte
    )
    pos_esp = _filtrar_por_especialidade(pos_geo)

    if planos is None:
        planos = []
        vistos: set[tuple[str, str]] = set()
        for sg in rascunho.subgrupos_atuais or []:
            ch = (sg.operadora, sg.plano_nome)
            if ch not in vistos:
                vistos.add(ch)
                planos.append(ch)
        for op in rascunho.opcoes_proposta or []:
            ch = (op.operadora, op.plano_nome)
            if ch not in vistos:
                vistos.add(ch)
                planos.append(ch)

    planos_saida: list[PlanoVisaoRede] = []
    colunas = base.colunas
    for operadora_raw, plano_nome in planos:
        res = resolver_casamento_rede(
            operadora_raw,
            plano_nome,
            colunas,
            tabela=tabela_planos,
            aliases=aliases,
        )
        if res.estado == EstadoCasamentoRede.SEM_REDE:
            planos_saida.append(
                PlanoVisaoRede(
                    operadora=operadora_raw,
                    plano_nome=plano_nome,
                    estado_mapeamento=EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA,
                    rotulo_coluna=None,
                    col_idx=None,
                    prestadores=(),
                )
            )
            continue
        estado_map = (
            EstadoMapeamentoPlanoRede.ALIAS
            if res.estado == EstadoCasamentoRede.ALIAS
            else EstadoMapeamentoPlanoRede.REGRA
        )
        col_idx = res.col_idx
        assert col_idx is not None
        col = next(c for c in colunas if c.col_idx == col_idx)
        op_col = col.operadora_canon or ""
        lista_prest: list[PrestadorVisaoRede] = []
        for p in pos_esp:
            ent = principais.por_prestador_matriz.get(p.chave)
            princ = ent.principal if ent else False
            cob, val = _coberto_na_coluna(p, col_idx, op_col, entrada_principal=ent)
            bairro_norm = normalizar_cabecalho(p.bairro) if p.bairro else ""
            regiao_matriz = (p.regiao or "").strip()
            zona_csv = ((ent.zona if ent else "") or "").strip()
            zona_visao = zona_csv or regiao_matriz
            lista_prest.append(
                PrestadorVisaoRede(
                    prestador=p.prestador,
                    chave_municipio=p.chave_municipio,
                    bairro=bairro_norm,
                    zona=zona_visao,
                    principal=princ,
                    coberto=cob,
                    rede_verticalizada=ent.rede_verticalizada if ent else "",
                    valor_celula=val,
                )
            )
        planos_saida.append(
            PlanoVisaoRede(
                operadora=operadora_raw,
                plano_nome=plano_nome,
                estado_mapeamento=estado_map,
                rotulo_coluna=res.rotulo_coluna,
                col_idx=col_idx,
                prestadores=tuple(lista_prest),
            )
        )

    return VisaoRedeEstudo(
        total_prestadores_base=len(base.prestadores),
        apos_recorte_geografico=len(pos_geo),
        apos_filtro_especialidade=len(pos_esp),
        municipios_permitidos=mun_perm,
        planos=tuple(planos_saida),
    )


def contar_funil_anistia(
    base: BaseRedeHospital,
    localizacoes: set[tuple[str, str]],
    *,
    modo: ModoRecorteGeografico | None = None,
) -> dict[str, int]:
    """Contagens para relatório: total → geo → especialidade."""
    total = len(base.prestadores)
    _, pos_geo = _filtrar_por_geografia(base, localizacoes, modo=modo)
    pos_esp = _filtrar_por_especialidade(pos_geo)
    _, pos_geo_somente = _filtrar_por_geografia(
        base,
        localizacoes,
        modo=ModoRecorteGeografico.SOMENTE_MUNICIPIO,
    )
    return {
        "total_base": total,
        "apos_municipio_beneficiario": len(pos_geo_somente),
        "apos_municipio_e_capital": len(pos_geo),
        "apos_especialidade": len(pos_esp),
    }
