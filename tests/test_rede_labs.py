"""Bloco Labs — ingestão, recorte com acento, marcas e cobertura binária."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pytest

from newport_app.presentation.laboratorios_principais import (
    BaseLaboratoriosPrincipaisInvalida,
    carregar_laboratorios_principais,
    casar_unidades_marca,
    limpar_cache_laboratorios_principais,
)
from newport_app.presentation.planos_rede import carregar_colunas_rede_xlsx
from newport_app.presentation.rede_matriz_hospital import (
    CAMINHO_XLSX_PADRAO,
    carregar_base_rede_hospital,
)
from newport_app.presentation.rede_matriz_laboratorio import (
    carregar_base_rede_laboratorio,
    limpar_cache_base_rede_laboratorio,
)
from newport_app.presentation.planos_rede import carregar_aliases_rede
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_labs import (
    MARCA_COBERTURA,
    casar_planos_laboratorio,
    recortar_laboratorios,
)
from newport_app.presentation.rede_visao import EstadoMapeamentoPlanoRede
from newport_app.services.rede_selecao import excluidos_rede, salvar_selecao_rede
from newport_app.services.rede_selecao_ui import montar_rede_selecao_ui
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario
from newport_app.presentation.rede_recorte import (
    municipios_permitidos,
    parse_municipio_base,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"

CASAMENTO_MARCAS_ESPERADO = {
    "Delboni": {
        "unidades": 10,
        "municipios": {
            "PR.CURITIBA",
            "SP.BARUERI",
            "SP.COTIA",
            "SP.GUARULHOS",
            "SP.OSASCO",
            "SP.SANTO ANDRE",
            "SP.SANTOS",
            "SP.SAO BERNARDO DO CAMPO",
            "SP.SAO PAULO",
        },
    },
    "Lavoisier": {
        "unidades": 14,
        "municipios": {
            "SP.BARUERI",
            "SP.CARAPICUIBA",
            "SP.COTIA",
            "SP.DIADEMA",
            "SP.FRANCISCO MORATO",
            "SP.GUARULHOS",
            "SP.ITAPEVI",
            "SP.MAUA",
            "SP.OSASCO",
            "SP.SANTO ANDRE",
            "SP.SANTOS",
            "SP.SAO BERNARDO DO CAMPO",
            "SP.SAO CAETANO DO SUL",
            "SP.SAO PAULO",
        },
    },
    "CDB": {
        "unidades": 4,
        "municipios": {"SP.MOGI DAS CRUZES", "SP.SAO BERNARDO DO CAMPO", "SP.SAO PAULO"},
    },
    "Femme": {"unidades": 2, "municipios": {"SP.OSASCO", "SP.SAO PAULO"}},
    "Pardini": {
        "unidades": 8,
        "municipios": {
            "MG.BELO HORIZONTE",
            "RJ.RIO DE JANEIRO",
            "SP.GUARULHOS",
            "SP.MOGI DAS CRUZES",
            "SP.OSASCO",
            "SP.SANTO ANDRE",
            "SP.SAO BERNARDO DO CAMPO",
            "SP.SAO PAULO",
        },
    },
    "Salomão": {"unidades": 2, "municipios": {"SP.OSASCO", "SP.SAO PAULO"}},
    "A+ Medicina Diagnóstica": {
        "unidades": 13,
        "municipios": {
            "BA.SALVADOR",
            "PE.RECIFE",
            "PR.CURITIBA",
            "RJ.RIO DE JANEIRO",
            "RS.PORTO ALEGRE",
            "SP.BARUERI",
            "SP.COTIA",
            "SP.GUARULHOS",
            "SP.OSASCO",
            "SP.SANTO ANDRE",
            "SP.SAO BERNARDO DO CAMPO",
            "SP.SAO PAULO",
        },
    },
    "Bittar": {"unidades": 1, "municipios": {"RJ.RIO DE JANEIRO"}},
    "Lamina": {"unidades": 1, "municipios": {"RJ.RIO DE JANEIRO"}},
    "Bronstein": {"unidades": 1, "municipios": {"RJ.RIO DE JANEIRO"}},
}


@pytest.fixture(scope="module")
def base_lab():
    if not _XLSX.is_file():
        pytest.skip("XLSX SiscorNet ausente em docs/")
    limpar_cache_base_rede_laboratorio()
    return carregar_base_rede_laboratorio(_XLSX)


@pytest.fixture(scope="module")
def base_hospital():
    if not _XLSX.is_file():
        pytest.skip("XLSX SiscorNet ausente em docs/")
    return carregar_base_rede_hospital(_XLSX)


def test_p1_parse_municipio_sao_paulo_com_acento_nao_some():
    """SP.SÃO PAULO da planilha casa com vidas em São Paulo após normalizar."""
    uf, cidade = parse_municipio_base("SP.SÃO PAULO")
    assert uf == "SP"
    assert cidade == "SAO PAULO"
    assert cidade == normalizar_cabecalho("São Paulo")
    perm = municipios_permitidos({("SP", "São Paulo")}, {"SP.SAO PAULO"})
    assert "SP.SAO PAULO" in perm
    perm_raw = municipios_permitidos({("SP", "SÃO PAULO")}, {"SP.SAO PAULO"})
    assert "SP.SAO PAULO" in perm_raw


def test_p1_ingestao_2683_sem_filtro_hger(base_lab):
    assert len(base_lab.prestadores) == 2683
    assert len(base_lab.municipios) == 52
    assert "SP.SAO PAULO" in base_lab.municipios
    assert any(p.chave_municipio == "SP.SAO PAULO" for p in base_lab.prestadores)
    assert len(base_lab.colunas) == 189
    com_celula = [p for p in base_lab.prestadores if p.celulas]
    assert len(com_celula) >= 2600
    amostra = next(p for p in base_lab.prestadores if "ULTRA" in " ".join(p.celulas.values()))
    assert amostra.celulas


def test_p1_colunas_lab_identicas_ao_hospital(base_lab, base_hospital):
    lab = {(c.col_idx, c.operadora_raw, c.linha, c.plano) for c in base_lab.colunas}
    hosp = {(c.col_idx, c.operadora_raw, c.linha, c.plano) for c in base_hospital.colunas}
    assert lab == hosp
    via_aba = carregar_colunas_rede_xlsx(_XLSX, aba="Matriz_Laboratorio")
    assert len(via_aba) == 189


def test_p1_csv_marcas_na_ordem_e_casamento(base_lab):
    limpar_cache_laboratorios_principais()
    base = carregar_laboratorios_principais()
    nomes = [m.marca for m in base.marcas if m.ativo]
    assert nomes == [
        "Delboni",
        "Lavoisier",
        "CDB",
        "Femme",
        "Pardini",
        "Salomão",
        "A+ Medicina Diagnóstica",
        "Bittar",
        "Lamina",
        "Bronstein",
    ]
    assert next(m for m in base.marcas if m.marca == "Bittar").ufs == frozenset({"RJ"})
    pares = casar_unidades_marca(base_lab.prestadores, base.marcas)
    por_marca: dict[str, list] = defaultdict(list)
    for u in pares:
        por_marca[u.marca].append(u.prestador)
    sem_unidade = [m for m in nomes if m not in por_marca]
    assert sem_unidade == [], f"marcas sem unidade na matriz: {sem_unidade}"
    for marca, esperado in CASAMENTO_MARCAS_ESPERADO.items():
        uns = por_marca[marca]
        muns = {p.chave_municipio for p in uns}
        assert len(uns) == esperado["unidades"], (
            f"{marca}: {len(uns)} unidades, esperado {esperado['unidades']}; "
            f"municípios {sorted(muns)}"
        )
        assert muns == esperado["municipios"], (
            f"{marca}: municípios {sorted(muns)} != {sorted(esperado['municipios'])}"
        )
    # Hospitais da aba lab não casam com marca nenhuma (Samaritano, Albert Sabin).
    nomes_casados = {u.prestador.prestador for u in pares}
    assert "HOSPITAL SAMARITANO" not in nomes_casados
    assert not any("ALBERT SABIN" in n.upper() for n in nomes_casados)


def test_p1_csv_malformado_cita_linha(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("marca;padroes_nome;ufs;ativo\nDelboni\n", encoding="utf-8-sig")
    with pytest.raises(BaseLaboratoriosPrincipaisInvalida, match="registro 2"):
        carregar_laboratorios_principais(bad)


def test_p2_recorte_sao_paulo_com_acento(base_lab):
    mun, labs = recortar_laboratorios(base_lab, {("SP", "São Paulo")})
    assert "SP.SAO PAULO" in mun
    assert len(labs) == 199
    assert all(p.chave_municipio == "SP.SAO PAULO" for p in labs)


def test_p2_recorte_atibaia_inclui_capital(base_lab):
    mun, labs = recortar_laboratorios(base_lab, {("SP", "Atibaia")})
    assert mun == frozenset({"SP.ATIBAIA", "SP.SAO PAULO"})
    assert {p.chave_municipio for p in labs} == mun
    assert len(labs) == 208


def test_p3_casamento_igual_ao_hospital(base_lab, base_hospital):
    tabela = carregar_aliases_rede(colunas_rede=base_lab.colunas)
    from tests.test_correcao_resumo_regime import _rascunho_anistia_seis

    rasc = _rascunho_anistia_seis()
    pares = [(sg.operadora, sg.plano_nome) for sg in rasc.subgrupos_atuais]
    pares += [(op.operadora, op.plano_nome) for op in rasc.opcoes_proposta]
    lab = casar_planos_laboratorio(pares, base_lab.colunas, tabela)
    hosp = casar_planos_laboratorio(pares, base_hospital.colunas, tabela)
    assert [(c.operadora, c.plano_nome, c.estado, c.col_idx) for c in lab] == [
        (c.operadora, c.plano_nome, c.estado, c.col_idx) for c in hosp
    ]
    fake = casar_planos_laboratorio(
        [("Amil", "plano que nao existe xyz")], base_lab.colunas, tabela
    )
    assert fake[0].estado == EstadoMapeamentoPlanoRede.REDE_NAO_MAPEADA
    assert fake[0].col_idx is None


def test_p2_recorte_niteroi_so_capital(base_lab):
    mun, labs = recortar_laboratorios(base_lab, {("RJ", "Niterói")})
    assert mun == frozenset({"RJ.RIO DE JANEIRO"})
    assert len(labs) == 178


def test_p4_bloco_sp_e_rj_por_marca(base_lab):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc is not None
    assert len(doc.secoes) == 2
    por_sg = {s.subgrupo_id: s for s in doc.secoes}
    sp = next(s for s in doc.secoes if s.labs and "Delboni" in [ln.marca for ln in s.labs.linhas])
    rj = next(s for s in doc.secoes if s.labs and "Bittar" in [ln.marca for ln in s.labs.linhas])
    assert {ln.marca for ln in sp.labs.linhas} == {
        "Delboni",
        "Lavoisier",
        "CDB",
        "Femme",
        "Pardini",
        "Salomão",
        "A+ Medicina Diagnóstica",
    }
    assert [ln.marca for ln in sp.labs.linhas] == [
        "Delboni",
        "Lavoisier",
        "CDB",
        "Femme",
        "Pardini",
        "Salomão",
        "A+ Medicina Diagnóstica",
    ]
    assert {ln.marca for ln in rj.labs.linhas} == {
        "Pardini",
        "A+ Medicina Diagnóstica",
        "Bittar",
        "Lamina",
        "Bronstein",
    }
    assert MARCA_COBERTURA in {
        val for ln in sp.labs.linhas for val in ln.celulas.values()
    }
    for ln in sp.labs.linhas:
        for val in ln.celulas.values():
            assert val in {MARCA_COBERTURA, "", "—"}
            assert "ULTRA" not in val
            assert "ACLIN" not in val
    assert por_sg[sp.subgrupo_id].paginas[0].labs is not None
    ui = montar_rede_selecao_ui(rascunho)
    ui_sp = next(s for s in ui.secoes if s.subgrupo_id == sp.subgrupo_id)
    assert ui_sp.laboratorios is not None
    assert [ln.marca for ln in ui_sp.laboratorios.linhas] == [
        ln.marca for ln in sp.labs.linhas
    ]
    # Seleção gravada não muda por causa dos labs.
    lid = sp.blocos[0].linhas[0].linha_id
    salvar_selecao_rede(rascunho, [lid], revisada=True)
    assert excluidos_rede(rascunho) == {lid}
    ui2 = montar_rede_selecao_ui(rascunho)
    ui2_sp = next(s for s in ui2.secoes if s.subgrupo_id == sp.subgrupo_id)
    assert ui2_sp.laboratorios is not None
    assert len(ui2_sp.laboratorios.linhas) == len(sp.labs.linhas)


def test_p4_sem_marca_no_recorte_bloco_ausente(base_lab):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    vidas = [
        v.model_copy(update={"uf": "AC", "cidade": "RIO BRANCO"}) for v in rascunho.vidas
    ]
    rasc = rascunho.model_copy(update={"vidas": vidas})
    doc = montar_rede_apresentacao(rasc, [cen_id])
    assert doc is not None
    for sec in doc.secoes:
        assert sec.labs is None
        for pag in sec.paginas:
            assert pag.labs is None
    ui = montar_rede_selecao_ui(rasc)
    for sec in ui.secoes:
        assert sec.laboratorios is None


def test_p1_lamina_fora_do_rj_nao_casa(base_lab):
    lamina = next(
        m for m in carregar_laboratorios_principais().marcas if m.marca == "Lamina"
    )
    df = [p for p in base_lab.prestadores if p.uf == "DF" and "LAMINA" in p.prestador.upper()]
    assert df
    pares = casar_unidades_marca(tuple(df), (lamina,))
    assert pares == ()
