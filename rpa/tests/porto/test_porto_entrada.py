"""Página pública da Porto: localização, cookies, botão e janela de login (códigos fictícios)."""
from __future__ import annotations

import json

import pytest
import yaml
from playwright.sync_api import sync_playwright

from nucleo.credenciais import Cofre, CofreMemoria
from nucleo.navegador import ARGS_SEM_PAUSA, ErroLogin, _sem_guardar_formularios
from nucleo.texto import so_digitos
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


_HTML_PORTAL_REAL = """
<header>
  <ul class="col-line-login-modal">
    <li>
      <button data-gtm-type="click" data-gtm-clicktype="button" data-gtm-name="login"
              type="button" class="ps-btn ps-btn-secondary " name="entrar"
              onclick="openLogin();" style="display:none">
        <div class="text-btn">ACESSAR O CORRETOR ONLINE</div>
      </button>
    </li>
  </ul>
</header>
<section id="modal-login" class="ps-modal-content" style="display:none">
  <h2>Acesse o Corretor Online</h2>
  <input id="logonPrincipal">
  <input type="password">
</section>
<script>
function openLogin() {
  document.getElementById('modal-login').style.display = 'block';
}
</script>
"""


def test_portal_real_abre_mesmo_com_botao_display_none():
    """O header da Porto aninha o texto num div e o botão pode não ter caixa visível."""
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(_HTML_PORTAL_REAL)
        assert not _visivel(sel.login_campo_cpf(page))
        assert _clicar_acessar_corretor(page)
        page.wait_for_function("() => document.getElementById('modal-login').style.display === 'block'")
        assert page.locator("#logonPrincipal").is_visible()
        page.context.browser.close()


def test_portal_real_openLogin_sem_innerText():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(
            "<script>window.__n=0; function openLogin(){ window.__n++; "
            "document.body.insertAdjacentHTML('beforeend',"
            "'<input id=logonPrincipal><input type=password>'); }</script>"
            "<p>sem botão visível</p>"
        )
        assert _clicar_acessar_corretor(page)
        assert page.evaluate("() => window.__n") == 1
        assert page.locator("#logonPrincipal").count() == 1
        page.context.browser.close()


def test_abre_com_overlay_em_cima_do_botao():
    """Cartaz fullscreen zera innerText/caixa; o contrato é openLogin(), não o layout."""
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(
            "<button data-gtm-name='login' onclick='openLogin()' style='position:absolute;left:0;top:0'>"
            "<div class='text-btn'>ACESSAR O CORRETOR ONLINE</div></button>"
            "<div id='cartaz' style='position:fixed;inset:0;background:#000;z-index:99999'></div>"
            "<script>function openLogin(){ document.getElementById('cartaz').remove();"
            "document.body.insertAdjacentHTML('beforeend',"
            "'<input id=logonPrincipal><input type=password>'); }</script>"
        )
        assert _clicar_acessar_corretor(page)
        assert page.locator("#logonPrincipal").count() == 1
        page.context.browser.close()


def test_abre_botao_dentro_de_shadow_dom():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content("""
        <ps-header></ps-header>
        <script>
        class PsHeader extends HTMLElement {
          constructor() {
            super();
            const r = this.attachShadow({mode: 'open'});
            const b = document.createElement('button');
            b.setAttribute('data-gtm-name', 'login');
            b.innerHTML = '<div class="text-btn">ACESSAR O CORRETOR ONLINE</div>';
            b.addEventListener('click', () => {
              document.body.insertAdjacentHTML('beforeend',
                '<input id=logonPrincipal><input type=password>');
            });
            r.appendChild(b);
          }
        }
        customElements.define('ps-header', PsHeader);
        </script>
        """)
        assert _clicar_acessar_corretor(page)
        page.wait_for_selector("#logonPrincipal")
        page.context.browser.close()


def test_espera_openLogin_injetado_depois():
    import time
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content("""
        <p>hidratando</p>
        <script>
        setTimeout(() => {
          window.openLogin = () => {
            document.body.insertAdjacentHTML('beforeend',
              '<input id=logonPrincipal><input type=password>');
          };
        }, 1200);
        </script>
        """)
        ok = False
        for _ in range(20):
            if _clicar_acessar_corretor(page):
                ok = True
                break
            time.sleep(0.2)
        assert ok
        assert page.locator("#logonPrincipal").count() == 1
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
        assert page.get_by_text("O Recaptcha serve").count()
        assert not _visivel(sel.captcha_desafio(page))
        page.context.browser.close()


