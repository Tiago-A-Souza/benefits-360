"""Login automático no Portal de Negócios da Bradesco, com o login que o corretor guardou na engrenagem do robô
(cofre do Windows, serviço NewportCotacoes/bradesco). Duas etapas: CPF/CNPJ -> Continuar -> senha (nidp).

Mesmas regras da SulAmérica (nucleo/credenciais.py e CLAUDE.md, regra 2):
- só entra quando o portal pede;
- nada do que é digitado vai para log, mapa, evento ou erro: falha com o login na tela vira ErroLogin com frase
  fixa (`from None`); o mapa da tela de login só é tirado ANTES de digitar (`login_vazio=True`);
- recusado (CPF/CNPJ não cadastrado ou senha errada): para na PRIMEIRA vez e marca o login como recusado;
- código de verificação: a tela do Newport pede ao corretor; captcha ou troca de senha: para e avisa.
No vídeo a etapa da senha passou sozinha (sessão ou senha salva no Chrome do corretor): o robô aceita os dois.
"""
from __future__ import annotations

import time

from nucleo.credenciais import cofre as cofre_da_config, lembrar_segredos, mensagem_login, ocultar
from nucleo.navegador import ErroLogin, Parado, conferir_parar, esperar_visivel, visiveis
from nucleo.texto import so_digitos

from . import seletores as sel
from .telas import login_na_tela

OPERADORA = ("bradesco", "Bradesco")


def _erro(motivo: str) -> ErroLogin:
    from . import Bradesco
    return ErroLogin(mensagem_login(motivo, OPERADORA[1], Bradesco.mensagens_login), motivo)


def _visivel(loc) -> bool:
    try:
        return bool(visiveis(loc))
    except Exception:  # noqa: BLE001
        return False


def logado(page) -> bool:
    """A página é do portal logado (área logada, painel, cotador ou página antiga de emissão)."""
    try:
        if page.is_closed():
            return False
        caminho = sel.caminho(page)
        if login_na_tela(page) or erro_403(page):
            return False
        return sel.ROTA_AREA_LOGADA in caminho or "/eeem-" in caminho or _visivel(page.get_by_text(sel.TEXTO_LOGADO))
    except Exception:  # noqa: BLE001
        return False


def erro_403(page) -> bool:
    """"Error 403: AuthorizationFailed": a sessão do robô no portal ficou inválida (07/11, depois de várias entradas
    seguidas e uma saída que não completou)."""
    try:
        return bool(visiveis(page.get_by_text(sel.TEXTO_ERRO_403)))
    except Exception:  # noqa: BLE001
        return False


def entrar(s, pode_parar: bool = True) -> None:
    """Garante a sessão no portal. Se o portal responder "AuthorizationFailed" (sessão do robô inválida), apaga os
    cookies do navegador do robô e entra de novo, uma vez."""
    for tentativa in range(2):
        _entrar(s, pode_parar)
        if not erro_403(s.page):
            return
        if tentativa:
            s.log.error("O portal continuou respondendo 'AuthorizationFailed' depois de entrar de novo.")
            raise _erro("sem_resposta")
        s.log.warning("O portal respondeu 'AuthorizationFailed' à sessão do robô; apagando os cookies do navegador do "
                      "robô e entrando de novo.")
        s.contexto.clear_cookies()
        s.page.goto(s.cfg["urls"]["login"])
        s.page.wait_for_load_state("domcontentloaded")


def _entrar(s, pode_parar: bool = True) -> None:
    """Garante a sessão no portal. Se a tela já é do portal logado, não digita nada."""
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if logado(page):
        log.info("Sessão do portal aberta: não precisa entrar de novo.")
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not login_na_tela(page):
        page.goto(s.cfg["urls"]["login"])
        page.wait_for_load_state("domcontentloaded")
        _esperar_ate(lambda: logado(s.page) or _visivel(sel.login_campo_documento(s.page)), 20)
        if _esperar_ate(lambda: logado(s.page) or login_na_tela(s.page), 15) and logado(s.page):
            log.info("Sessão do portal ainda ativa.")
            s.aviso("login_ok", sessao_ativa=True)
            return
    cofre = cofre_da_config(s.cfg, OPERADORA[0])
    if cofre.situacao()["recusadas"]:
        raise _erro("recusadas")
    login = cofre.ler()
    if login is None:
        raise _erro("sem_credenciais")
    try:
        _tentar(s, cofre, login, parar)
    finally:
        login = None


def _esperar_ate(condicao, segundos: float) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            if condicao():
                return True
        except Exception:  # noqa: BLE001
            pass
        conferir_parar("login")
        time.sleep(0.25)
    return False


