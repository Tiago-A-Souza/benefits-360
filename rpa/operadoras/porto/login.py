"""Login automático da Porto (Corretor Online): CPF, senha e SUSEP do cofre NewportCotacoes/porto.

Regras:
- página pública → recusa localização/cookies → «Acessar o Corretor Online» → janela;
- na janela, CPF e senha (se o portal mostrar) e o dropdown da SUSEP só por clique;
- só entra quando o portal pede; a sessão fica no perfil do navegador;
- nada do que é digitado vai para log, mapa, evento ou erro;
- recusado: para na primeira vez;
- reCAPTCHA: preenche CPF e senha e espera o corretor clicar em ENTRAR. Nunca resolve nem burla.
"""
from __future__ import annotations

import time
from datetime import datetime

from nucleo.configuracao import aprendido, aprender
from nucleo.credenciais import cofre as cofre_da_config, mensagem_login

from nucleo.navegador import ErroLogin, Parado, visiveis
from nucleo.texto import so_digitos

from . import seletores as sel
from .telas import (
    _visivel, esperar_ate, fechar_banners_entrada, logado, login_na_tela,
    tela_susep,
)

OPERADORA = ("porto", "Porto Seguro")


def _erro(motivo: str) -> ErroLogin:
    from . import Porto
    return ErroLogin(mensagem_login(motivo, OPERADORA[1], Porto.mensagens_login), motivo)


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


def _sessao_viva(s) -> None:
    pasta = s.cfg["saida"]["pasta"]
    dados = aprendido(pasta)
    if dados.get("sessao_login_em"):
        s.log.info("Sessão do portal aberta: não precisa entrar de novo.")
    aprender(pasta, "sessao_viva_em", _agora().isoformat())


def _sessao_nova(s) -> None:
    pasta = s.cfg["saida"]["pasta"]
    agora = _agora()
    aprender(pasta, "sessao_login_em", agora.isoformat())
    aprender(pasta, "sessao_viva_em", agora.isoformat())
    s.log.info("Login feito.")
    s.aviso("login_ok", sessao_ativa=False)


def _marcar(s, chave: str, mensagem: str, captura: str | None = None, login_vazio: bool = False) -> None:
    """Evento em português + captura sem valor de login (o mapa cobre CPF/senha/SUSEP já lidos)."""
    s._etapa_login = chave
    s.log.info(mensagem)
    s.aviso("etapa", etapa=chave, pedido="", plano="")
    if not captura:
        return
    try:
        s.mapa.registrar(s.page, captura, forcar=True, login_vazio=login_vazio)
    except Exception:  # noqa: BLE001
        pass


def _login_a_vista(page) -> bool:
    return (login_na_tela(page) or tela_susep(page)
            or _visivel(sel.login_campo_cpf(page)) or _visivel(sel.login_campo_senha(page)))


# Portal real: o header chama window.openLogin() — o contrato estável. innerText +
# getBoundingClientRect quebram com janela escondida, display:none, overlay ou shadow DOM.
_JS_CLICAR_ACESSAR = r"""() => {
  const rx = /acess[ae]r?\s+o\s+corretor\s+online/i;
  const css = "button[data-gtm-name='login'], [onclick*='openLogin'], button#acessar, a#acessar";
  const recaptcha = /recaptcha|google\.com\/recaptcha|hcaptcha/i;
  const texto = (e) => {
    if (!e) return '';
    let t = (e.textContent || e.innerText || '');
    try {
      t += ' ' + (e.getAttribute('aria-label') || e.getAttribute('title') || e.getAttribute('name') || '');
    } catch (err) {}
    return t.replace(/\s+/g, ' ').trim();
  };
  const clicar = (e) => {
    if (!e) return false;
    const alvo = (e.closest && e.closest('button, a, [role=button], [role=link]')) || e;
    try { alvo.click(); return true; } catch (err) { return false; }
  };
  const tentar = (doc, win) => {
    if (!doc) return false;
    try {
      if (win && typeof win.openLogin === 'function') { win.openLogin(); return true; }
    } catch (err) {}
    try {
      const porCss = doc.querySelector(css);
      if (porCss && clicar(porCss)) return true;
    } catch (err) {}
    const acc = [];
    const walk = (raiz) => {
      if (!raiz) return;
      let nos;
      try { nos = raiz.querySelectorAll('button, a, [role=button], [role=link], .ps-btn, .text-btn'); }
      catch (err) { return; }
      for (const e of nos) acc.push(e);
      let todos;
      try { todos = raiz.querySelectorAll('*'); } catch (err) { return; }
      for (const e of todos) { if (e.shadowRoot) walk(e.shadowRoot); }
    };
    walk(doc);
    const b = acc.find(e => { const t = texto(e); return rx.test(t) && t.length <= 120; });
    if (b && clicar(b)) return true;
    return false;
  };
  if (tentar(document, window)) return true;
  for (const f of document.querySelectorAll('iframe')) {
    const src = ((f.src || '') + ' ' + (f.title || '')).toLowerCase();
    if (recaptcha.test(src)) continue;
    try {
      if (tentar(f.contentDocument, f.contentWindow)) return true;
    } catch (err) {}
  }
  return false;
}"""

