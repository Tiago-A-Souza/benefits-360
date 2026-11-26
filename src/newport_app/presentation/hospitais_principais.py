"""Base CSV de hospitais principais — porta de manutenção."""

from __future__ import annotations

import csv
import threading
from dataclasses import dataclass
from pathlib import Path

from newport_app.presentation.rede_recorte import chave_municipio
from newport_app.config.paths import arquivo_docs
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
    """CSV malformado."""


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
    """Uma entrada por linha do CSV e índice por prestador da matriz."""

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


def _zona_norm(zona: str) -> str:
    return normalizar_cabecalho(zona or "")


# Zona auditada (CSV) por bairro — prevalece sobre `regiao` da matriz SiscorNet em SP.
_SP_BAIRRO_ZONA_AUDITADA: dict[str, str] = {
    "ITAIM BIBI": "ZONA OESTE",
    "MOEMA": "ZONA SUL",
    "CAPAO REDONDO": "ZONA SUL",
    "VILA OLIMPIA": "ZONA OESTE",
    "VILA NOVA CONCEICAO": "ZONA OESTE",
    "BELA VISTA": "CENTRO",
    "POMPEIA": "ZONA OESTE",
    "SANTANA": "ZONA NORTE",
    "IPIRANGA": "ZONA SUL",
}


def _zona_auditada_por_bairro(chave_municipio: str, bairro: str) -> str | None:
    if chave_municipio != "SP.SAO PAULO":
        return None
    return _SP_BAIRRO_ZONA_AUDITADA.get(normalizar_cabecalho(bairro))


def _bairro_no_texto(bairro: str, *textos: str) -> bool:
    b = normalizar_cabecalho(bairro)
    if not b:
        return False
    blob = normalizar_cabecalho(" ".join(t for t in textos if t))
    if b in blob:
        return True
    for tok in b.split():
        if len(tok) >= 4 and tok in blob:
            return True
    return False


def _mesclar_linhas_csv(
    linhas: tuple[EntradaHospitalPrincipal, ...] | list[EntradaHospitalPrincipal],
) -> EntradaHospitalPrincipal:
    if not linhas:
        raise ValueError("mesclar_linhas_csv: lista vazia")
    meta = linhas[0]
    for e in linhas[1:]:
        meta = _mesclar(meta, e)
    return meta


def _meta_por_registro_matriz(
    prestador_matriz: "PrestadorRedeHospital",
    linhas_grupo: list[EntradaHospitalPrincipal],
    *,
    fallback: EntradaHospitalPrincipal,
) -> EntradaHospitalPrincipal:
    """Associa registro da matriz (bairro) à linha do CSV — zona auditada primeiro."""
    from newport_app.presentation.rede_matriz_hospital import PrestadorRedeHospital

    assert isinstance(prestador_matriz, PrestadorRedeHospital)
    bairro = normalizar_cabecalho(prestador_matriz.bairro or "")
    ch = prestador_matriz.chave_municipio

    zona_alvo = _zona_auditada_por_bairro(ch, bairro)
    if zona_alvo:
        filtradas = [e for e in linhas_grupo if _zona_norm(e.zona) == _zona_norm(zona_alvo)]
        if filtradas:
            return _mesclar_linhas_csv(filtradas)

    if bairro:
        por_obs = [
            e
            for e in linhas_grupo
            if _bairro_no_texto(bairro, e.observacao, e.especialidades)
        ]
        if por_obs:
            princ = [e for e in por_obs if e.principal] or por_obs
            return _mesclar_linhas_csv(princ)

    com_zona = [e for e in linhas_grupo if (e.zona or "").strip()]
    if len(com_zona) == 1:
        return com_zona[0]

    regiao = _zona_norm(prestador_matriz.regiao)
    if regiao and not com_zona:
        filtradas = [e for e in linhas_grupo if _zona_norm(e.zona) == regiao]
        if filtradas:
            return _mesclar_linhas_csv(filtradas)

    if len(linhas_grupo) == 1:
        return linhas_grupo[0]
    return fallback


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


_CACHE_PRINCIPAIS_LOCK = threading.Lock()
# caminho → (assinatura do CSV, matriz de referência, resultado)
_CACHE_PRINCIPAIS: dict[Path, tuple[tuple[int, int], object, BaseHospitaisPrincipais]] = {}


def limpar_cache_hospitais_principais() -> None:
    with _CACHE_PRINCIPAIS_LOCK:
        _CACHE_PRINCIPAIS.clear()


def carregar_hospitais_principais(
    caminho: Path | None = None,
    *,
    prestadores_matriz: tuple | None = None,
) -> BaseHospitaisPrincipais:
    """Reaproveita o resultado enquanto o CSV (mtime/tamanho) e a matriz forem os mesmos."""
    origem = caminho or arquivo_docs("hospitais_principais_base.csv")
    try:
        st = origem.stat()
    except OSError:
        return _ler_hospitais_principais(caminho, prestadores_matriz=prestadores_matriz)
    assinatura = (st.st_mtime_ns, st.st_size)
    chave = origem.resolve()
    with _CACHE_PRINCIPAIS_LOCK:
        hit = _CACHE_PRINCIPAIS.get(chave)
        if (
            hit is not None
            and hit[0] == assinatura
            and hit[1] is prestadores_matriz
        ):
            return hit[2]
        resultado = _ler_hospitais_principais(
            caminho, prestadores_matriz=prestadores_matriz
        )
        _CACHE_PRINCIPAIS[chave] = (assinatura, prestadores_matriz, resultado)
        return resultado


def _ler_hospitais_principais(
    caminho: Path | None = None,
    *,
    prestadores_matriz: tuple | None = None,
) -> BaseHospitaisPrincipais:
    from newport_app.presentation.rede_matriz_hospital import PrestadorRedeHospital

    origem = caminho or arquivo_docs("hospitais_principais_base.csv")
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

    linhas_por_grupo: dict[tuple[str, str], list[EntradaHospitalPrincipal]] = {}
    for entrada in linhas:
        ch_gr = entrada.chave_grupo
        linhas_por_grupo.setdefault(ch_gr, []).append(entrada)

    por_matriz: dict[tuple[str, str, str], EntradaHospitalPrincipal] = {}
    for p in matriz_ref:
        assert isinstance(p, PrestadorRedeHospital)
        ch_gr = (p.prestador, p.chave_municipio)
        fallback = agrupado.get(ch_gr)
        if fallback is None:
            por_matriz[p.chave] = EntradaHospitalPrincipal(
                uf=p.uf,
                municipio=p.cidade,
                zona="",
                prestador=p.prestador,
                principal=False,
                confianca="",
                rede_verticalizada="",
                especialidades="",
                observacao="",
                chave_municipio=p.chave_municipio,
                linha_csv=0,
            )
            continue
        grupo = linhas_por_grupo.get(ch_gr, [])
        por_matriz[p.chave] = _meta_por_registro_matriz(
            p, grupo, fallback=fallback
        )

    return BaseHospitaisPrincipais(
        linhas_csv=tuple(linhas),
        por_prestador_matriz=por_matriz,
    )