def _tentar(s, cofre, login: dict, parar) -> None:
    page, log = s.page, s.log
    s.aviso("login_entrando")
    log.info("Entrando no portal da Bradesco com o login guardado na engrenagem do robô.")
    for botao in visiveis(sel.botao_rejeitar_cookies(page))[:1]:
        try:
            botao.click(timeout=3000)          # o banner de cookies cobre a tela: só os necessários
        except Exception:  # noqa: BLE001
            pass
    if _visivel(sel.captcha(page)):
        raise _erro("captcha")
    passo = "campo CPF/CNPJ"
    if _visivel(sel.login_campo_documento(page)):
        s.mapa.registrar(page, "login", login_vazio=True)       # só com o campo vazio (calibrar o login)
        try:
            campo = esperar_visivel(sel.login_campo_documento(page), s.t("timeout_tela_ms"), "campo CPF/CNPJ", "login")
            s.mapa.login_digitado = True
            page.evaluate("() => document.querySelectorAll('form, input').forEach(e => e.setAttribute('autocomplete', 'off'))")
            campo.click()
            campo.fill("")
            campo.press_sequentially(so_digitos(login["documento"]), delay=40)   # campo com máscara
            passo = "Continuar"
            sel.login_botao_continuar(page).first.click()
        except Exception as e:  # noqa: BLE001
            log.error(f"Login: não consegui fazer o passo '{passo}' na tela de login ({type(e).__name__}).")
            raise _erro("falha") from None
    _esperar_resultado(s, cofre, login, parar)


def _esperar_resultado(s, cofre, login: dict, parar) -> None:
    page, log = s.page, s.log
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    senha_digitada = codigos = 0
    while time.monotonic() < fim:
        if parar():
            raise Parado("login")
        page = _pagina_viva(s)
        if erro_403(page):
            return                      # quem chamou apaga os cookies e entra de novo
        if logado(page):
            log.info("Login feito.")
            s.aviso("login_ok", sessao_ativa=False)
            return
        if _visivel(sel.captcha(page)):
            raise _erro("captcha")
        if _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)):
            raise _erro("troca_senha")
        if _visivel(sel.campo_codigo(page)):
            if codigos >= 3:
                raise _erro("codigo")
            codigos += 1
            _digitar_codigo(s)
            fim = time.monotonic() + limite
            continue
        senha = visiveis(sel.login_campo_senha(page)) if not _visivel(sel.login_campo_documento(page)) else []
        recusa = _recusa_visivel(page)
        if recusa and (senha_digitada or _visivel(sel.login_campo_documento(page))):
            time.sleep(0.6)
            if not logado(s.page) and _recusa_visivel(s.page):
                _recusado(s, cofre)
        if senha and not senha_digitada:
            # Depois do Continuar a tela ainda pode mudar (outra etapa ou outra página): espera assentar.
            time.sleep(1.5)
            page = s.page
            if logado(page) or _visivel(sel.campo_codigo(page)):
                continue
            senha = visiveis(sel.login_campo_senha(page))
            if not senha:
                continue
            _digitar_senha(s, login, senha[0])
            senha_digitada = 1
            continue
        time.sleep(0.3)
    _diagnostico(s)
    raise _erro("sem_resposta")


def _diagnostico(s) -> None:
    """Para calibrar o login sem mapa (a tela de login nunca vira mapa depois de digitar): o log diz onde o robô
    está e o que a tela oferece (caminho, título, nomes de botões, avisos), nunca o que foi digitado."""
    try:
        page = s.page
        botoes = [" ".join((b.inner_text() or b.get_attribute("value") or "").split())[:40]
                  for b in visiveis(page.locator("button, input[type=submit], input[type=button], a[role=button]"))][:12]
        campos = [f"{(c.get_attribute('type') or 'text')}:{c.get_attribute('id') or c.get_attribute('name') or '-'}"
                  f"({'vazio' if not c.input_value() else 'preenchido'})"
                  for c in visiveis(page.locator("input:not([type=hidden])"))][:10]
        avisos = [ocultar(" ".join((x.inner_text() or "").split()))[:150]
                  for x in visiveis(page.locator("[role=alert], .alert, .error, .erro, .message, .msg, "
                                                 "[class*=error i], [class*=invalid i], [class*=feedback i]"))][:5]
        entrar = visiveis(sel.login_botao_entrar(page))
        botoes.append(f"Entrar habilitado: {entrar[0].is_enabled() if entrar else '-'}")
        s.log.warning(f"Login sem resposta. Tela: {sel.caminho(page) or '-'} | título: {page.title()[:80]} | "
                      f"abas: {len(s.contexto.pages)} | botões: {botoes} | campos: {campos} | avisos: {avisos}")
    except Exception as e:  # noqa: BLE001
        s.log.warning(f"Login sem resposta (não consegui descrever a tela: {type(e).__name__}).")


