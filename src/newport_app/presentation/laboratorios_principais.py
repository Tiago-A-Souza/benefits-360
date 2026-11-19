"""Marcas de laboratório da proposta comercial — porta de manutenção."""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from pathlib import Path

from newport_app.config.paths import arquivo_docs
from newport_app.presentation.rede_matriz_laboratorio import PrestadorRedeLaboratorio
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_DOCS = Path(__file__).resolve().parents[3] / "docs"
CAMINHO_BASE = _DOCS / "laboratorios_principais_base.csv"

CABECALHO_ESPERADO = ("marca", "padroes_nome", "ufs", "ativo")


class BaseLaboratoriosPrincipaisInvalida(ValueError):
    """CSV malformado."""


@dataclass(frozen=True)
class MarcaLaboratorio:
    marca: str
    padroes_nome: tuple[str, ...]
    ufs: frozenset[str]
    ativo: bool
    linha_csv: int


@dataclass(frozen=True)
class BaseLaboratoriosPrincipais:
    marcas: tuple[MarcaLaboratorio, ...]


@dataclass(frozen=True)
class UnidadeMarcaLab:
    marca: str
    prestador: PrestadorRedeLaboratorio


_CACHE_LOCK = threading.Lock()
_CACHE: dict[Path, tuple[tuple[int, int], BaseLaboratoriosPrincipais]] = {}


def _abrir_csv(caminho: Path) -> list[tuple[int, list[str]]]:
    if not caminho.is_file():
        raise BaseLaboratoriosPrincipaisInvalida(f"arquivo ausente: {caminho}")
    registros: list[tuple[int, list[str]]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        for indice, row in enumerate(leitor, start=1):
            registros.append((indice, row))
    return registros


def limpar_cache_laboratorios_principais() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()


def carregar_laboratorios_principais(
    caminho: Path | None = None,
) -> BaseLaboratoriosPrincipais:
    origem = caminho or arquivo_docs("laboratorios_principais_base.csv")
    st = origem.stat()
    assinatura = (st.st_mtime_ns, st.st_size)
    chave = origem.resolve()
    with _CACHE_LOCK:
        hit = _CACHE.get(chave)
        if hit is not None and hit[0] == assinatura:
            return hit[1]
        base = _ler_csv(origem)
        _CACHE[chave] = (assinatura, base)
        return base


def _ler_csv(origem: Path) -> BaseLaboratoriosPrincipais:
    registros = _abrir_csv(origem)
    if not registros:
        raise BaseLaboratoriosPrincipaisInvalida(f"{origem}: arquivo vazio")
    cab = tuple(c.strip() for c in registros[0][1])
    if cab != CABECALHO_ESPERADO:
        raise BaseLaboratoriosPrincipaisInvalida(
            f"{origem}: registro 1: cabeçalho deve ser {';'.join(CABECALHO_ESPERADO)}, "
            f"obtido {cab!r}"
        )
    marcas: list[MarcaLaboratorio] = []
    vistos: set[str] = set()
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: linha vazia"
            )
        if len(row) != 4:
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: esperado 4 colunas, obtido {len(row)}"
            )
        marca = (row[0] or "").strip()
        padroes_raw = (row[1] or "").strip()
        ufs_raw = (row[2] or "").strip()
        ativo_raw = (row[3] or "").strip().lower()
        if not marca:
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: marca vazia"
            )
        chave_marca = normalizar_cabecalho(marca)
        if chave_marca in vistos:
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: marca duplicada {marca!r}"
            )
        vistos.add(chave_marca)
        padroes = tuple(p.strip() for p in padroes_raw.split(";") if p.strip())
        if not padroes:
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: padroes_nome vazio"
            )
        if ativo_raw not in {"sim", "nao"}:
            raise BaseLaboratoriosPrincipaisInvalida(
                f"{origem}: registro {indice}: ativo deve ser sim/nao, obtido {row[3]!r}"
            )
        ufs = frozenset(
            uf.strip().upper() for uf in ufs_raw.split(";") if uf.strip()
        )
        marcas.append(
            MarcaLaboratorio(
                marca=marca,
                padroes_nome=padroes,
                ufs=ufs,
                ativo=ativo_raw == "sim",
                linha_csv=indice,
            )
        )
    if not marcas:
        raise BaseLaboratoriosPrincipaisInvalida(f"{origem}: nenhuma marca")
    return BaseLaboratoriosPrincipais(marcas=tuple(marcas))


def nome_casa_padroes(nome: str, padroes: tuple[str, ...]) -> bool:
    n = normalizar_cabecalho(nome)
    if not n:
        return False
    return any(normalizar_cabecalho(p) in n for p in padroes if p.strip())


def unidade_casa_marca(prestador: PrestadorRedeLaboratorio, marca: MarcaLaboratorio) -> bool:
    if not marca.ativo:
        return False
    if marca.ufs and prestador.uf not in marca.ufs:
        return False
    return nome_casa_padroes(prestador.prestador, marca.padroes_nome)


def casar_unidades_marca(
    prestadores: tuple[PrestadorRedeLaboratorio, ...] | list[PrestadorRedeLaboratorio],
    marcas: tuple[MarcaLaboratorio, ...] | None = None,
) -> tuple[UnidadeMarcaLab, ...]:
    """Cada unidade casa com no máximo uma marca (primeira do CSV)."""
    if marcas is None:
        marcas = carregar_laboratorios_principais().marcas
    ativas = [m for m in marcas if m.ativo]
    saida: list[UnidadeMarcaLab] = []
    for p in prestadores:
        for marca in ativas:
            if unidade_casa_marca(p, marca):
                saida.append(UnidadeMarcaLab(marca=marca.marca, prestador=p))
                break
    return tuple(saida)