_JS_DIAGNOSTICO = r"""() => ({
  url: location.href,
  openLogin: typeof openLogin,
  logon: !!document.querySelector('#logonPrincipal'),
  botoes: [...document.querySelectorAll('button, a')].slice(0, 8).map(
    e => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 50)
  ),
})"""


def _tem_open_login(page) -> bool:
    try:
        return bool(page.evaluate("() => typeof openLogin === 'function'"))
    except Exception:  # noqa: BLE001
        return False


def _entrada_pronta(page) -> bool:
    try:
        if _login_a_vista(page) or logado(page) or _tem_open_login(page):
            return True
        return sel.botao_acessar_corretor(page).count() > 0
    except Exception:  # noqa: BLE001
        return False


def _clicar_acessar_corretor(page) -> bool:
    """Abre o modal via openLogin() / DOM. Sem tamanho na tela, sem iframe de reCAPTCHA."""
    try:
        if page.evaluate(_JS_CLICAR_ACESSAR):
            return True
    except Exception:  # noqa: BLE001
        pass
    for loc in (
        page.locator("button[data-gtm-name='login']"),
        page.locator("[onclick*='openLogin']"),
        page.locator("button#acessar, a#acessar"),
        page.get_by_role("button", name=sel._RX_BOTAO_CORRETOR),
        page.get_by_role("link", name=sel._RX_BOTAO_CORRETOR),
    ):
        try:
            if loc.count() == 0:
                continue
            loc.first.click(timeout=2000, force=True)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def _abrir_janela_corretor(s) -> None:
    """Portal real: modal na mesma página. Simulador: pode ir para /login na mesma aba.

    Não trata o primeiro clique como sucesso: insiste até CPF/senha/SUSEP aparecerem
    (o portal hidrata tarde; overlay e shadow DOM fazem o clique “passar em branco”).
    """
    page = s.page
    timeout_ms = int(s.t("timeout_tela_ms"))
    fim = time.monotonic() + timeout_ms / 1000
    tentou = False
    while time.monotonic() < fim:
        fechar_banners_entrada(s.page)
        if _login_a_vista(s.page) or logado(s.page):
            break
        if _clicar_acessar_corretor(s.page):
            tentou = True
            if esperar_ate(lambda: _login_a_vista(s.page) or logado(s.page), 2.0):
                break
            continue
        time.sleep(0.4)
    if len(page.context.pages) > 1:
        s.page = page.context.pages[-1]
    if esperar_ate(lambda: _login_a_vista(s.page) or logado(s.page), 8):
        _marcar(s, "janela do corretor online", "Janela do Corretor Online aberta.")
        return
    try:
        diag = s.page.evaluate(_JS_DIAGNOSTICO)
        s.log.warning("Porto 1ª tela sem login após o clique: %s", diag)
    except Exception:  # noqa: BLE001
        pass
    raise _erro("sem_janela_login" if tentou else "sem_botao_entrada")


