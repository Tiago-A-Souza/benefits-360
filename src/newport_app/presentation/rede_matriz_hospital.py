"""Ingestão da aba Matriz_Hospital (SiscorNet)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from newport_app.presentation.planos_rede import (
    ColunaRede,
    carregar_colunas_rede_xlsx,
    reconhecer_operadora_rede,
)
from newport_app.presentation.rede_recorte import parse_municipio_base
from newport_app.presentation.regras_comerciais import carregar_aliases

_DOCS = Path(__file__).resolve().parents[3] / "docs"
CAMINHO_XLSX_PADRAO = _DOCS / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


class BaseRedeHospitalInvalida(ValueError):
    """Planilha ausente ou layout inesperado."""


@dataclass(frozen=True)
class PrestadorRedeHospital:
    prestador: str
    classificacao: str
    municipio_rotulo: str
    chave_municipio: str
    uf: str
    cidade: str
    bairro: str
    regiao: str
    linha_idx: int
    celulas: dict[int, str] = field(default_factory=dict)

    @property
    def chave(self) -> tuple[str, str, str]:
        from newport_app.siscor_importer.normalize import normalizar_cabecalho

        bairro_norm = normalizar_cabecalho(self.bairro) if self.bairro else ""
        return (self.prestador, self.chave_municipio, bairro_norm)


@dataclass(frozen=True)
class BaseRedeHospital:
    prestadores: tuple[PrestadorRedeHospital, ...]
    colunas: tuple[ColunaRede, ...]
    municipios: frozenset[str]

    @property
    def chaves_prestadores(self) -> frozenset[tuple[str, str, str]]:
        return frozenset(p.chave for p in self.prestadores)


def caminho_base_rede_hospital() -> Path:
    from newport_app.config.paths import caminho_xlsx_rede_padrao

    env = os.environ.get("NEWPORT_REDE_XLSX", "").strip()
    if env:
        p = Path(env)
        if p.is_file():
            return p
        raise BaseRedeHospitalInvalida(f"NEWPORT_REDE_XLSX não é um arquivo: {p}")
    catalogo = caminho_xlsx_rede_padrao()
    if catalogo.is_file():
        return catalogo
    if CAMINHO_XLSX_PADRAO.is_file():
        return CAMINHO_XLSX_PADRAO
    legado = Path(
        r"C:\Users\tiago\Downloads\SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"
    )
    if legado.is_file():
        return legado
    raise BaseRedeHospitalInvalida(
        f"base de rede ausente — coloque em {catalogo} ou NEWPORT_REDE_XLSX"
    )


_CACHE_BASE_LOCK = threading.Lock()
_CACHE_BASE: dict[Path, tuple[tuple[int, int, int, int], BaseRedeHospital]] = {}


def _assinatura_arquivo(caminho: Path) -> tuple[int, int]:
    st = caminho.stat()
    return (st.st_mtime_ns, st.st_size)


def _assinatura_base(origem: Path) -> tuple[int, int, int, int]:
    """mtime e tamanho da planilha + do CSV de aliases (que molda `operadora_canon`)."""
    from newport_app.presentation.regras_comerciais import CAMINHO_ALIASES

    xlsx = _assinatura_arquivo(origem)
    try:
        aliases = _assinatura_arquivo(CAMINHO_ALIASES)
    except OSError:
        aliases = (0, 0)
    return (*xlsx, *aliases)


def limpar_cache_base_rede_hospital() -> None:
    """Descarta a base em memória (testes e diagnóstico)."""
    with _CACHE_BASE_LOCK:
        _CACHE_BASE.clear()


def carregar_base_rede_hospital(caminho: Path | None = None) -> BaseRedeHospital:
    """Lê a planilha uma vez; só relê se o arquivo (mtime/tamanho) mudar.

    A leitura do Excel custa segundos de CPU. A base é imutável por contrato —
    quem consome nunca altera `prestadores`, `colunas` nem `celulas`.
    """
    origem = caminho or caminho_base_rede_hospital()
    if not origem.is_file():
        raise BaseRedeHospitalInvalida(f"arquivo ausente: {origem}")
    chave = origem.resolve()
    assinatura = _assinatura_base(origem)
    with _CACHE_BASE_LOCK:
        hit = _CACHE_BASE.get(chave)
        if hit is not None and hit[0] == assinatura:
            return hit[1]
        base = _ler_base_rede_hospital(origem)
        _CACHE_BASE[chave] = (assinatura, base)
        return base


def _ler_base_rede_hospital(origem: Path) -> BaseRedeHospital:
    aliases = carregar_aliases()
    colunas = carregar_colunas_rede_xlsx(origem, aliases)
    wb = load_workbook(origem, read_only=True, data_only=True)
    try:
        ws = wb["Matriz_Hospital"]
        header = list(next(ws.iter_rows(min_row=4, max_row=4, values_only=True)))
        if not header or normalizar_prestador_header(header[0]) != "PRESTADOR":
            raise BaseRedeHospitalInvalida(
                f"{origem}: linha 4 deve começar com Prestador, obtido {header[:5]!r}"
            )
        max_col = max((c.col_idx for c in colunas), default=4)
        prestadores: list[PrestadorRedeHospital] = []
        municipios: set[str] = set()
        for row in ws.iter_rows(min_row=5, values_only=True):
            if not row or row[0] is None or str(row[0]).strip() == "":
                continue
            prestador = str(row[0]).strip()
            classif = str(row[1] or "").strip()
            mun_rot = str(row[2] or "").strip()
            bairro = str(row[3] or "").strip() if len(row) > 3 else ""
            regiao = str(row[4] or "").strip() if len(row) > 4 else ""
            uf, cidade = parse_municipio_base(mun_rot)
            chave_mun = f"{uf}.{cidade}"
            municipios.add(chave_mun)
            celulas: dict[int, str] = {}
            for col in colunas:
                idx = col.col_idx
                if idx < len(row):
                    val = row[idx]
                    if val is not None and str(val).strip():
                        celulas[idx] = str(val).strip()
            prestadores.append(
                PrestadorRedeHospital(
                    prestador=prestador,
                    classificacao=classif,
                    municipio_rotulo=mun_rot,
                    chave_municipio=chave_mun,
                    uf=uf,
                    cidade=cidade,
                    bairro=bairro,
                    regiao=regiao,
                    linha_idx=len(prestadores) + 5,
                    celulas=celulas,
                )
            )
    finally:
        wb.close()
    if len(prestadores) == 0:
        raise BaseRedeHospitalInvalida(f"{origem}: nenhum prestador lido")
    return BaseRedeHospital(
        prestadores=tuple(prestadores),
        colunas=colunas,
        municipios=frozenset(municipios),
    )


def normalizar_prestador_header(valor: object) -> str:
    from newport_app.siscor_importer.normalize import normalizar_cabecalho

    return normalizar_cabecalho(str(valor or ""))
