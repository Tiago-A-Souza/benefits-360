"""Seleção do SUSEP no dropdown clicável (simulador). Códigos fictícios AAAAAA/BBBBBB/CCCCCC/ZZZZZZ."""
from __future__ import annotations

import pytest
from playwright.sync_api import sync_playwright

from operadoras.porto.seletores import (
    SusepNaoEncontrada,
    escolher_susep,
    mensagem_susep_ausente,
    normalizar_susep,
)
from operadoras.porto.simulador.servidor import Simulador

COD_P = "AAAAAA"
COD_SEM = "BBBBBB"
COD_TERCEIRO = "CCCCCC"
COD_INEXISTENTE = "ZZZZZZ"


@pytest.fixture()
def sim_base():
    s = Simulador()
    s.codigos_susep = [COD_P, COD_SEM, COD_TERCEIRO]
    s.susep_com_p = {COD_P}
    yield s
    s.parar()


def _iniciar(sim, *, modo: str, atraso: int = 0, unicos=None):
    sim.dropdown_susep = modo
    sim.atraso_susep_ms = atraso
    if unicos is not None:
        sim.codigos_susep = list(unicos)
        sim.susep_com_p = {unicos[0]} if unicos else set()
    sim.iniciar()
    return sim


def _abrir_dropdown(page, sim):
    page.goto(sim.url_login)
    page.get_by_label("CPF").fill(Simulador.CPF)
    page.get_by_label("Senha").fill(Simulador.SENHA)
    page.get_by_role("button", name="ENTRAR").click()
    page.wait_for_url("**/susep")


@pytest.mark.parametrize("modo", ["select", "menu"])
@pytest.mark.parametrize(
    "pedido,esperado",
    [
        (COD_P, COD_P),
        (f"{COD_P} (P)", COD_P),
        (COD_P.lower(), COD_P),
        (COD_SEM, COD_SEM),
    ],
)
def test_escolhe_codigo_exato_sem_p_e_minusculas(sim_base, modo, pedido, esperado):
    sim = _iniciar(sim_base, modo=modo)
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        _abrir_dropdown(page, sim)
        escolher_susep(page, pedido)
        page.wait_for_url("**/home")
        assert sim.susep_escolhida == esperado
        page.context.browser.close()


@pytest.mark.parametrize("modo", ["select", "menu"])
def test_codigo_inexistente_erro_com_lista_mascarada(sim_base, modo):
    sim = _iniciar(sim_base, modo=modo)
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        _abrir_dropdown(page, sim)
        with pytest.raises(SusepNaoEncontrada) as ei:
            escolher_susep(page, COD_INEXISTENTE)
        msg = mensagem_susep_ausente(ei.value.rotulos)
        assert COD_P not in msg and COD_SEM not in msg and COD_INEXISTENTE not in msg
        assert "AA**AA" in msg and "BB**BB" in msg
        assert "precisa ser um deles" in msg
        assert sim.susep_escolhida == ""
        page.context.browser.close()


@pytest.mark.parametrize("modo", ["select", "menu"])
def test_carregamento_tardio_das_opcoes(sim_base, modo):
    sim = _iniciar(sim_base, modo=modo, atraso=800)
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        _abrir_dropdown(page, sim)
        escolher_susep(page, COD_P.lower())
        page.wait_for_url("**/home", timeout=15000)
        assert sim.susep_escolhida == COD_P
        page.context.browser.close()


@pytest.mark.parametrize("modo", ["select", "menu"])
def test_unico_susep_e_usado_mesmo_se_o_pedido_nao_bater(sim_base, modo):
    sim = _iniciar(sim_base, modo=modo, unicos=[COD_P])
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        _abrir_dropdown(page, sim)
        escolher_susep(page, COD_INEXISTENTE)
        page.wait_for_url("**/home")
        assert sim.susep_escolhida == COD_P
        page.context.browser.close()


def test_menu_nao_aceita_digitar(sim_base):
    sim = _iniciar(sim_base, modo="menu")
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        _abrir_dropdown(page, sim)
        caixa = page.get_by_role("combobox", name="SUSEP")
        caixa.click()
        page.keyboard.type(COD_P)
        page.wait_for_timeout(400)
        assert sim.susep_escolhida == ""
        page.locator("[role=option]").filter(has_text=COD_P).click()
        page.wait_for_url("**/home")
        assert sim.susep_escolhida == COD_P
        page.context.browser.close()


def test_normalizar_ignora_espacos_e_sufixo():
    assert normalizar_susep(f"  {COD_P.lower()} (P)  ") == COD_P
    assert normalizar_susep(COD_SEM) == COD_SEM