def _pagina_viva(s):
    """A aba do robô. Se a do login fechou (07/11: a aba fechou depois da senha), segue na aba que ficou aberta."""
    try:
        if not s.page.is_closed():
            return s.page
        vivas = [p for p in s.contexto.pages if not p.is_closed()]
    except Exception:  # noqa: BLE001
        vivas = []
    if not vivas:
        s.log.error("Login: a janela do portal fechou depois da senha (fechada à mão ou pelo portal).")
        raise _erro("falha")
    s.page = vivas[-1]
    s.log.info("A aba do login fechou; o robô seguiu na aba que o portal deixou aberta.")
    return s.page


def _recusa_visivel(page) -> bool:
    try:
        for msg in visiveis(sel.login_mensagem_erro(page)):
            if sel.TEXTO_LOGIN_RECUSADO.search(msg.inner_text() or ""):
                return True
        return _visivel(page.get_by_text(sel.TEXTO_LOGIN_RECUSADO))
    except Exception:  # noqa: BLE001
        return False


def _digitar_senha(s, login: dict, campo) -> None:
    """Digita a senha guardada inteira. Portal real 07/11: depois do Continuar a 1ª tela mostra um campo "Senha"
    (#senha) com maxlength=8, mas o corretor entra com uma senha maior: o robô NÃO corta nem recusa a senha pelo
    maxlength (só registra no log, sem o valor) e preenche o valor inteiro."""
    page, log = s.page, s.log
    passo = "senha"
    try:
        s.mapa.login_digitado = True
        page.evaluate("() => document.querySelectorAll('form, input').forEach(e => e.setAttribute('autocomplete', 'off'))")
        # Portal real 07/11: a página da senha (nidp) tem o seu próprio campo (#input_cpf_cnpj) e pede um CPF ("Por
        # favor digite um CPF válido para prosseguir"): o CPF de acesso guardado na engrenagem, não o CNPJ da 1ª tela.
        passo = "CPF da página da senha"
        for doc in visiveis(sel.login_campo_documento_nidp(page))[:1]:
            if so_digitos(doc.input_value()) != so_digitos(login["cpf"]):
                doc.click()
                doc.fill("")
                doc.press_sequentially(so_digitos(login["cpf"]), delay=40)
                log.info("Página da senha: o robô preencheu o CPF de acesso guardado.")
        passo = "senha"
        limite = campo.get_attribute("maxlength")
        log.info(f"Senha: campo da página {sel.caminho(page) or '-'} (maxlength {limite or '-'}).")
        if limite and limite.isdigit() and len(login["senha"]) > int(limite):
            # O fill do navegador corta no maxlength (a senha sairia pela metade e o portal contaria uma tentativa
            # errada): tira o limite do campo antes de preencher.
            campo.evaluate("e => e.removeAttribute('maxlength')")
            log.info(f"O campo de senha diz maxlength={limite}; o robô preenche a senha guardada inteira.")
        campo.fill(login["senha"])
        passo = "Entrar"
        botoes = visiveis(sel.login_botao_entrar(page))
        if botoes:
            botoes[0].click()
        else:
            campo.press("Enter")
    except ErroLogin:
        raise
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui fazer o passo '{passo}' na tela da senha ({type(e).__name__}).")
        raise _erro("falha") from None


def _recusado(s, cofre) -> None:
    cofre.marcar_recusadas()
    try:
        textos = visiveis(sel.login_mensagem_erro(s.page))
        resposta = ocultar(" ".join(textos[0].inner_text().split()))[:200] if textos else ""
    except Exception:  # noqa: BLE001
        resposta = ""
    s.log.error("O portal recusou o login guardado" + (f" (mensagem do portal: \"{resposta}\")" if resposta else "")
                + ". O robô não tenta de novo até o login ser guardado outra vez.")
    raise _erro("recusadas")


def _digitar_codigo(s) -> None:
    page, log = s.page, s.log
    log.info("O portal pediu um código de verificação; pedindo na tela do Newport.")
    codigo = s.pedir_codigo() if s.pedir_codigo else None
    if not codigo:
        raise _erro("codigo")
    lembrar_segredos(codigo)
    try:
        sel.campo_codigo(page).first.fill(codigo)
        botoes = visiveis(sel.botao_confirmar_codigo(page))
        if botoes:
            botoes[0].click()
        else:
            sel.campo_codigo(page).first.press("Enter")
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui digitar o código de verificação ({type(e).__name__}).")
        raise _erro("falha") from None
    finally:
        codigo = None
    _esperar_ate(lambda: not visiveis(sel.campo_codigo(s.page)), 10)
