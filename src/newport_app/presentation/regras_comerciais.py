"""Regras comerciais do documento — base CSV + casamento por igualdade após normalizar.

A porta de manutenção é o CSV. Este módulo só lê, valida e casa nomes.
Não altera snapshot, hash nem a interface.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from newport_app.config.paths import arquivo_docs
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_DOCS = Path(__file__).resolve().parents[3] / "docs"
CAMINHO_BASE = _DOCS / "regras_comerciais_base.csv"
CAMINHO_ALIASES = _DOCS / "regras_comerciais_aliases.csv"

OPERADORAS_CANONICAS: tuple[str, ...] = (
    "Amil",
    "Alice",
    "Bradesco",
    "Porto Seguro",
    "Hapvida",
    "NotreDame",
    "Seguros Unimed",
    "SulAmérica",
    "Omint",
    "Unimed os Bandeirantes",
)

# Chaves próprias fora da grade de regras (80 células). Reajuste PME e aliases.
OPERADORAS_CANONICAS_EXTRA: tuple[str, ...] = (
    "Careplus",
    "CNU",
)

OPERADORAS_RECONHECIVEIS: tuple[str, ...] = OPERADORAS_CANONICAS + OPERADORAS_CANONICAS_EXTRA

REGRAS_ORDEM: tuple[str, ...] = (
    "Redução de Carências",
    "Adesão",
    "Compulsório",
    "Vigência do Contrato",
    "Regras De Cancelamento",
    "Multa Por Cancelamento",
    "Análise de Sinistralidade",
    "Inclusão de PJS",
)

# Mesma paginação das outras visões (builder.MAX_PROPOSTAS_POR_PAGINA).
MAX_OPERADORAS_POR_PAGINA = 3


class BaseRegrasComerciaisInvalida(ValueError):
    """Base ou aliases malformados — a mensagem cita o registro."""


@dataclass(frozen=True)
class TabelaRegrasComerciais:
    operadoras: tuple[str, ...]
    regras: tuple[str, ...]
    celulas: dict[tuple[str, str], str]

    def valor(self, operadora: str, regra: str) -> str:
        return self.celulas[(operadora, regra)]


def _abrir_csv(caminho: Path) -> list[tuple[int, list[str]]]:
    if not caminho.is_file():
        raise BaseRegrasComerciaisInvalida(f"arquivo ausente: {caminho}")
    registros: list[tuple[int, list[str]]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        for indice, row in enumerate(leitor, start=1):
            registros.append((indice, row))
    return registros


def carregar_base(caminho: Path | None = None) -> dict[tuple[str, str], str]:
    """Lê o CSV de valores. Uma célula por (operadora, regra)."""
    origem = caminho or arquivo_docs("regras_comerciais_base.csv")
    registros = _abrir_csv(origem)
    if not registros:
        raise BaseRegrasComerciaisInvalida(f"{origem}: arquivo vazio")
    cab = [c.strip() for c in registros[0][1]]
    if cab != ["operadora", "regra", "valor"]:
        raise BaseRegrasComerciaisInvalida(
            f"{origem}: registro 1: cabeçalho deve ser operadora;regra;valor, "
            f"obtido {cab!r}"
        )
    celulas: dict[tuple[str, str], str] = {}
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: linha vazia"
            )
        if len(row) != 3:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: esperado 3 colunas, obtido {len(row)}"
            )
        operadora, regra, valor = (c.strip() if i < 2 else c for i, c in enumerate(row))
        valor = (valor or "").replace("\r\n", "\n").replace("\r", "\n").strip()
        if operadora not in OPERADORAS_CANONICAS:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: operadora fora da lista canônica: "
                f"{operadora!r}"
            )
        if regra not in REGRAS_ORDEM:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: regra fora das oito: {regra!r}"
            )
        if not valor:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: célula vazia "
                f"({operadora!r}, {regra!r})"
            )
        chave = (operadora, regra)
        if chave in celulas:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: duplicata ({operadora!r}, {regra!r})"
            )
        celulas[chave] = valor
    esperadas = {(op, rg) for op in OPERADORAS_CANONICAS for rg in REGRAS_ORDEM}
    faltando = sorted(esperadas - set(celulas))
    if faltando:
        op, rg = faltando[0]
        raise BaseRegrasComerciaisInvalida(
            f"{origem}: célula faltando ({op!r}, {rg!r}) "
            f"— {len(faltando)} ausente(s) de 80"
        )
    return celulas


def carregar_aliases(caminho: Path | None = None) -> dict[str, str]:
    """Mapa normalizado → canônica. Igualdade após `normalizar_cabecalho`."""
    origem = caminho or arquivo_docs("regras_comerciais_aliases.csv")
    registros = _abrir_csv(origem)
    if not registros:
        raise BaseRegrasComerciaisInvalida(f"{origem}: arquivo vazio")
    cab = [c.strip() for c in registros[0][1]]
    if cab != ["canonica", "variacao"]:
        raise BaseRegrasComerciaisInvalida(
            f"{origem}: registro 1: cabeçalho deve ser canonica;variacao, "
            f"obtido {cab!r}"
        )
    mapa: dict[str, str] = {}
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: linha vazia"
            )
        if len(row) != 2:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: esperado 2 colunas, obtido {len(row)}"
            )
        canonica, variacao = (c.strip() for c in row)
        if canonica not in OPERADORAS_RECONHECIVEIS:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: canônica fora da lista: {canonica!r}"
            )
        if not variacao:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: variação vazia para {canonica!r}"
            )
        # Reutiliza a mesma normalização dos cabeçalhos SISCOR
        # (siscor_importer/normalize.py:29) — NBSP, ZWSP, BOM, NFKD, caixa.
        chave = normalizar_cabecalho(variacao)
        if not chave:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: variação normaliza para vazio "
                f"({variacao!r})"
            )
        anterior = mapa.get(chave)
        if anterior is not None and anterior != canonica:
            raise BaseRegrasComerciaisInvalida(
                f"{origem}: registro {indice}: variação {variacao!r} casa com "
                f"{canonica!r} e também com {anterior!r}"
            )
        mapa[chave] = canonica
    for canonica in OPERADORAS_RECONHECIVEIS:
        chave = normalizar_cabecalho(canonica)
        mapa.setdefault(chave, canonica)
    return mapa


def reconhecer_operadora(
    nome: str | None,
    aliases: dict[str, str] | None = None,
) -> str | None:
    """Casa o nome da cotação com uma canônica, ou None.

    Primeiro `normalizar_cabecalho` (normalize.py:29), depois igualdade no
    mapa. Nunca «contém».
    """
    if nome is None or not str(nome).strip():
        return None
    mapa = aliases if aliases is not None else carregar_aliases()
    return mapa.get(normalizar_cabecalho(nome))


def operadoras_das_cotacoes(
    nomes: list[str],
    *,
    aliases: dict[str, str] | None = None,
) -> tuple[str, ...]:
    """Canônicas distintas, na ordem em que as cotações as apresentaram."""
    mapa = aliases if aliases is not None else carregar_aliases()
    saida: list[str] = []
    for nome in nomes:
        canonica = reconhecer_operadora(nome, mapa)
        if canonica and canonica not in saida:
            saida.append(canonica)
    return tuple(saida)


def montar_tabela(
    nomes_cotacao: list[str],
    *,
    base: dict[tuple[str, str], str] | None = None,
    aliases: dict[str, str] | None = None,
) -> TabelaRegrasComerciais | None:
    """Tabela pronta para o renderer, ou None se nenhuma operadora casar."""
    reconhecidas = operadoras_das_cotacoes(nomes_cotacao, aliases=aliases)
    operadoras = tuple(op for op in reconhecidas if op in OPERADORAS_CANONICAS)
    if not operadoras:
        return None
    celulas = base if base is not None else carregar_base()
    recorte = {
        (op, rg): celulas[(op, rg)] for op in operadoras for rg in REGRAS_ORDEM
    }
    return TabelaRegrasComerciais(
        operadoras=operadoras,
        regras=REGRAS_ORDEM,
        celulas=recorte,
    )


def operadoras_do_cenario(rascunho, cenario, operadora_coluna: str) -> list[str]:
    """Operadoras de todas as opções atribuídas no cenário, não só a de referência.

    Uma coluna mista (Porto num grupo, SulAmérica no outro) precisa das duas
    nas regras contratuais — o HTML já mostra os dois planos.
    """
    saida: list[str] = []
    por_id = {op.id: op for op in getattr(rascunho, "opcoes_proposta", []) or []}
    if cenario is not None:
        for atr in getattr(cenario, "atribuicoes", []) or []:
            oid = getattr(atr, "opcao_plano_id", None)
            if not oid:
                continue
            opcao = por_id.get(oid)
            nome = (getattr(opcao, "operadora", None) or "").strip()
            if nome and nome not in saida:
                saida.append(nome)
    coluna = (operadora_coluna or "").strip()
    if coluna and coluna not in saida:
        saida.insert(0, coluna)
    return saida


def nomes_operadora_do_view_model(vm) -> list[str]:
    """Nomes crus das cotações no ViewModel — só propostas, não plano vigente.

    Inclui `operadoras_participantes` para coluna mista: o rótulo da coluna
    pode ser Porto e o outro grupo ter SulAmérica.
    """
    nomes: list[str] = []
    for secao in getattr(vm, "secoes_regime", []) or []:
        for prop in getattr(secao, "propostas", []) or []:
            extras = getattr(prop, "operadoras_participantes", None) or []
            for nome in (getattr(prop, "operadora", None), *extras):
                texto = (nome or "").strip()
                if texto:
                    nomes.append(texto)
    return nomes
