"""Equivalência plano da cotação → coluna da base de rede (CSV + regra automática)."""

from __future__ import annotations

import csv
import os
from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Iterable

from newport_app.presentation.casamento_rede import (
    chave_casamento_rede,
    flags_chave_casamento,
)
from newport_app.presentation.regras_comerciais import (
    OPERADORAS_RECONHECIVEIS,
    carregar_aliases,
    reconhecer_operadora,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_DOCS = Path(__file__).resolve().parents[3] / "docs"
CAMINHO_ALIASES = _DOCS / "planos_rede_aliases.csv"

ALIASES_OPERADORA_ESTUDO: dict[str, str] = {
    "HAPVIDA NDI": "NotreDame",
    "HAPVIDA": "Hapvida",
    "GNDI": "NotreDame",
    "SUL AMERICA": "SulAmérica",
    "SULAMERICA": "SulAmérica",
}

FLAGS_CASAMENTO_REDE: dict = {
    "strip_op_prefix": True,
    "strip_copart": True,
    "strip_reembolso_sul": True,
    "strip_paren": True,
    "ignore_acom_advance": True,
    "acom_full": True,
    "alias_hapvida": True,
}


class BasePlanosRedeInvalida(ValueError):
    """CSV malformado ou coluna inexistente — mensagem cita o registro."""


class EstadoCasamentoRede(StrEnum):
    ALIAS = "alias"
    REGRA = "regra"
    SEM_REDE = "sem_rede"


@dataclass(frozen=True)
class ColunaRede:
    operadora_raw: str
    operadora_canon: str
    linha: str
    plano: str
    col_idx: int

    @property
    def rotulo_completo(self) -> str:
        if self.linha:
            return f"{self.linha} {self.plano}".strip()
        return self.plano


@dataclass(frozen=True)
class EntradaAliasRede:
    operadora: str
    plano_cotacao: str
    coluna_rede: str
    fonte: str
    atualizado_em: str
    rotulo_coluna: str
    col_idx: int


@dataclass(frozen=True)
class ResultadoCasamentoRede:
    estado: EstadoCasamentoRede
    rotulo_coluna: str | None = None
    col_idx: int | None = None


@dataclass(frozen=True)
class TabelaPlanosRedeAliases:
    entradas: tuple[EntradaAliasRede, ...]
    por_plano: dict[tuple[str, str], EntradaAliasRede]


def _abrir_csv(caminho: Path) -> list[tuple[int, list[str]]]:
    if not caminho.is_file():
        raise BasePlanosRedeInvalida(f"arquivo ausente: {caminho}")
    registros: list[tuple[int, list[str]]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        for indice, row in enumerate(leitor, start=1):
            registros.append((indice, row))
    return registros


def reconhecer_operadora_rede(
    nome: str | None,
    aliases: dict[str, str] | None = None,
    *,
    extra_estudo: bool = True,
) -> str | None:
    mapa = aliases if aliases is not None else carregar_aliases()
    canon = reconhecer_operadora(nome, mapa)
    if canon:
        return canon
    if not extra_estudo or nome is None:
        return None
    chave = normalizar_cabecalho(nome)
    return ALIASES_OPERADORA_ESTUDO.get(chave) or mapa.get(chave)


def colunas_por_sufixo(
    operadora: str,
    sufixo: str,
    colunas: Iterable[ColunaRede],
) -> list[ColunaRede]:
    """Casa sufixo abreviado ao final do rótulo (ou célula plano), na operadora."""
    alvo = normalizar_cabecalho(sufixo)
    if not alvo:
        return []
    hits: list[ColunaRede] = []
    vistos: set[int] = set()
    for col in colunas:
        if col.operadora_canon != operadora:
            continue
        for rotulo in (col.rotulo_completo, col.plano):
            norm = normalizar_cabecalho(rotulo)
            if norm.endswith(alvo) or norm == alvo:
                if col.col_idx not in vistos:
                    vistos.add(col.col_idx)
                    hits.append(col)
                break
    return hits


def carregar_colunas_rede_xlsx(caminho: Path, aliases: dict[str, str] | None = None) -> tuple[ColunaRede, ...]:
    from openpyxl import load_workbook

    mapa = aliases if aliases is not None else carregar_aliases()
    wb = load_workbook(caminho, read_only=True, data_only=True)
    try:
        ws = wb["Matriz_Hospital"]
        rows = list(ws.iter_rows(min_row=1, max_row=4, values_only=True))
    finally:
        wb.close()
    if len(rows) < 4:
        raise BasePlanosRedeInvalida(f"{caminho}: aba Matriz_Hospital incompleta")
    _, op_row, linha_row, plano_row = rows
    saida: list[ColunaRede] = []
    for col in range(5, len(plano_row)):
        plano_cel = plano_row[col]
        if plano_cel is None or str(plano_cel).strip() == "":
            continue
        op_raw = str(op_row[col] or "").strip()
        linha = str(linha_row[col] or "").strip()
        plano = str(plano_cel).strip()
        op_can = reconhecer_operadora_rede(op_raw, mapa) or ""
        saida.append(
            ColunaRede(
                operadora_raw=op_raw,
                operadora_canon=op_can,
                linha=linha,
                plano=plano,
                col_idx=col,
            )
        )
    return tuple(saida)


def caminho_base_rede_padrao() -> Path | None:
    env = os.environ.get("NEWPORT_REDE_XLSX", "").strip()
    if env:
        p = Path(env)
        return p if p.is_file() else None
    padrao = Path(
        r"C:\Users\tiago\Downloads\SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"
    )
    return padrao if padrao.is_file() else None


def carregar_aliases_rede(
    caminho: Path | None = None,
    *,
    colunas_rede: Iterable[ColunaRede] | None = None,
) -> TabelaPlanosRedeAliases:
    origem = caminho or CAMINHO_ALIASES
    registros = _abrir_csv(origem)
    if not registros:
        raise BasePlanosRedeInvalida(f"{origem}: arquivo vazio")
    cab = [c.strip() for c in registros[0][1]]
    esperado = ["operadora", "plano_cotacao", "coluna_rede", "fonte", "atualizado_em"]
    if cab != esperado:
        raise BasePlanosRedeInvalida(
            f"{origem}: registro 1: cabeçalho deve ser {';'.join(esperado)}, "
            f"obtido {cab!r}"
        )
    catalogo = tuple(colunas_rede) if colunas_rede is not None else None
    entradas: list[EntradaAliasRede] = []
    indice_plano: dict[tuple[str, str], EntradaAliasRede] = {}
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BasePlanosRedeInvalida(f"{origem}: registro {indice}: linha vazia")
        if len(row) != 5:
            raise BasePlanosRedeInvalida(
                f"{origem}: registro {indice}: esperado 5 colunas, obtido {len(row)}"
            )
        operadora, plano_cotacao, coluna_rede, fonte, atualizado_em = (
            c.strip() for c in row
        )
        if operadora not in OPERADORAS_RECONHECIVEIS:
            raise BasePlanosRedeInvalida(
                f"{origem}: registro {indice}: operadora fora da lista canônica: "
                f"{operadora!r}"
            )
        if not plano_cotacao or not coluna_rede:
            raise BasePlanosRedeInvalida(
                f"{origem}: registro {indice}: plano ou coluna_rede vazio"
            )
        chave_plano = normalizar_cabecalho(plano_cotacao)
        if not chave_plano:
            raise BasePlanosRedeInvalida(
                f"{origem}: registro {indice}: plano_cotacao normaliza para vazio"
            )
        chave = (operadora, chave_plano)
        if chave in indice_plano:
            raise BasePlanosRedeInvalida(
                f"{origem}: registro {indice}: duplicata "
                f"({operadora!r}, {plano_cotacao!r})"
            )
        rotulo_coluna = ""
        col_idx = -1
        if catalogo is not None:
            casados = colunas_por_sufixo(operadora, coluna_rede, catalogo)
            if len(casados) == 0:
                raise BasePlanosRedeInvalida(
                    f"{origem}: registro {indice}: coluna_rede {coluna_rede!r} "
                    f"não existe na base para {operadora!r}"
                )
            if len(casados) > 1:
                rotulos = ", ".join(c.rotulo_completo for c in casados[:5])
                raise BasePlanosRedeInvalida(
                    f"{origem}: registro {indice}: coluna_rede {coluna_rede!r} "
                    f"ambígua para {operadora!r}: {rotulos}"
                )
            rotulo_coluna = casados[0].rotulo_completo
            col_idx = casados[0].col_idx
        entrada = EntradaAliasRede(
            operadora=operadora,
            plano_cotacao=plano_cotacao,
            coluna_rede=coluna_rede,
            fonte=fonte,
            atualizado_em=atualizado_em,
            rotulo_coluna=rotulo_coluna,
            col_idx=col_idx,
        )
        entradas.append(entrada)
        indice_plano[chave] = entrada
    return TabelaPlanosRedeAliases(
        entradas=tuple(entradas),
        por_plano=indice_plano,
    )


def indexar_rede_automatica(
    colunas: Iterable[ColunaRede],
    flags: dict | None = None,
    aliases: dict[str, str] | None = None,
) -> dict[tuple, list[ColunaRede]]:
    fl = flags if flags is not None else FLAGS_CASAMENTO_REDE
    fk = flags_chave_casamento(fl)
    idx: dict[tuple, list[ColunaRede]] = defaultdict(list)
    for col in colunas:
        op = col.operadora_canon or reconhecer_operadora_rede(
            col.operadora_raw, aliases, extra_estudo=fl.get("alias_hapvida", True)
        )
        if not op:
            continue
        k = chave_casamento_rede(op, col.plano, **fk)
        idx[k].append(col)
        if fl.get("ignore_acom_advance") and op == "NotreDame":
            acom, linha, nucleo = k[1], k[2], k[3]
            if linha == "ADVANCE":
                k2 = (op, "", linha, nucleo)
                if k2 != k:
                    idx[k2].append(col)
    return idx


def _candidatos_regra(
    idx: dict[tuple, list[ColunaRede]],
    k: tuple,
    flags: dict,
) -> list[ColunaRede]:
    op, acom, linha, nucleo = k
    tentativas = [k]
    if acom:
        tentativas.append((op, "", linha, nucleo))
    if linha:
        tentativas.append((op, acom, "", nucleo))
        if acom:
            tentativas.append((op, "", "", nucleo))
    if flags.get("ignore_acom_advance") and op == "NotreDame" and linha == "ADVANCE":
        tentativas.extend([(op, "", "ADVANCE", nucleo), (op, "", linha, nucleo)])
    vistos: set[int] = set()
    out: list[ColunaRede] = []
    for t in tentativas:
        for c in idx.get(t, []):
            if c.col_idx not in vistos:
                vistos.add(c.col_idx)
                out.append(c)
    return out


def resolver_casamento_rede(
    operadora_raw: str,
    plano_nome: str,
    colunas: Iterable[ColunaRede],
    *,
    tabela: TabelaPlanosRedeAliases | None = None,
    aliases: dict[str, str] | None = None,
    flags: dict | None = None,
) -> ResultadoCasamentoRede:
    fl = flags if flags is not None else FLAGS_CASAMENTO_REDE
    mapa = aliases if aliases is not None else carregar_aliases()
    op = reconhecer_operadora_rede(
        operadora_raw, mapa, extra_estudo=fl.get("alias_hapvida", True)
    )
    if not op:
        return ResultadoCasamentoRede(estado=EstadoCasamentoRede.SEM_REDE)
    chave_plano = normalizar_cabecalho(plano_nome)
    tab = tabela if tabela is not None else carregar_aliases_rede()
    alias = tab.por_plano.get((op, chave_plano))
    if alias is not None:
        if alias.col_idx >= 0 and alias.rotulo_coluna:
            return ResultadoCasamentoRede(
                estado=EstadoCasamentoRede.ALIAS,
                rotulo_coluna=alias.rotulo_coluna,
                col_idx=alias.col_idx,
            )
        cols = list(colunas)
        casados = colunas_por_sufixo(op, alias.coluna_rede, cols)
        if len(casados) == 1:
            c = casados[0]
            return ResultadoCasamentoRede(
                estado=EstadoCasamentoRede.ALIAS,
                rotulo_coluna=c.rotulo_completo,
                col_idx=c.col_idx,
            )
        return ResultadoCasamentoRede(estado=EstadoCasamentoRede.SEM_REDE)

    fk = flags_chave_casamento(fl)
    k = chave_casamento_rede(op, plano_nome, **fk)
    idx = indexar_rede_automatica(colunas, fl, mapa)
    cands = _candidatos_regra(idx, k, fl)
    if len(cands) == 1:
        c = cands[0]
        return ResultadoCasamentoRede(
            estado=EstadoCasamentoRede.REGRA,
            rotulo_coluna=c.rotulo_completo,
            col_idx=c.col_idx,
        )
    return ResultadoCasamentoRede(estado=EstadoCasamentoRede.SEM_REDE)