def _abrir_login(s) -> None:
    """Página pública → recusa localização/cookies → «Acessar o Corretor Online» → modal de login."""
    _marcar(s, "abrindo login", "Abrindo a página pública do Corretor Online.")
    s.page.goto(s.cfg["urls"]["login"], wait_until="domcontentloaded")
    fechar_banners_entrada(s.page)
    esperar_ate(lambda: _entrada_pronta(s.page), min(20.0, int(s.t("timeout_tela_ms")) / 1000))
    fechar_banners_entrada(s.page)
    _marcar(s, "abrindo login",
            f"Primeira página da Porto aberta ({sel.caminho(s.page) or '/'}).")
    if logado(s.page) and not login_na_tela(s.page) and not tela_susep(s.page):
        return
    ja_no_login = _visivel(sel.login_campo_cpf(s.page)) and _visivel(sel.login_campo_senha(s.page))
    if not ja_no_login:
        _marcar(s, "abrindo login", "Clicando em Acessar o Corretor Online.")
        _abrir_janela_corretor(s)
        fechar_banners_entrada(s.page)
    # Mapa depois do clique: na 1ª tela um iframe sem URL fazia o Playwright pendurar
    # em evaluate (sem timeout) e o robô nunca chegava a openLogin().
    _marcar(s, "abrindo login",
            f"Primeira página da Porto aberta ({sel.caminho(s.page) or '/'}).",
            captura="entrada_porto", login_vazio=True)


def _cpf_para_campo(valor: str) -> str:
    """O #logonPrincipal tem máscara e maxlength 14: 000.000.000-00."""
    d = so_digitos(valor)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    return valor


def _preencher(page, campo, valor: str) -> None:
    """O modal da Porto deixa inputs type=password escondidos no DOM: preenche só o visível."""
    alvo = visiveis(campo)[0] if visiveis(campo) else campo.first
    alvo.click()
    alvo.fill(valor)


def _codigo_susep(s, login: dict | None) -> str:
    """Código do cofre (Conexões); se faltar, o padrão da engrenagem. Aceita 'AAAAAA (P)'."""
    bruto = ((login or {}).get("susep") or (s.cfg.get("padroes") or {}).get("susep") or "")
    return sel.normalizar_susep(bruto)


def _falha_susep(rotulos: list[str] | None = None) -> ErroLogin:
    if rotulos:
        return ErroLogin(sel.mensagem_susep_ausente(rotulos), "sem_susep")
    return _erro("sem_susep")


def _escolher_susep(s, codigo: str) -> None:
    page = s.page
    if not codigo:
        raise _falha_susep()
    _marcar(s, "SUSEP selecionado", "Escolhendo o código SUSEP no menu do portal (só clique, sem digitar).")
    if not esperar_ate(lambda: tela_susep(page), s.t("timeout_tela_ms") / 1000):
        if logado(page):
            return
        raise _falha_susep(sel.listar_rotulos_susep(page))
    try:
        sel.escolher_susep(page, codigo)
    except sel.SusepNaoEncontrada as e:
        try:
            s.mapa.registrar(page, "ERRO_susep", forcar=True)
        except Exception:  # noqa: BLE001
            pass
        raise _falha_susep(e.rotulos) from None
    except Exception:  # noqa: BLE001
        if logado(page) or not tela_susep(page):
            return
        try:
            s.mapa.registrar(page, "ERRO_susep", forcar=True)
        except Exception:  # noqa: BLE001
            pass
        raise _falha_susep(sel.listar_rotulos_susep(page)) from None
    _marcar(s, "SUSEP selecionado", "SUSEP selecionada na lista do portal.")
    botao = sel.susep_botao_seguir(page)
    if _visivel(botao):
        botao.first.click()
        time.sleep(0.4)
    esperar_ate(lambda: logado(page), 15)


def entrar(s, pode_parar: bool = True, insistir: bool = True) -> None:
    s._etapa_login = "abrindo login"
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if logado(page) and not login_na_tela(page) and not tela_susep(page):
        _sessao_viva(s)
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not login_na_tela(page) and not tela_susep(page):
        _abrir_login(s)
        page = s.page
    if logado(page) and not login_na_tela(page) and not tela_susep(page):
        _sessao_viva(s)
        s.aviso("login_ok", sessao_ativa=True)
        return
    cofre = cofre_da_config(s.cfg, OPERADORA[0])
    if cofre.situacao()["recusadas"]:
        raise _erro("recusadas")
    login = cofre.ler()
    if login is None:
        raise _erro("sem_credenciais")
    try:
        _tentar_login(s, cofre, login, parar, _codigo_susep(s, login))
    finally:
        login = None


