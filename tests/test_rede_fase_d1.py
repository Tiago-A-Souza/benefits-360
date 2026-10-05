"""REDE fase D1 — aba estática no documento HTML."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.planos_rede import (
    EstadoCasamentoRede,
    carregar_aliases_rede,
    resolver_casamento_rede,
)
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_codigos import formatar_cobertura_abreviada
from newport_app.presentation.rede_matriz_hospital import carregar_base_rede_hospital
from newport_app.presentation.rede_visao import montar_visao_rede_estudo
from newport_app.presentation.regras_comerciais import carregar_aliases
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_regras_comerciais import _html_de

ROOT = Path(__file__).resolve().parents[1]


def _rascunho_dois_grupos_um_cenario():
    rascunho = _rascunho_anistia_seis()
    vidas = []
    for v in rascunho.vidas:
        uf, cidade = "RJ", "RIO DE JANEIRO"
        if v.subgrupo_atual_id == "sg-b":
            uf, cidade = "SP", "SAO PAULO"
        vidas.append(v.model_copy(update={"uf": uf, "cidade": cidade}))
    prop_id = rascunho.opcoes_proposta[0].id
    atrib = []
    for sg in rascunho.subgrupos_atuais:
        atrib.append(
            AtribuicaoRascunho(
                id=f"a-{sg.id[:6]}",
                alvo_tipo="subgrupo",
                alvo_id=sg.id,
                opcao_plano_id=prop_id,
            )
        )
    cen = CenarioRascunho(id="c-d1-test", rotulo="Cenário teste", atribuicoes=atrib)
    return rascunho.model_copy(update={"vidas": vidas, "cenarios": [cen]}), prop_id


@pytest.fixture(scope="module")
def base_rede():
    xlsx = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"
    if not xlsx.is_file():
        pytest.skip("base SiscorNet ausente")
    return carregar_base_rede_hospital(xlsx)


def test_01_duas_secoes_dois_grupos():
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    assert doc is not None
    assert len(doc.secoes) == 2


def test_02_quatro_colunas_total_um_cenario():
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    assert doc is not None
    cols = sum(len(s.colunas) for s in doc.secoes)
    assert cols == 4
    for sec in doc.secoes:
        assert len(sec.colunas) == 2


def test_03_prestador_visao_tem_bairro_zona(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede

    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    sg = rascunho.subgrupos_atuais[1]
    principais = carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base_rede.colunas)
    op = rascunho.opcoes_proposta[0]
    vis = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela,
        planos=[(sg.operadora, sg.plano_nome)],
    )
    einstein = [
        p
        for p in vis.planos[0].prestadores
        if p.principal
        and p.prestador == "HOSPITAL ALBERT EINSTEIN"
        and p.chave_municipio == "SP.SAO PAULO"
    ]
    assert len(einstein) >= 4
    zonas = {p.zona for p in einstein}
    assert len(zonas) >= 2
    assert "ZONA SUL" in zonas and "ZONA OESTE" in zonas
    assert all(p.bairro for p in einstein)


def test_04_sao_camilo_pompeia_zona_oeste(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede

    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    principais = carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base_rede.colunas)
    sg = next(s for s in rascunho.subgrupos_atuais if s.id == "sg-b")
    vis = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela,
        planos=[(sg.operadora, sg.plano_nome)],
    )
    pompeia = next(
        p
        for p in vis.planos[0].prestadores
        if p.prestador == "HOSPITAL SAO CAMILO"
        and p.bairro == "POMPEIA"
        and p.principal
    )
    santana = next(
        p
        for p in vis.planos[0].prestadores
        if p.prestador == "HOSPITAL SAO CAMILO"
        and p.bairro == "SANTANA"
        and p.principal
    )
    assert pompeia.zona.upper() == "ZONA OESTE"
    assert santana.zona.upper() == "ZONA NORTE"


def test_05_codigos_abreviados():
    assert formatar_cobertura_abreviada("HGER - PSGER", coberto=True) == "H PS"
    assert formatar_cobertura_abreviada("HD", coberto=True) == "HD"
    assert formatar_cobertura_abreviada("HGER", coberto=False) == ""


def test_06_rodape_tres_ressalvas():
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    assert "Pontos de atenção" in html
    assert "Medservice" in html
    assert "centros clínicos" in html.lower() or "centros clinicos" in html.lower()


def test_07_zero_script_no_html_completo(tmp_path: Path):
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    from newport_app.presentation.builder import construir_view_model

    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[prop_id])
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    html = render_html_completo(vm, vm, vm, rede=doc)
    assert "<script" not in html.lower()


def test_08_quatro_abas_anteriores_intactas(tmp_path: Path):
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    from newport_app.presentation.builder import construir_view_model

    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[prop_id])
    sem = render_html_completo(vm, vm, vm, rede=None)
    com = render_html_completo(vm, vm, vm, rede=montar_rede_apresentacao(rascunho, [prop_id]))
    extrair = lambda h: re.search(r'id="visao-resumo"[^>]*>(.*?)</section>', h, re.S).group(1)
    assert extrair(sem) == extrair(com)


def test_09_rede_nao_mapeada(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede

    rascunho, _ = _rascunho_dois_grupos_um_cenario()
    principais = carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base_rede.colunas)
    vis = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela,
        planos=[("Amil", "PRODUTO INEXISTENTE REDE XYZ")],
    )
    assert vis.planos[0].estado_mapeamento.value == "rede_nao_mapeada"


def test_10_contagem_por_bloco():
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    assert doc.secoes[0].blocos
    bloco = doc.secoes[0].blocos[0]
    assert sum(bloco.contagem_por_coluna.values()) >= 0


def test_11_gabarito_html_financeiro_intacto(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html


def test_12_anistia_contagem_por_secao(capfd):
    rascunho, prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [prop_id])
    for sec in doc.secoes:
        print(f"SEC {sec.rotulo} linhas={sec.total_linhas}")
    assert doc.secoes[0].total_linhas > 0
    assert doc.secoes[1].total_linhas > 0
