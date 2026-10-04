"""REDE fase C — ingestão, filtro, recorte e visão de rede."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.hospitais_principais import (
    CAMINHO_BASE as CAMINHO_PRINCIPAIS,
    BaseHospitaisPrincipaisInvalida,
    carregar_hospitais_principais,
)
from newport_app.presentation.planos_rede import (
    EstadoCasamentoRede,
    carregar_aliases_rede,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_especialidade import (
    celula_passa_filtro_especialidade,
    prestador_passa_filtro_especialidade,
)
from newport_app.presentation.rede_matriz_hospital import (
    CAMINHO_XLSX_PADRAO,
    BaseRedeHospitalInvalida,
    carregar_base_rede_hospital,
)
from newport_app.presentation.rede_recorte import (
    CRITERIO_RECORTE_GEOGRAFICO,
    ModoRecorteGeografico,
    municipios_permitidos,
)
from newport_app.presentation.rede_visao import (
    EstadoMapeamentoPlanoRede,
    contar_funil_anistia,
    montar_visao_rede_estudo,
)
from newport_app.presentation.regras_comerciais import carregar_aliases
from newport_app.siscor_importer.normalize import normalizar_cabecalho
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_planos_rede import _planos_estudo_reais
from tests.test_rede_fase_b import _parse_bytes
from tests.fixtures.siscor.xlsx_builder import planilha_anistia_41_sintetica
from newport_app.presentation.builder import construir_view_model
from tests.test_regras_comerciais import _html_de
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico

ROOT = Path(__file__).resolve().parents[1]

TOTAL_APOS_ESPECIALIDADE_GLOBAL = 782
FUNIL_ANISTIA_ESPERADO = {
    "total_base": 1071,
    "apos_municipio_beneficiario": 312,
    "apos_municipio_e_capital": 312,
    "apos_especialidade": 234,
}


@pytest.fixture(scope="module")
def base_rede():
    if not CAMINHO_XLSX_PADRAO.is_file():
        pytest.skip("XLSX SiscorNet ausente em docs/")
    return carregar_base_rede_hospital()


@pytest.fixture(scope="module")
def principais(base_rede):
    return carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)


@pytest.fixture(scope="module")
def tabela_planos(base_rede):
    return carregar_aliases_rede(colunas_rede=base_rede.colunas)


def test_01_base_1071_prestadores_51_municipios(base_rede):
    assert len(base_rede.prestadores) == 1071
    assert len(base_rede.municipios) == 51


def test_02_csv_1071_linhas_391_principais(principais):
    assert principais.total_linhas_csv == 1071
    assert sum(1 for e in principais.linhas_csv if e.principal) == 391


def test_03_todo_csv_existe_na_matriz(base_rede, principais):
    for p in base_rede.prestadores:
        assert p.chave in principais.por_prestador_matriz


def test_04_csv_malformado_falha_com_linha(base_rede, tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "uf;municipio;zona;prestador;principal;confianca;rede_verticalizada;"
        "especialidades;observacao\n"
        "XX\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(BaseHospitaisPrincipaisInvalida, match="registro 2"):
        carregar_hospitais_principais(bad, prestadores_matriz=base_rede.prestadores)


def test_05_prestador_inexistente_falha(base_rede, tmp_path):
    bad = tmp_path / "bad.csv"
    cab = (
        "uf;municipio;zona;prestador;principal;confianca;rede_verticalizada;"
        "especialidades;observacao\n"
    )
    bad.write_text(
        cab + "SP;SAO PAULO;;HOSPITAL QUE NAO EXISTE;nao;;;;\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(BaseHospitaisPrincipaisInvalida, match="registro 2"):
        carregar_hospitais_principais(bad, prestadores_matriz=base_rede.prestadores)


def test_06_celula_hger_mat_psger_mantida():
    assert celula_passa_filtro_especialidade("HGER - MAT - PSGER")


def test_07_celula_hcelt_psort_descartada():
    assert not celula_passa_filtro_especialidade("HCELT")
    assert not celula_passa_filtro_especialidade("PSORT")


def test_08_total_apos_filtro_especialidade(base_rede):
    n = sum(
        1 for p in base_rede.prestadores if prestador_passa_filtro_especialidade(p.celulas)
    )
    assert n == TOTAL_APOS_ESPECIALIDADE_GLOBAL


def test_09_todo_principal_passa_filtro(base_rede, principais):
    falhas = []
    for p in base_rede.prestadores:
        meta = principais.por_prestador_matriz[p.chave]
        if not meta.principal:
            continue
        if not prestador_passa_filtro_especialidade(p.celulas):
            falhas.append(p.prestador)
    assert falhas == []


def test_10_funil_anistia_municipio_e_capital(base_rede):
    loc = _localizacoes_anistia_planilha()
    funil = contar_funil_anistia(base_rede, loc)
    assert funil == FUNIL_ANISTIA_ESPERADO


def test_11_duque_de_caxias_ve_rio_pela_capital(base_rede):
    loc = {( "RJ", normalizar_cabecalho("Duque de Caxias") )}
    somente = municipios_permitidos(
        loc, set(base_rede.municipios), modo=ModoRecorteGeografico.SOMENTE_MUNICIPIO
    )
    assert somente == set()
    com_cap = municipios_permitidos(
        loc, set(base_rede.municipios), modo=ModoRecorteGeografico.MUNICIPIO_E_CAPITAL_UF
    )
    assert "RJ.RIO DE JANEIRO" in com_cap
    n = sum(1 for p in base_rede.prestadores if p.chave_municipio in com_cap)
    assert n > 0


def test_12_criterio_configuravel_um_lugar():
    assert CRITERIO_RECORTE_GEOGRAFICO == ModoRecorteGeografico.MUNICIPIO_E_CAPITAL_UF
    loc = {( "RJ", normalizar_cabecalho("Duque de Caxias") )}
    base_mun = {"RJ.RIO DE JANEIRO"}
    assert (
        len(
            municipios_permitidos(
                loc, base_mun, modo=ModoRecorteGeografico.SOMENTE_MUNICIPIO
            )
        )
        == 0
    )
    assert (
        len(
            municipios_permitidos(
                loc, base_mun, modo=ModoRecorteGeografico.MUNICIPIO_E_CAPITAL_UF
            )
        )
        == 1
    )


def test_13_visao_por_plano_com_cobertura(base_rede, principais, tabela_planos):
    rascunho = _rascunho_anistia_seis()
    vidas = []
    for i, v in enumerate(rascunho.vidas):
        if i == 0:
            vidas.append(v.model_copy(update={"uf": "RJ", "cidade": "RIO DE JANEIRO"}))
        else:
            vidas.append(v)
    rascunho = rascunho.model_copy(update={"vidas": vidas})
    visao = montar_visao_rede_estudo(
        rascunho, base_rede, principais, tabela_planos
    )
    assert visao.planos
    assert visao.apos_filtro_especialidade > 0
    algum_coberto = any(
        pr.coberto for pl in visao.planos for pr in pl.prestadores
    )
    assert algum_coberto


def test_14_plano_sem_mapeamento_rede_nao_mapeada(base_rede, principais, tabela_planos):
    rascunho = _rascunho_anistia_seis()
    visao = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela_planos,
        planos=[("Amil", "PRODUTO INEXISTENTE REDE XYZ")],
    )
    pl = visao.planos[0]
    assert pl.estado_mapeamento == EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA
    assert pl.prestadores == ()


def test_15_verticalizado_so_cobre_operadora(base_rede, principais, tabela_planos):
    alvo = None
    for p in base_rede.prestadores:
        meta = principais.por_prestador_matriz[p.chave]
        if "HAPVIDA" in normalizar_cabecalho(meta.rede_verticalizada):
            alvo = p
            break
    if alvo is None:
        pytest.skip("sem prestador verticalizado Hapvida na base")
    col_hap = next(
        (c for c in base_rede.colunas if c.operadora_canon == "Hapvida"), None
    )
    col_amil = next((c for c in base_rede.colunas if c.operadora_canon == "Amil"), None)
    if not col_hap or not col_amil:
        pytest.skip("colunas Hapvida/Amil ausentes")
    from newport_app.presentation.rede_visao import _coberto_na_coluna

    meta = principais.por_prestador_matriz[alvo.chave]
    cob_h, _ = _coberto_na_coluna(
        alvo, col_hap.col_idx, "Hapvida", entrada_principal=meta
    )
    cob_a, _ = _coberto_na_coluna(
        alvo, col_amil.col_idx, "Amil", entrada_principal=meta
    )
    if alvo.celulas.get(col_hap.col_idx):
        assert cob_h
    assert not cob_a


def test_16_gabarito_anistia(tmp_path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_17_rascunhos_compilam():
    rascunho = _rascunho_anistia_seis()
    assert compile(rascunho, policy_registry=default_registry).compilavel


def test_18_hash_snapshot_inalterado(tmp_path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h = hash_snapshot_canonico(nucleo)
    repo, _, snap_svc, _ = _stack(tmp_path, "hash-fase-c")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h


def test_19_html_export_inalterado(tmp_path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html


def test_20_fases_a_b_intactas(base_rede, tabela_planos):
    planos = _planos_estudo_reais()
    assert len(planos) == 55
    for op, pl in planos:
        r = resolver_casamento_rede(op, pl, base_rede.colunas, tabela=tabela_planos)
        assert r.estado in (EstadoCasamentoRede.ALIAS, EstadoCasamentoRede.REGRA)
    r = _parse_bytes(planilha_anistia_41_sintetica())
    assert r.candidata.estatisticas.localizacao_preenchida == 39


def _localizacoes_anistia_planilha() -> set[tuple[str, str]]:
    from pathlib import Path as P

    raizes = [P(r"C:\Users\tiago\Downloads"), ROOT / ".private" / "runtime"]
    path = None
    for raiz in raizes:
        if not raiz.is_dir():
            continue
        for hit in raiz.glob("POSI*.xlsx"):
            if "CADASTRAL" in hit.name.upper() and "IVTEC" not in hit.name.upper():
                path = hit
                break
    if path is None:
        pytest.skip("planilha Anistia real indisponível")
    r = parse_planilha_siscor(path.read_bytes(), estudo_id="funil", documento_id="doc")
    return {
        (l.uf, l.cidade)
        for l in r.candidata.linhas
        if l.uf and l.cidade
    }


def test_xlsx_ausente_falha(tmp_path):
    with pytest.raises(BaseRedeHospitalInvalida):
        carregar_base_rede_hospital(tmp_path / "nao_existe.xlsx")
