"""Base CSV de hospitais principais — porta de manutenção."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from newport_app.presentation.rede_recorte import chave_municipio
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_DOCS = Path(__file__).resolve().parents[3] / "docs"
CAMINHO_BASE = _DOCS / "hospitais_principais_base.csv"

CABECALHO_ESPERADO = (
    "uf",
    "municipio",
    "zona",
    "prestador",
    "principal",
    "confianca",
    "rede_verticalizada",
    "especialidades",
    "observacao",
)


class BaseHospitaisPrincipaisInvalida(ValueError):
    """CSV malformado ou prestador ausente na matriz."""


@dataclass(frozen=True)
class EntradaHospitalPrincipal:
    uf: str
    municipio: str
    zona: str
    prestador: str
    principal: bool
    confianca: str
    rede_verticalizada: str
    especialidades: str
    observacao: str
    chave_municipio: str
    linha_csv: int

    @property
    def chave_grupo(self) -> tuple[str, str]:
        return (self.prestador, self.chave_municipio)


@dataclass(frozen=True)
class BaseHospitaisPrincipais:
    """Uma entrada por linha do CSV (1071) e índice por prestador da matriz."""

    linhas_csv: tuple[EntradaHospitalPrincipal, ...]
    por_prestador_matriz: dict[tuple[str, str, str], EntradaHospitalPrincipal]

    @property
    def total_linhas_csv(self) -> int:
        return len(self.linhas_csv)

    @property
    def total_principais(self) -> int:
        return sum(1 for e in self.por_prestador_matriz.values() if e.principal)


def _abrir_csv(caminho: Path) -> list[tuple[int, list[str]]]:
    if not caminho.is_file():
        raise BaseHospitaisPrincipaisInvalida(f"arquivo ausente: {caminho}")
    registros: list[tuple[int, list[str]]] = []
    with caminho.open(encoding="utf-8-sig", newline="") as fh:
        leitor = csv.reader(fh, delimiter=";", quotechar='"')
        for indice, row in enumerate(leitor, start=1):
            registros.append((indice, row))
    return registros


def _mesclar(a: EntradaHospitalPrincipal, b: EntradaHospitalPrincipal) -> EntradaHospitalPrincipal:
    return EntradaHospitalPrincipal(
        uf=a.uf,
        municipio=a.municipio,
        zona=a.zona or b.zona,
        prestador=a.prestador,
        principal=a.principal or b.principal,
        confianca=a.confianca or b.confianca,
        rede_verticalizada=a.rede_verticalizada or b.rede_verticalizada,
        especialidades=a.especialidades or b.especialidades,
        observacao=" | ".join(x for x in (a.observacao, b.observacao) if x),
        chave_municipio=a.chave_municipio,
        linha_csv=min(a.linha_csv, b.linha_csv),
    )


def carregar_hospitais_principais(
    caminho: Path | None = None,
    *,
    prestadores_matriz: tuple | None = None,
) -> BaseHospitaisPrincipais:
    from newport_app.presentation.rede_matriz_hospital import PrestadorRedeHospital

    origem = caminho or CAMINHO_BASE
    registros = _abrir_csv(origem)
    if not registros:
        raise BaseHospitaisPrincipaisInvalida(f"{origem}: arquivo vazio")
    cab = [c.strip().lower() for c in registros[0][1]]
    if cab != list(CABECALHO_ESPERADO):
        raise BaseHospitaisPrincipaisInvalida(
            f"{origem}: registro 1: cabeçalho esperado {CABECALHO_ESPERADO!r}, "
            f"obtido {cab!r}"
        )
    linhas: list[EntradaHospitalPrincipal] = []
    agrupado: dict[tuple[str, str], EntradaHospitalPrincipal] = {}
    matriz_ref = prestadores_matriz
    for indice, row in registros[1:]:
        if not row or all(not (c or "").strip() for c in row):
            raise BaseHospitaisPrincipaisInvalida(
                f"{origem}: registro {indice}: linha vazia"
            )
        if len(row) != len(CABECALHO_ESPERADO):
            raise BaseHospitaisPrincipaisInvalida(
                f"{origem}: registro {indice}: esperado {len(CABECALHO_ESPERADO)} "
                f"colunas, obtido {len(row)}"
            )
        uf, municipio, zona, prestador, principal, confianca, rede_v, esp, obs = (
            (c or "").strip() for c in row
        )
        if not uf or not municipio or not prestador:
            raise BaseHospitaisPrincipaisInvalida(
                f"{origem}: registro {indice}: uf, municipio ou prestador vazio"
            )
        uf = uf.upper()
        mun_norm = normalizar_cabecalho(municipio)
        chave_mun = chave_municipio(uf, mun_norm)
        princ = principal.strip().lower() in {"sim", "s", "yes", "1", "true"}
        entrada = EntradaHospitalPrincipal(
            uf=uf,
            municipio=municipio,
            zona=zona,
            prestador=prestador,
            principal=princ,
            confianca=confianca,
            rede_verticalizada=rede_v,
            especialidades=esp,
            observacao=obs,
            chave_municipio=chave_mun,
            linha_csv=indice,
        )
        if matriz_ref is not None:
            tem = any(
                p.prestador == prestador and p.chave_municipio == chave_mun
                for p in matriz_ref
            )
            if not tem:
                raise BaseHospitaisPrincipaisInvalida(
                    f"{origem}: registro {indice}: prestador {prestador!r} em "
                    f"{chave_mun} não existe na base de rede"
                )
        linhas.append(entrada)
        ch_gr = entrada.chave_grupo
        if ch_gr in agrupado:
            agrupado[ch_gr] = _mesclar(agrupado[ch_gr], entrada)
        else:
            agrupado[ch_gr] = entrada

    if matriz_ref is None:
        por_matriz = {k: v for k, v in agrupado.items()}  # type: ignore
        return BaseHospitaisPrincipais(
            linhas_csv=tuple(linhas),
            por_prestador_matriz=por_matriz,  # type: ignore[assignment]
        )

    por_matriz: dict[tuple[str, str, str], EntradaHospitalPrincipal] = {}
    for p in matriz_ref:
        assert isinstance(p, PrestadorRedeHospital)
        meta = agrupado.get((p.prestador, p.chave_municipio))
        if meta is None:
            raise BaseHospitaisPrincipaisInvalida(
                f"{origem}: prestador {p.prestador!r} em {p.chave_municipio} "
                f"(bairro {p.bairro!r}) não consta no CSV de principais"
            )
        por_matriz[p.chave] = meta

    return BaseHospitaisPrincipais(
        linhas_csv=tuple(linhas),
        por_prestador_matriz=por_matriz,
    )