def test_aviso_recaptcha_do_modal_nao_e_desafio():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(
            "<p>O Recaptcha serve para a sua maior segurança ao acessar o Corretor Online.</p>"
            "<label for=cpf>CPF</label><input id=cpf>"
            "<label for=senha>Senha</label><input id=senha type=password>"
            "<button>ENTRAR</button>"
        )
        assert not _visivel(sel.captcha_desafio(page))
        assert not sel.login_recaptcha_protege(page)
        page.set_content("<p id=captcha>Não sou um robô — desafio reCAPTCHA</p>")
        assert _visivel(sel.captcha_desafio(page))
        page.context.browser.close()


def test_recaptcha_protege_pelo_iframe_nao_pelo_aviso():
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content("<p>O Recaptcha serve para a sua maior segurança ao acessar o Corretor Online.</p>")
        assert not sel.login_recaptcha_protege(page)
        page.set_content(
            "<iframe title='reCAPTCHA' src='https://www.google.com/recaptcha/api2/anchor?size=invisible'></iframe>"
            "<small>protegido pelo reCAPTCHA</small>"
        )
        assert sel.login_recaptcha_protege(page)
        page.context.browser.close()


def test_bloqueio_de_automacao_nao_e_senha_errada():
    msg = "Por motivos de segurança, não conseguimos validar seu acesso."
    assert sel.TEXTO_BLOQUEIO_AUTOMACAO.search(msg)
    assert not sel.TEXTO_RECUSA_LOGIN.search(msg)
    assert not sel.TEXTO_PROTEGIDO_RECAPTCHA.search(
        "O Recaptcha serve para a sua maior segurança ao acessar o Corretor Online.")
    assert sel.TEXTO_PROTEGIDO_RECAPTCHA.search("protegido pelo reCAPTCHA")


def test_cpf_do_modal_nao_e_o_de_recuperar_senha():
    from operadoras.porto.login import _cpf_para_campo, _preencher

    html = """
    <label class="ps-frm-lbl">CPF</label>
    <input id="logonSenha" type="text" name="logon" title="CPF" data-gtm-name="cpf-recuperar-senha">
    <label class="ps-frm-lbl">CPF</label>
    <input id="logonPrincipal" type="text" name="logon" title="logon" data-gtm-name="cpf"
           autocomplete="username" class="ps-frm-cpf" maxlength="14">
    <input name="password" type="password">
    """
    with sync_playwright() as pw:
        page = pw.chromium.launch(headless=True).new_page()
        page.set_content(html)
        bruto = "52998224725"
        _preencher(page, sel.login_campo_cpf(page), _cpf_para_campo(bruto))
        assert page.locator("#logonPrincipal").input_value() == "529.982.247-25"
        assert page.locator("#logonSenha").input_value() == ""
        page.context.browser.close()


def test_com_recaptcha_preenche_e_nao_clica_entrar(tmp_path, sim):
    sim.proteger_recaptcha = True
    avisos = []
    secao = {"urls": {"login": sim.url, "cotador": sim.url_home},
             "tempos": {"timeout_login_ms": 4000, "timeout_tela_ms": 8000, "timeout_codigo_ms": 2500}}
    cfg = {"geral": {"pasta_saida": str(tmp_path / "saida"), "modo_visual": False, "lentidao_ms": 0,
                     "mapear": False, "pausa_entre_pedidos_s": 0},
           "teste": {"cofre": "memoria"}, "operadoras": {"porto": secao}}
    with sync_playwright() as pw:
        import operadoras
        from nucleo.estado import Estado
        from nucleo.navegador import Mapeador, abrir
        from nucleo.registro import carregar_config, configurar_log

        (tmp_path / "config.yaml").write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
        op = operadoras.obter("porto")
        cfg_op = op.config(carregar_config(tmp_path / "config.yaml"))
        pasta = tmp_path / "saida" / "porto"
        log = configurar_log(pasta / "logs")
        contexto, page = abrir(pw, cfg_op)
        s = op.nova_sessao(cfg_op, log, contexto, page, Estado(pasta / "estado.json"),
                           op.resultados(pasta / "resultados.xlsx", log),
                           Mapeador(pasta, False, log), True,
                           avisar=lambda tipo, **d: avisos.append((tipo, d)))
        with pytest.raises(ErroLogin) as e:
            entrar(s)
        assert e.value.motivo == "captcha"
        assert sim.tentativas_login == 0
        assert so_digitos(s.page.locator("#cpf").input_value()) == so_digitos(Simulador.CPF)
        assert s.page.locator("#senha").input_value() == Simulador.SENHA
        contexto.close()
    assert any(t == "login_aguardando" for t, _ in avisos)


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
