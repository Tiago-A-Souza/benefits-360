"""Ingestão da aba Matriz_Laboratorio (SiscorNet). Sem filtro HGER/HD/PSGER/MAT."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from newport_app.presentation.planos_rede import ColunaRede, carregar_colunas_rede_xlsx
from newport_app.presentation.rede_matriz_hospital import (
    caminho_base_rede_hospital,
    normalizar_prestador_header,
)
from newport_app.presentation.rede_recorte import parse_municipio_base
from newport_app.presentation.regras_comerciais import carregar_aliases


class BaseRedeLaboratorioInvalida(ValueError):
    """Planilha ausente ou layout inesperado na aba de laboratório."""


def _bairro_lab(valor: object) -> str:
    texto = str(valor or "").strip()
    if texto in {"", "..."}:
        return ""
    return texto


@dataclass(frozen=True)
class PrestadorRedeLaboratorio:
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


@dataclass(frozen=True)
class BaseRedeLaboratorio:
    prestadores: tuple[PrestadorRedeLaboratorio, ...]
    colunas: tuple[ColunaRede, ...]
    municipios: frozenset[str]


_CACHE_BASE_LOCK = threading.Lock()
_CACHE_BASE: dict[Path, tuple[tuple[int, int, int, int], BaseRedeLaboratorio]] = {}


def _assinatura_arquivo(caminho: Path) -> tuple[int, int]:
    st = caminho.stat()
    return (st.st_mtime_ns, st.st_size)


def _assinatura_base(origem: Path) -> tuple[int, int, int, int]:
    from newport_app.presentation.regras_comerciais import CAMINHO_ALIASES

    xlsx = _assinatura_arquivo(origem)
    try:
        aliases = _assinatura_arquivo(CAMINHO_ALIASES)
    except OSError:
        aliases = (0, 0)
    return (*xlsx, *aliases)


def limpar_cache_base_rede_laboratorio() -> None:
    """Descarta a base em memória (testes e diagnóstico)."""
    with _CACHE_BASE_LOCK:
        _CACHE_BASE.clear()


def carregar_base_rede_laboratorio(caminho: Path | None = None) -> BaseRedeLaboratorio:
    """Lê a aba Matriz_Laboratorio uma vez; só relê se o arquivo mudar."""
    origem = caminho or caminho_base_rede_hospital()
    if not origem.is_file():
        raise BaseRedeLaboratorioInvalida(f"arquivo ausente: {origem}")
    chave = origem.resolve()
    assinatura = _assinatura_base(origem)
    with _CACHE_BASE_LOCK:
        hit = _CACHE_BASE.get(chave)
        if hit is not None and hit[0] == assinatura:
            return hit[1]
        base = _ler_base_rede_laboratorio(origem)
        _CACHE_BASE[chave] = (assinatura, base)
        return base


def _ler_base_rede_laboratorio(origem: Path) -> BaseRedeLaboratorio:
    aliases = carregar_aliases()
    colunas = carregar_colunas_rede_xlsx(origem, aliases, aba="Matriz_Laboratorio")
    wb = load_workbook(origem, read_only=True, data_only=True)
    try:
        ws = wb["Matriz_Laboratorio"]
        header = list(next(ws.iter_rows(min_row=4, max_row=4, values_only=True)))
        if not header or normalizar_prestador_header(header[0]) != "PRESTADOR":
            raise BaseRedeLaboratorioInvalida(
                f"{origem}: linha 4 da Matriz_Laboratorio deve começar com Prestador, "
                f"obtido {header[:5]!r}"
            )
        prestadores: list[PrestadorRedeLaboratorio] = []
        municipios: set[str] = set()
        for row in ws.iter_rows(min_row=5, values_only=True):
            if not row or row[0] is None or str(row[0]).strip() == "":
                continue
            prestador = str(row[0]).strip()
            classif = str(row[1] or "").strip()
            mun_rot = str(row[2] or "").strip()
            bairro = _bairro_lab(row[3] if len(row) > 3 else "")
            regiao = _bairro_lab(row[4] if len(row) > 4 else "")
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
                PrestadorRedeLaboratorio(
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
        raise BaseRedeLaboratorioInvalida(f"{origem}: nenhum laboratório lido")
    return BaseRedeLaboratorio(
        prestadores=tuple(prestadores),
        colunas=colunas,
        municipios=frozenset(municipios),
    )
