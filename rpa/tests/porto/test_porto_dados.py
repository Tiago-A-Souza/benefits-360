"""Dados iniciais do cotador Gatsby da Porto (markup real 27/11/2026, CNPJ fictício)."""
from __future__ import annotations

from playwright.sync_api import sync_playwright

from nucleo.texto import formatar_cnpj, so_digitos
from operadoras.porto import seletores as sel
from operadoras.porto.etapas import _digitar_cnpj
from operadoras.porto.telas import empresa_preenchida, fechar_overlays, saiu_de_dados_iniciais

CNPJ_FICTICIO = "11.222.333/0001-81"

_HTML_PORTAL = """
<div id="banner">
  <p>Está com dúvidas sobre como utilizar o novo sistema de cotação?</p>
  <a href="#">Acesse o conteúdo explicativo</a>
  <button type="button" aria-label="close" onclick="this.parentElement.remove()">x</button>
</div>
<p>1 de 4 - Dados iniciais</p>
<section>
  <h2>Dados do cliente</h2>
  <input name=".document" type="text" maxlength="255">
  <span>CNPJ</span>
  <input name=".companyName" type="text" disabled value="">
  <span>Razão Social</span>
  <input name=".codCNAE" type="text" disabled>
  <span>CNAE</span>
  <input name=".address.postalCode" type="text">
  <span>CEP</span>
  <button type="button">Voltar</button>
  <button type="button">Próximo</button>
</section>
<script>
document.querySelector('input[name=".document"]').addEventListener('blur', function () {
  const d = (this.value || '').replace(/\\D/g, '');
  if (d.length !== 14) return;
  const n = document.querySelector('input[name=".companyName"]');
  n.disabled = false;
  n.value = 'PADARIA MODELO DE TREINO LTDA';
  n.disabled = true;
});
</script>
"""

_HTML_SIMULADOR = """
<label for="cnpj">CNPJ</label><input id="cnpj" name="cnpj">
<p>Razão social: <span id="rs"></span></p>
<button type="button">Próximo</button>
"""


def test_campo_cnpj_do_portal_e_name_document_sem_label():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL)
        loc = sel.campo_cnpj(page)
        assert loc.first.is_visible()
        loc.first.fill(formatar_cnpj(CNPJ_FICTICIO))
        assert so_digitos(page.locator("input[name='.document']").input_value()) == so_digitos(CNPJ_FICTICIO)
        page.context.browser.close()


def test_consulta_receita_dispara_no_tab_nao_no_fill():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL)
        cnpj = sel.campo_cnpj(page).first
        cnpj.fill(formatar_cnpj(CNPJ_FICTICIO), force=True)
        assert not empresa_preenchida(page)
        _digitar_cnpj(cnpj, CNPJ_FICTICIO)
        assert empresa_preenchida(page)
        page.context.browser.close()


def test_campo_cnpj_do_simulador_continua_pelo_label():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_SIMULADOR)
        loc = sel.campo_cnpj(page)
        assert loc.first.get_attribute("id") == "cnpj"
        loc.first.fill(CNPJ_FICTICIO)
        page.context.browser.close()


def test_rotulo_razao_social_vazio_nao_conta_como_empresa_preenchida():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL)
        assert not empresa_preenchida(page)
        page.locator("input[name='.companyName']").evaluate(
            "e => { e.disabled = false; e.value = 'PADARIA MODELO DE TREINO LTDA'; e.disabled = true; }"
        )
        assert empresa_preenchida(page)
        page.context.browser.close()


def test_simulador_conta_razao_no_span_rs():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_SIMULADOR)
        assert not empresa_preenchida(page)
        page.locator("#rs").evaluate("e => { e.textContent = 'PADARIA MODELO DE TREINO LTDA'; }")
        assert empresa_preenchida(page)
        page.context.browser.close()


def test_saiu_de_dados_quando_aparece_passo_2():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL)
        assert not saiu_de_dados_iniciais(page)
        page.set_content("<p>2 de 4 - Produto e vidas</p><label>Quantidade total</label><input id=total-vidas>")
        assert saiu_de_dados_iniciais(page)
        page.context.browser.close()


def test_fecha_banner_duvidas_pelo_botao_close():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL)
        assert page.get_by_text(sel.TEXTO_BANNER_DUVIDAS).count()
        fechar_overlays(page)
        assert page.locator("#banner").count() == 0
        page.context.browser.close()
