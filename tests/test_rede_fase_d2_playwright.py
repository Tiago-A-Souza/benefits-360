"""REDE fase D2 — interação real no navegador (Playwright)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, sync_playwright  # noqa: E402

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.presentation.rede_sandbox import nome_arquivo_para_cliente
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"
ESTUDO_ID = "pw-rede-d2-e2e"


@pytest.fixture(scope="module")
def html_trabalho(tmp_path_factory) -> tuple[Path, str]:
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    tmp = tmp_path_factory.mktemp("rede_pw")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": ESTUDO_ID})
    snap = _aprovar_anistia(tmp, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    nome_origem = "apresentacao_completo_pw.html"
    html = render_html_completo(
        vm,
        vm,
        vm,
        rede=doc,
        estudo_id=ESTUDO_ID,
        nome_arquivo_html=nome_origem,
    )
    path = tmp / nome_origem
    path.write_text(html, encoding="utf-8")
    return path, nome_arquivo_para_cliente(nome_origem)


def _launch_browser(playwright):
    try:
        return playwright.chromium.launch()
    except Exception:
        return playwright.chromium.launch(channel="chrome")


@pytest.fixture(scope="module")
def browser_instance():
    with sync_playwright() as p:
        browser = _launch_browser(p)
        yield browser
        browser.close()


@pytest.fixture
def page(browser_instance, html_trabalho: tuple[Path, str]) -> Page:
    context = browser_instance.new_context(accept_downloads=True)
    pg = context.new_page()
    pg.goto(html_trabalho[0].as_uri())
    _ir_aba_rede(pg)
    yield pg
    context.close()


def _ir_aba_rede(page: Page) -> None:
    page.evaluate(
        """() => {
        const t = document.getElementById('tab-rede');
        if (!t) throw new Error('aba rede ausente');
        t.checked = true;
    }"""
    )
    page.wait_for_selector(
        "#visao-rede .rede-sandbox:not(.rede-sandbox-no-js)", state="visible"
    )


def _visible_prestadores(page: Page) -> int:
    return page.locator(
        "tr.p-rede:not(.rede-row-out):not(.rede-filter-hide)"
    ).evaluate_all(
        "rows => rows.filter(r => r.style.display !== 'none' && "
        "getComputedStyle(r).display !== 'none').length"
    )


def test_07_filtro_zona_reduz_linhas(page: Page):
    antes = _visible_prestadores(page)
    sel = page.locator("#rede-filtro-zona")
    opts = sel.locator("option")
    assert opts.count() >= 2
    valor = opts.nth(1).get_attribute("value") or ""
    assert valor
    sel.select_option(valor)
    depois = _visible_prestadores(page)
    assert depois < antes
    assert depois > 0


def test_08_filtro_municipio(page: Page):
    page.locator("#rede-filtro-zona").select_option("")
    sel = page.locator("#rede-filtro-mun")
    opts = sel.locator("option")
    assert opts.count() >= 2
    valor = opts.nth(1).get_attribute("value") or ""
    sel.select_option(valor)
    depois = _visible_prestadores(page)
    assert depois > 0
    total = page.locator("tr.p-rede").count()
    assert depois <= total


def test_09_busca_por_nome(page: Page):
    page.locator("#rede-filtro-zona").select_option("")
    page.locator("#rede-filtro-mun").select_option("")
    primeira = page.locator("tr.p-rede[data-nome]").first
    nome = primeira.get_attribute("data-nome") or ""
    assert len(nome) >= 3
    trecho = nome[: min(8, len(nome))]
    page.locator("#rede-filtro-nome").fill(trecho)
    vis = _visible_prestadores(page)
    assert vis >= 1
    assert vis <= page.locator("tr.p-rede").count()


def test_10_desmarcar_some_na_visao_final(
    page: Page, html_trabalho: tuple[Path, str], tmp_path: Path
):
    _, nome_cliente = html_trabalho
    page.locator("#rede-filtro-nome").fill("")
    row = page.locator("tr.p-rede").first
    rid = row.get_attribute("data-rede-id")
    assert rid
    row.locator("input[type=checkbox]").uncheck()
    dest = tmp_path / nome_cliente
    with page.expect_download() as dl_info:
        page.locator("#rede-btn-confirmar").click()
    download = dl_info.value
    assert download.suggested_filename == nome_cliente
    download.save_as(dest)
    conteudo = dest.read_text(encoding="utf-8")
    assert '"mode":"final"' in conteudo.replace(" ", "")
    assert rid in conteudo
    pg2 = page.context.new_page()
    pg2.goto(dest.as_uri())
    _ir_aba_rede(pg2)
    pg2.wait_for_selector(".rede-sandbox-final")
    visivel = pg2.locator(f'tr.p-rede[data-rede-id="{rid}"]').evaluate_all(
        "els => els.filter(el => el.offsetParent !== null).length"
    )
    assert visivel == 0
    pg2.close()


def test_11_marcar_tudo_por_bloco(page: Page):
    page.locator("#rede-filtro-zona").select_option("")
    page.locator("#rede-filtro-mun").select_option("")
    btn = page.locator("button.rede-marcar-bloco").first
    assert btn.get_attribute("data-checked") == "1"
    btn.click()
    assert btn.get_attribute("data-checked") == "0"
    assert "Marcar bloco" in btn.inner_text()
    btn.click()
    assert btn.get_attribute("data-checked") == "1"
    assert "Desmarcar" in btn.inner_text()


def test_12_contagem_reflete_prestadores_restantes(page: Page):
    page.locator("#rede-filtro-zona").select_option("")
    page.locator("#rede-filtro-mun").select_option("")
    page.locator("#rede-filtro-nome").fill("")
    vis = _visible_prestadores(page)
    marcados = page.locator(
        "tr.p-rede:not(.rede-row-out) input[type=checkbox]:checked"
    ).count()
    texto = page.locator("#rede-contador-marcados").inner_text()
    assert str(marcados) in texto
    page.locator("tr.p-rede").first.locator("input[type=checkbox]").uncheck()
    marcados2 = page.locator(
        "tr.p-rede:not(.rede-row-out) input[type=checkbox]:checked"
    ).count()
    assert marcados2 == marcados - 1
    cont = page.locator("tr.cont-rede").first
    assert cont.is_visible()
    assert vis >= 1


def test_13_ciclo_confirmar_reabrir_editar_id(
    page: Page, html_trabalho: tuple[Path, str], tmp_path: Path
):
    _, nome_cliente = html_trabalho
    page.locator("#rede-filtro-nome").fill("")
    for cb in page.locator("tr.p-rede input[type=checkbox]").all()[:3]:
        cb.uncheck()
    dest = tmp_path / "ciclo_cliente.html"
    with page.expect_download() as dl_info:
        page.locator("#rede-btn-confirmar").click()
    download = dl_info.value
    assert download.suggested_filename == nome_cliente
    download.save_as(dest)
    aviso = page.locator("#rede-aviso-download")
    assert aviso.is_visible()
    assert nome_cliente in aviso.inner_text()
    assert "navegador" in aviso.inner_text().lower()

    pg2 = page.context.new_page()
    pg2.goto(dest.as_uri())
    _ir_aba_rede(pg2)
    pg2.wait_for_selector("#rede-btn-editar:not([hidden])")

    alerts: list[str] = []
    fase = {"prompts": 0}

    def on_dialog(d):
        if d.type == "alert":
            alerts.append(d.message)
            d.accept()
            return
        if fase["prompts"] == 0:
            d.accept("id-errado")
            fase["prompts"] = 1
        else:
            d.accept(ESTUDO_ID)

    pg2.on("dialog", on_dialog)
    pg2.locator("#rede-btn-editar").click()
    pg2.wait_for_timeout(400)
    assert any("incorreto" in a.lower() for a in alerts)
    pg2.locator("#rede-btn-editar").click()
    pg2.wait_for_selector(".rede-sandbox-bar:not([hidden])")
    pg2.remove_listener("dialog", on_dialog)
    assert pg2.locator("#rede-btn-confirmar").is_visible()
    pg2.close()