def _pedir_clique_entrar(s, fim: float) -> float:
    """reCAPTCHA valida o clique em ENTRAR. O robô não clica: espera o corretor na janela do portal."""
    try:
        s.page.bring_to_front()
    except Exception:  # noqa: BLE001
        pass
    s.aviso("login_aguardando")
    _marcar(s, "aguardando reCAPTCHA",
            "O portal protege o login com reCAPTCHA. CPF e senha já estão preenchidos: clique em ENTRAR "
            "na janela do portal; o robô continua depois (SUSEP).")
    extra = int(s.cfg["execucao"].get("timeout_codigo_ms", 300000)) / 1000
    return max(fim, time.monotonic() + extra)


def _tentar_login(s, cofre, login: dict, parar, codigo_susep: str) -> None:
    page, log = s.page, s.log
    if _visivel(sel.captcha_desafio(page)):
        _marcar(s, "aguardando reCAPTCHA",
                "O portal pediu um reCAPTCHA. O robô parou: resolva no navegador e peça de novo.")
        raise _erro("captcha")
    s.aviso("login_entrando")
    _marcar(s, "abrindo login", "Entrando no portal da Porto com o login guardado na engrenagem do robô.")
    page = s.page
    if not esperar_ate(lambda: _login_a_vista(s.page), s.t("timeout_tela_ms") / 1000):
        raise _erro("sem_resposta")
    page = s.page
    s.mapa.registrar(page, "login", login_vazio=True)
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    digitou = {"cpf": False, "senha": False, "susep": False}
    esperando_entrar = False
    recusa_antes = _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN))
    try:
        while time.monotonic() < fim:
            if parar():
                raise Parado("login")
            page = s.page
            if _visivel(sel.captcha_desafio(page)) and not esperando_entrar:
                _marcar(s, "aguardando reCAPTCHA",
                        "O portal pediu um reCAPTCHA. O robô parou: resolva no navegador e peça de novo.")
                raise _erro("captcha")
            if _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)):
                raise _erro("troca_senha")
            if logado(page) and not login_na_tela(page) and not tela_susep(page):
                _marcar(s, "logado", "Login concluído.")
                _sessao_nova(s)
                return
            if tela_susep(page) and not digitou["susep"]:
                _escolher_susep(s, codigo_susep)
                digitou["susep"] = True
                continue
            if _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)) and not recusa_antes and digitou["senha"]:
                time.sleep(0.8)
                if not logado(page) and _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)):
                    cofre.marcar_recusadas()
                    raise _erro("recusadas")
            if _visivel(page.get_by_text(sel.TEXTO_BLOQUEIO_AUTOMACAO)):
                _marcar(s, "aguardando reCAPTCHA",
                        "O portal recusou o acesso (reCAPTCHA). Neste aviso o ENTRAR não vale: feche o modal e "
                        "peça o login de novo.")
                raise _erro("captcha")
            if _visivel(sel.login_campo_cpf(page)) and not digitou["cpf"]:
                s.mapa.login_digitado = True
                _preencher(page, sel.login_campo_cpf(page), _cpf_para_campo(login["cpf"]))
                digitou["cpf"] = True
                continue
            if _visivel(sel.login_campo_senha(page)) and not digitou["senha"]:
                s.mapa.login_digitado = True
                _preencher(page, sel.login_campo_senha(page), login["senha"])
                digitou["senha"] = True
                if sel.login_recaptcha_protege(page):
                    fim = _pedir_clique_entrar(s, fim)
                    esperando_entrar = True
                    continue
                sel.login_botao_entrar(page).first.click()
                _marcar(s, "CPF e senha enviados", "CPF e senha enviados.")
                time.sleep(0.5)
                continue
            time.sleep(0.3)
    except (ErroLogin, Parado):
        raise
    except Exception as e:  # noqa: BLE001
        raise ErroLogin(_erro("falha").args[0], "falha") from None
    raise _erro("captcha" if esperando_entrar else "sem_resposta")
