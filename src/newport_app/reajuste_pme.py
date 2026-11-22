"""Sugestão de reajuste PME (ANS) para grupos abaixo de 30 vidas.

A porta de manutenção é o CSV. Este módulo só lê, valida e sugere.
Não altera motor, snapshot, hash nem valores já informados.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from newport_app.config.paths import arquivo_docs
from newport_app.models.draft import RascunhoEstudo
from newport_app.presentation.regras_comerciais import (
    OPERADORAS_RECONHECIVEIS,
    reconhecer_operadora,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_DOCS = Path(__file__).resolve().parents[2] / "docs"
CAMINHO_BASE = _DOCS / "reajustes_pme_base.csv"

LIMIAR_VIDAS_PME = 30
TIPOS_PERMITIDOS = frozenset({"premio", "reembolso"})
OPERADORA_REFERENCIA_ANS = "Individuais (ANS)"
TIPO_PREMIO = "premio"

_CHAVE_ANS = normalizar_cabecalho(OPERADORA_REFERENCIA_ANS)


class BaseReajustesPmeInvalida(ValueError):
    """Base malformada — a mensagem cita o registro."""


@dataclass(frozen=True)
class LinhaReajustePme:
    periodo: str
    operadora_csv: str
    chave_operadora: str | None
    tipo: str
    reajuste_bps: int
    reajuste_pct: Decimal
    linha: int


@dataclass(frozen=True)
class SugestaoReajustePme:
    subgrupo_id: str
    periodo: str | None
    reajuste_bps: int | None
    reajuste_pct_exibicao: str | None
    origem: str | None
    operadora_canonica: str | None
    vidas_incluidas: int


def _abrir_csv(caminho: Path) -> list[tuple[int, list[str]]]:
    if not caminho.is_file():
        raise BaseReajustesPmeInvalida(f"arquivo ausente: {caminho}")
    registros: list[tuple[int, list[str]]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        for indice, row in enumerate(leitor, start=1):
            registros.append((indice, row))
    return registros


def _pct_para_bps(texto: str, origem: Path, indice: int) -> tuple[Decimal, int]:
    bruto = (texto or "").strip().replace(",", ".")
    if not bruto:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: percentual vazio"
        )
    try:
        pct = Decimal(bruto)
    except InvalidOperation as exc:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: percentual inválido: {texto!r}"
        ) from exc
    if pct < 0:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: percentual negativo: {texto!r}"
        )
    centesimos = pct * Decimal(100)
    if centesimos != centesimos.to_integral_value():
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: percentual não converte a bps inteiros: "
            f"{texto!r}"
        )
    bps = int(centesimos)
    return pct, bps


def _chave_csv(operadora: str, origem: Path, indice: int) -> str | None:
    """Canônica para índice, ou None se for a linha de referência ANS."""
    if normalizar_cabecalho(operadora) == _CHAVE_ANS:
        return None
    canonica = reconhecer_operadora(operadora)
    if canonica is None:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: operadora fora da canônica: {operadora!r}"
        )
    if canonica not in OPERADORAS_RECONHECIVEIS:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro {indice}: operadora fora da canônica: {operadora!r}"
        )
    return canonica


def carregar_base(caminho: Path | None = None) -> tuple[LinhaReajustePme, ...]:
    """Lê o CSV. Uma linha por (periodo, operadora, tipo)."""
    origem = caminho or arquivo_docs("reajustes_pme_base.csv")
    registros = _abrir_csv(origem)
    if not registros:
        raise BaseReajustesPmeInvalida(f"{origem}: arquivo vazio")
    cab = [c.strip() for c in registros[0][1]]
    esperado = [
        "periodo",
        "operadora",
        "tipo",
        "reajuste_pct",
        "fonte",
        "vigente_desde",
        "atualizado_em",
    ]
    if cab != esperado:
        raise BaseReajustesPmeInvalida(
            f"{origem}: registro 1: cabeçalho deve ser {';'.join(esperado)}, "
            f"obtido {cab!r}"
        )
    linhas: list[LinhaReajustePme] = []
    vistos: dict[tuple[str, str | None, str], int] = {}
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: linha vazia"
            )
        if len(row) < 4:
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: esperado ao menos 4 colunas, "
                f"obtido {len(row)}"
            )
        periodo = (row[0] or "").strip()
        operadora = (row[1] or "").strip()
        tipo = (row[2] or "").strip()
        pct_txt = row[3] if len(row) > 3 else ""
        if not periodo:
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: período vazio"
            )
        if not operadora:
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: operadora vazia"
            )
        if tipo not in TIPOS_PERMITIDOS:
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: tipo fora de premio/reembolso: "
                f"{tipo!r}"
            )
        chave = _chave_csv(operadora, origem, indice)
        pct, bps = _pct_para_bps(str(pct_txt), origem, indice)
        dup = (periodo, chave if chave is not None else _CHAVE_ANS, tipo)
        anterior = vistos.get(dup)
        if anterior is not None:
            raise BaseReajustesPmeInvalida(
                f"{origem}: registro {indice}: duplicata "
                f"({periodo!r}, {operadora!r}, {tipo!r}) — também no registro "
                f"{anterior}"
            )
        vistos[dup] = indice
        linhas.append(
            LinhaReajustePme(
                periodo=periodo,
                operadora_csv=operadora,
                chave_operadora=chave,
                tipo=tipo,
                reajuste_bps=bps,
                reajuste_pct=pct,
                linha=indice,
            )
        )
    return tuple(linhas)


def _indice_premio(
    linhas: tuple[LinhaReajustePme, ...] | None = None,
) -> dict[tuple[str, str], LinhaReajustePme]:
    """(periodo, canonica) → linha de prêmio. Exclui Individuais (ANS)."""
    origem = linhas if linhas is not None else carregar_base()
    indice: dict[tuple[str, str], LinhaReajustePme] = {}
    for linha in origem:
        if linha.tipo != TIPO_PREMIO:
            continue
        if linha.chave_operadora is None:
            continue
        indice[(linha.periodo, linha.chave_operadora)] = linha
    return indice


def periodos_conhecidos(
    linhas: tuple[LinhaReajustePme, ...] | None = None,
) -> frozenset[str]:
    origem = linhas if linhas is not None else carregar_base()
    return frozenset(ln.periodo for ln in origem)


def periodo_da_data(
    data: date | None,
    *,
    periodos: frozenset[str] | None = None,
) -> str | None:
    """Maio Y–Abril Y+1 a partir da data de referência. Fora da tabela → None."""
    if data is None:
        return None
    if data.month >= 5:
        inicio = data.year
    else:
        inicio = data.year - 1
    rotulo = f"Maio {inicio} a Abril {inicio + 1}"
    conhecidos = periodos if periodos is not None else periodos_conhecidos()
    if rotulo not in conhecidos:
        return None
    return rotulo


def _eh_referencia_ans(nome: str | None) -> bool:
    if nome is None or not str(nome).strip():
        return False
    return normalizar_cabecalho(nome) == _CHAVE_ANS


def reconhecer_operadora_reajuste(nome: str | None) -> str | None:
    """Canônica para reajuste. Individuais (ANS) nunca casa."""
    if _eh_referencia_ans(nome):
        return None
    return reconhecer_operadora(nome)


def formatar_pct_de_bps(bps: int) -> str:
    inteiro, resto = divmod(abs(bps), 100)
    if resto == 0:
        return str(inteiro)
    if resto % 10 == 0:
        return f"{inteiro},{resto // 10}"
    return f"{inteiro},{resto:02d}"


def vidas_incluidas_estudo(rascunho: RascunhoEstudo) -> int:
    """Contagem que decide o corte de 30: vidas com `incluida=True`."""
    return len(rascunho.vidas_incluidas())


def _lookup_premio(
    periodo: str,
    canonica: str,
    indice: dict[tuple[str, str], LinhaReajustePme] | None = None,
) -> LinhaReajustePme | None:
    mapa = indice if indice is not None else _indice_premio()
    return mapa.get((periodo, canonica))


def sugerir_reajuste_plano(
    *,
    operadora: str | None,
    data_referencia: date | None,
    vidas_incluidas: int,
    formato: str = "renovacao",
    indice: dict[tuple[str, str], LinhaReajustePme] | None = None,
    periodos: frozenset[str] | None = None,
) -> tuple[str | None, int | None, str | None, str | None]:
    """Retorna (periodo, bps, pct_exibicao, origem). Sem invenção."""
    if formato == "novo":
        return None, None, None, None
    periodo = periodo_da_data(data_referencia, periodos=periodos)
    if vidas_incluidas >= LIMIAR_VIDAS_PME:
        return periodo, None, None, None
    if periodo is None:
        return None, None, None, None
    canonica = reconhecer_operadora_reajuste(operadora)
    if canonica is None:
        return periodo, None, None, None
    linha = _lookup_premio(periodo, canonica, indice)
    if linha is None:
        return periodo, None, None, None
    return (
        periodo,
        linha.reajuste_bps,
        formatar_pct_de_bps(linha.reajuste_bps),
        "tabela_pme",
    )


def sugestoes_do_rascunho(
    rascunho: RascunhoEstudo,
    *,
    linhas: tuple[LinhaReajustePme, ...] | None = None,
) -> list[SugestaoReajustePme]:
    """Sugestões por plano vigente. Não muta o rascunho."""
    base = linhas if linhas is not None else carregar_base()
    indice = _indice_premio(base)
    periodos = frozenset(ln.periodo for ln in base)
    n_vidas = vidas_incluidas_estudo(rascunho)
    data_ref = rascunho.escolhas.data_referencia_idade
    saida: list[SugestaoReajustePme] = []
    for sg in rascunho.subgrupos_atuais:
        periodo, bps, pct, origem = sugerir_reajuste_plano(
            operadora=sg.operadora,
            data_referencia=data_ref,
            vidas_incluidas=n_vidas,
            formato=rascunho.formato,
            indice=indice,
            periodos=periodos,
        )
        saida.append(
            SugestaoReajustePme(
                subgrupo_id=sg.id,
                periodo=periodo,
                reajuste_bps=bps,
                reajuste_pct_exibicao=pct,
                origem=origem,
                operadora_canonica=reconhecer_operadora_reajuste(sg.operadora),
                vidas_incluidas=n_vidas,
            )
        )
    return saida


def aplicar_sugestao_se_vazio(atual_bps: int | None, sugerido_bps: int | None) -> int | None:
    """Preenche só se o campo ainda não tem valor informado."""
    if atual_bps is not None:
        return atual_bps
    return sugerido_bps
