"""Página pública da Porto: localização, cookies, botão e janela de login (códigos fictícios)."""
from __future__ import annotations

import json

import pytest
import yaml
from playwright.sync_api import sync_playwright

from nucleo.credenciais import Cofre, CofreMemoria
from nucleo.navegador import ARGS_SEM_PAUSA, _sem_guardar_formularios
from operadoras.porto import seletores as sel
from operadoras.porto.login import _clicar_acessar_corretor, entrar
from operadoras.porto.simulador.servidor import Simulador
from operadoras.porto.telas import _visivel, fechar_banners_entrada, logado

COD = "AAAAAA"


@pytest.fixture()
def sim():
    s = Simulador()
    s.codigos_susep = [COD]
    s.susep_com_p = {COD}
    s.susep = COD
    s.iniciar()
    yield s
    s.parar()


@pytest.fixture(autouse=True)
def login_falso(sim):
    CofreMemoria.esvaziar()
    Cofre("porto", memoria=True).guardar(cpf=Simulador.CPF, senha=Simulador.SENHA, susep=COD)
    yield
    CofreMemoria.esvaziar()


def _cfg(tmp_path, sim):
    secao = {"urls": {"login": sim.url, "cotador": sim.url_home},
             "tempos": {"timeout_login_ms": 20000, "timeout_tela_ms": 15000}}
    return {"geral": {"pasta_saida": str(tmp_path / "saida"), "modo_visual": False, "lentidao_ms": 0,
                      "mapear": True, "pausa_entre_pedidos_s": 0},
            "teste": {"cofre": "memoria"}, "operadoras": {"porto": secao}}


def _sessao(tmp_path, sim, pw, avisos):
    import operadoras
    from nucleo.estado import Estado
    from nucleo.navegador import Mapeador, abrir
    from nucleo.registro import carregar_config, configurar_log

    (tmp_path / "config.yaml").write_text(yaml.safe_dump(_cfg(tmp_path, sim), allow_unicode=True), encoding="utf-8")
    op = operadoras.obter("porto")
    cfg = op.config(carregar_config(tmp_path / "config.yaml"))
    pasta = tmp_path / "saida" / "porto"
    log = configurar_log(pasta / "logs")
    contexto, page = abrir(pw, cfg)
    s = op.nova_sessao(cfg, log, contexto, page, Estado(pasta / "estado.json"),
                       op.resultados(pasta / "resultados.xlsx", log),
                       Mapeador(pasta, True, log), True,
                       avisar=lambda tipo, **d: avisos.append((tipo, d)))
    return s, contexto


def test_chromium_recusa_localizacao_sem_clique(tmp_path):
    assert "--deny-permission-prompts" in ARGS_SEM_PAUSA
    _sem_guardar_formularios(tmp_path)
    prefs = json.loads((tmp_path / "Default" / "Preferences").read_text(encoding="utf-8"))
    assert prefs["profile"]["default_content_setting_values"]["geolocation"] == 2
    assert prefs["profile"]["default_content_setting_values"]["notifications"] == 2


def test_fecha_aviso_de_localizacao_e_cookies(sim):
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.goto(sim.url)
        assert page.get_by_text("sua localização").count()
        assert page.get_by_text("Usamos cookies").count()
        fechar_banners_entrada(page)
        assert page.locator("#aviso-localizacao").count() == 0
        assert page.locator("#aviso-cookies").count() == 0
        page.context.browser.close()


def test_botao_do_header_e_button_mesmo_com_senha_escondida(sim):
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.goto(sim.url)
        fechar_banners_entrada(page)
        botao = sel.botao_acessar_corretor(page)
        assert botao.first.is_visible()
        assert page.get_by_role("button", name=sel._RX_BOTAO_CORRETOR).count() == 1
        assert sel.login_campo_senha(page).count() >= 1
        assert not _visivel(sel.login_campo_senha(page))
        assert _clicar_acessar_corretor(page)
        page.wait_for_url("**/login")
        page.context.browser.close()


def test_entrar_pela_pagina_publica_abre_janela_e_loga(tmp_path, sim):
    avisos = []
    with sync_playwright() as pw:
        s, contexto = _sessao(tmp_path, sim, pw, avisos)
        entrar(s)
        assert logado(s.page)
        assert sim.susep_escolhida == COD
        contexto.close()
    etapas = [d.get("etapa") for t, d in avisos if t == "etapa"]
    for pedaco in ("abrindo login", "janela do corretor online", "CPF e senha enviados", "SUSEP selecionado", "logado"):
        assert pedaco in etapas, etapas
    logs = "".join(p.read_text(encoding="utf-8") for p in (tmp_path / "saida" / "porto" / "logs").glob("*.log"))
    assert Simulador.CPF not in logs
    assert Simulador.SENHA not in logs
    assert COD not in logs
    mapas = list((tmp_path / "saida" / "porto" / "mapa").rglob("*.png"))
    assert any("entrada_porto" in p.name for p in mapas)
    assert not any(COD.lower() in p.name.lower() for p in mapas)
