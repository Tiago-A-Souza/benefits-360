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
    rasc = rascunho.model_copy(update={"vidas": vidas, "cenarios": [cen]})
    return rasc, cen.id, prop_id


@pytest.fixture(scope="module")
def base_rede():
    xlsx = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"
    if not xlsx.is_file():
        pytest.skip("base SiscorNet ausente")
    return carregar_base_rede_hospital(xlsx)


def test_01_duas_secoes_dois_grupos():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc is not None
    assert len(doc.secoes) == 2


def test_02_quatro_colunas_total_um_cenario():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc is not None
    cols = sum(len(s.colunas) for s in doc.secoes)
    assert cols == 4
    for sec in doc.secoes:
        assert len(sec.colunas) == 2


def test_03_prestador_visao_tem_bairro_zona(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede

    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
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

    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
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
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    assert "Pontos de atenção" in html
    assert "Medservice" in html
    assert "centros clínicos" in html.lower() or "centros clinicos" in html.lower()


def test_07_documento_completo_zero_script(tmp_path: Path):
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    from newport_app.presentation.builder import construir_view_model

    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    html = render_html_completo(vm, vm, vm, rede=doc)
    assert "<script" not in html.lower()
    assert "visao-rede" in html


def test_08_quatro_abas_anteriores_intactas(tmp_path: Path):
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    snap = _aprovar_anistia(tmp_path, rascunho)
    from newport_app.presentation.builder import construir_view_model

    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    sem = render_html_completo(vm, vm, vm, rede=None)
    com = render_html_completo(
        vm,
        vm,
        vm,
        rede=montar_rede_apresentacao(rascunho, [cen_id]),
    )
    extrair = lambda h: re.search(r'id="visao-resumo"[^>]*>(.*?)</section>', h, re.S).group(1)
    assert extrair(sem) == extrair(com)


def test_09_rede_nao_mapeada(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede

    rascunho, _cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
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
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc.secoes[0].blocos
    bloco = doc.secoes[0].blocos[0]
    assert sum(bloco.contagem_por_coluna.values()) >= 0


def test_11_gabarito_html_financeiro_intacto(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html


def test_13_cabecalho_atual_sem_operadora_duplicada():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    assert "Contrato atual" in html
    assert "AMIL | AMIL" not in html
    assert html.count("<th") >= 4


def test_14_bairro_na_linha_prestador():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    assert "bairro-rede" in html or "POMPEIA" in html or "SANTANA" in html


def test_15_contagem_prestadores_cobertos_bate_celulas():
    from tests.fixtures.siscor.xlsx_builder import planilha_anistia_41_sintetica
    from newport_app.siscor_importer.parser import parse_planilha_siscor
    from newport_app.presentation.colisao_coluna import resolver_colunas_selecionadas
    from newport_app.presentation.rede_apresentacao import contagem_coberturas_bloco
    from newport_app.presentation.rede_renderer import _render_tabela_pagina
    from newport_app.snapshot.comparativo import ler_comparativo_congelado

    rascunho = _rascunho_anistia_seis()
    parsed = parse_planilha_siscor(
        planilha_anistia_41_sintetica(), estudo_id="t", documento_id="d"
    )
    vidas = []
    for v, lin in zip(rascunho.vidas, parsed.candidata.linhas, strict=True):
        vidas.append(
            v.model_copy(
                update={
                    "uf": (lin.uf or "").upper() if lin.uf else None,
                    "cidade": lin.cidade,
                }
            )
        )
    rascunho = rascunho.model_copy(update={"vidas": vidas})
    snap = _aprovar_anistia(ROOT / ".private" / "runtime", rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    calculadas = [p for p in matriz.propostas if p.calculo_realizado]
    cen_id = resolver_colunas_selecionadas([], calculadas)[0]
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc is not None
    sec = doc.secoes[0]
    bloco_barra = next(
        b
        for b in sec.blocos
        if any("RIO BARRA" in ln.prestador for ln in b.linhas)
    )
    ch_prop = next(c.chave for c in sec.colunas if c.chave != "rede-atual")
    cont = contagem_coberturas_bloco(bloco_barra.linhas, sec.colunas)
    assert cont["rede-atual"] > 0
    assert cont[ch_prop] > 0
    html = _render_tabela_pagina(sec.paginas[0])
    assert f"<td>{cont[ch_prop]}</td>" in html
    assert "Cobertos" in html


def test_16_tres_cenarios_uma_tabela_por_secao():
    from tests.fixtures.siscor.xlsx_builder import planilha_anistia_41_sintetica
    from newport_app.siscor_importer.parser import parse_planilha_siscor
    from newport_app.presentation.colisao_coluna import resolver_colunas_selecionadas
    from newport_app.snapshot.comparativo import ler_comparativo_congelado

    rascunho = _rascunho_anistia_seis()
    parsed = parse_planilha_siscor(
        planilha_anistia_41_sintetica(), estudo_id="t", documento_id="d"
    )
    vidas = []
    for v, lin in zip(rascunho.vidas, parsed.candidata.linhas, strict=True):
        vidas.append(
            v.model_copy(
                update={
                    "uf": (lin.uf or "").upper() if lin.uf else None,
                    "cidade": lin.cidade,
                }
            )
        )
    rascunho = rascunho.model_copy(update={"vidas": vidas})
    snap = _aprovar_anistia(ROOT / ".private" / "runtime", rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    calculadas = [p for p in matriz.propostas if p.calculo_realizado]
    cenarios_sel = resolver_colunas_selecionadas([], calculadas)[:3]
    doc = montar_rede_apresentacao(rascunho, cenarios_sel)
    assert doc is not None
    for sec in doc.secoes:
        assert len(sec.paginas) == 1
        assert len(sec.paginas[0].colunas) == 4
        assert sec.paginas[0].colunas[0].chave == "rede-atual"


def test_19_sirio_itaim_zo_bela_vista_zc(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede
    from newport_app.presentation.rede_codigos import sigla_zona_capital

    principais = carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base_rede.colunas)
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    sg = rascunho.subgrupos_atuais[1]
    vis = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela,
        planos=[(sg.operadora, sg.plano_nome)],
        localizacoes={("SP", "SAO PAULO")},
    )
    prest = vis.planos[0].prestadores
    itaim = next(
        p
        for p in prest
        if p.prestador == "HOSPITAL SIRIO LIBANES" and p.bairro == "ITAIM BIBI"
    )
    bela = next(
        p
        for p in prest
        if p.prestador == "HOSPITAL SIRIO LIBANES" and p.bairro == "BELA VISTA"
    )
    assert sigla_zona_capital(itaim.zona) == "ZO"
    assert sigla_zona_capital(bela.zona) == "ZC"


def test_20_sete_correcoes_zona_sp(base_rede):
    from newport_app.presentation.hospitais_principais import carregar_hospitais_principais
    from newport_app.presentation.planos_rede import carregar_aliases_rede
    from newport_app.presentation.rede_codigos import sigla_zona_capital

    principais = carregar_hospitais_principais(prestadores_matriz=base_rede.prestadores)
    tabela = carregar_aliases_rede(colunas_rede=base_rede.colunas)
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    sg = rascunho.subgrupos_atuais[1]
    vis = montar_visao_rede_estudo(
        rascunho,
        base_rede,
        principais,
        tabela,
        planos=[(sg.operadora, sg.plano_nome)],
        localizacoes={("SP", "SAO PAULO")},
    )
    prest = vis.planos[0].prestadores

    def sigla(prestador: str, bairro: str) -> str:
        p = next(x for x in prest if x.prestador == prestador and x.bairro == bairro)
        return sigla_zona_capital(p.zona)

    # HOSP E MATER SAO LUIZ - REDE DOR / ITAIM BIBI saiu na extração 17/11.
    assert sigla("HOSPITAL SIRIO LIBANES", "ITAIM BIBI") == "ZO"
    assert sigla("HOSPITAL ALVORADA MOEMA", "MOEMA") == "ZS"
    assert sigla("HOSP ADVENTISTA DE SAO PAULO", "CAPAO REDONDO") == "ZS"
    assert sigla("HOSPITAL SANTA PAULA", "VILA OLIMPIA") == "ZO"
    assert sigla("HOSPITAL VILA NOVA STAR - REDE DOR", "VILA NOVA CONCEICAO") == "ZO"
    assert sigla("MATERNIDADE STAR - REDE DOR", "VILA OLIMPIA") == "ZO"


def test_18_deduplica_mesmo_plano_em_dois_cenarios():
    rascunho, cen_id, prop_id = _rascunho_dois_grupos_um_cenario()
    op = rascunho.opcoes_proposta[0]
    cen_b = CenarioRascunho(
        id="c-d1-dup",
        rotulo="Dup",
        atribuicoes=[
            AtribuicaoRascunho(
                id="a2-a",
                alvo_tipo="subgrupo",
                alvo_id="sg-a",
                opcao_plano_id=prop_id,
            ),
            AtribuicaoRascunho(
                id="a2-b",
                alvo_tipo="subgrupo",
                alvo_id="sg-b",
                opcao_plano_id=prop_id,
            ),
        ],
    )
    rasc = rascunho.model_copy(update={"cenarios": [rascunho.cenarios[0], cen_b]})
    doc = montar_rede_apresentacao(rasc, [cen_id, "c-d1-dup"])
    assert doc is not None
    assert len(doc.secoes[0].colunas) == 2


def test_17_prefixo_zona_na_linha_nao_no_bloco():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    assert "ZONA NORTE" not in html or "· ZONA" not in html
    assert "ZN " in html or "ZO " in html or "ZS " in html


def test_12_anistia_contagem_por_secao(capfd):
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    for sec in doc.secoes:
        print(f"SEC {sec.rotulo} linhas={sec.total_linhas}")
    assert doc.secoes[0].total_linhas > 0
    assert doc.secoes[1].total_linhas > 0


def test_18_cabecalho_repetido_por_bloco_municipio():
    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    from newport_app.presentation.rede_renderer import render_corpo_rede

    html = render_corpo_rede(doc)
    n_blocos = sum(len(p.blocos) for s in doc.secoes for p in s.paginas)
    n_tabelas = sum(len(s.paginas) for s in doc.secoes)
    n_labs = html.count("tabela-labs")
    assert html.count("rede-cab-repetido") == n_blocos - n_tabelas
    assert html.count("class='bloco-rede'") == n_blocos + n_labs
    idx = html.find("bloco-rede")
    assert idx >= 0
    trecho = html[idx : idx + 600]
    assert "rede-cab-repetido" not in trecho
    assert "class='p-rede'" in trecho or "p-rede" in trecho


def test_19_cabecalho_rede_sticky_e_nomes_encurtados(tmp_path: Path):
    from newport_app.presentation.nome_plano_exibicao import nome_plano_documento
    from newport_app.presentation.rede_renderer import render_corpo_rede

    rascunho, cen_id, _prop_id = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    html_rede = render_corpo_rede(doc)
    assert "rede-rolo" in html_rede
    html_doc, _ = _html_de(tmp_path, rascunho)
    assert ".tabela-rede thead th{position:sticky" in html_doc
    for col in doc.secoes[0].colunas:
        curto = nome_plano_documento(col.plano_nome)
        assert f"<span class='pl'>{curto}</span>" in html_rede


def _anistia_seis_com_localizacao():
    from newport_app.siscor_importer.parser import parse_planilha_siscor
    from tests.fixtures.siscor.xlsx_builder import planilha_anistia_41_sintetica
    from tests.test_frente2_grupo_familiar import _anistia_com_vinculos

    rascunho = _anistia_com_vinculos()
    parsed = parse_planilha_siscor(
        planilha_anistia_41_sintetica(), estudo_id="t", documento_id="d"
    )
    vidas = []
    for v, lin in zip(rascunho.vidas, parsed.candidata.linhas, strict=True):
        vidas.append(
            v.model_copy(
                update={
                    "uf": (lin.uf or "").upper() if lin.uf else None,
                    "cidade": lin.cidade,
                }
            )
        )
    return rascunho.model_copy(update={"vidas": vidas})


def _doc_anistia_seis_rede(tmp_path: Path):
    from newport_app.presentation.colisao_coluna import resolver_colunas_selecionadas
    from newport_app.snapshot.comparativo import ler_comparativo_congelado

    rascunho = _anistia_seis_com_localizacao()
    snap = _aprovar_anistia(tmp_path, rascunho)
    matriz = ler_comparativo_congelado(snap.payload)
    calculadas = [p for p in matriz.propostas if p.calculo_realizado]
    cen_ids = resolver_colunas_selecionadas([], calculadas)
    doc = montar_rede_apresentacao(rascunho, cen_ids)
    assert doc is not None
    return doc, rascunho


def test_20_omite_prestador_sem_cobertura_em_nenhuma_coluna(tmp_path: Path):
    from newport_app.presentation.rede_renderer import render_corpo_rede

    doc, _ = _doc_anistia_seis_rede(tmp_path)
    bloco_belem = next(
        b for b in doc.secoes[0].blocos if "BELEM" in b.titulo.upper()
    )
    assert not any("HOSP RIO MAR" in ln.prestador.upper() for ln in bloco_belem.linhas)
    html = render_corpo_rede(doc)
    assert "HOSP RIO MAR" not in html.upper()
    assert f"{len(bloco_belem.linhas)} prestadores" in html


def test_21_belem_mantem_prestador_so_contrato_atual(tmp_path: Path):
    from newport_app.presentation.rede_apresentacao import (
        _valor_conta_cobertura,
        linha_tem_cobertura_na_secao,
    )
    from newport_app.presentation.rede_renderer import render_corpo_rede

    doc, _ = _doc_anistia_seis_rede(tmp_path)
    sec = doc.secoes[0]
    bloco_belem = next(b for b in sec.blocos if "BELEM" in b.titulo.upper())
    props = [c for c in sec.colunas if c.chave != "rede-atual"]
    maradei = next(
        ln
        for ln in bloco_belem.linhas
        if "MARADEI" in ln.prestador.upper()
    )
    assert _valor_conta_cobertura(maradei.celulas.get("rede-atual"))
    assert not any(
        _valor_conta_cobertura(maradei.celulas.get(c.chave)) for c in props
    )
    assert linha_tem_cobertura_na_secao(maradei, sec.colunas)
    html = render_corpo_rede(doc)
    assert "MARADEI" in html.upper()
    assert maradei.prestador.upper() in html.upper()
