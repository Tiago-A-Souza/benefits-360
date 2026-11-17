"""Login automático da Amil (vendasmil): o robô entra com o login que o corretor guardou na engrenagem do robô (cofre do
Windows, nucleo/credenciais.py) e, quando o portal manda o CÓDIGO DE VERIFICAÇÃO de 8 dígitos por e-mail, pede o código na
tela do Newport (sessao.pedir_codigo) e digita aqui. O corretor nunca mexe na janela do portal.

Regras (as mesmas da SulAmérica):
- só entra quando o portal pede; a sessão fica no perfil do navegador (saida/amil/perfil_navegador) para pedir código o
  menos possível, e o robô registra no log quanto tempo ela dura (portal.json: sessao_login_em / sessao_viva_em);
- nada do que é digitado vai para log, mapa, evento ou erro: qualquer falha com o login na tela vira ErroLogin com frase
  fixa (`from None`); o log diz só em que passo parou; o mapa da tela de login só antes de digitar;
- recusado pelo portal: para na PRIMEIRA vez e marca o login como recusado (não tenta de novo até guardar a senha outra vez);
- captcha, troca de senha: para e avisa. Captcha nunca é resolvido pelo robô.

A 1ª etapa do login não aparece no vídeo (só a do código): o robô trata as duas formas, usuário e senha na mesma página ou
em duas, e o mapa `NN_login.*` (tirado antes de digitar) calibra os seletores.
"""
from __future__ import annotations

import re
import time
from datetime import datetime

from nucleo.configuracao import aprendido, aprender
from nucleo.credenciais import cofre as cofre_da_config, lembrar_segredos, mensagem_login
from nucleo.navegador import ErroLogin, Parado, esperar_visivel

from . import seletores as sel
from .telas import _visivel, esperar_ate, esperar_sem_carregando, logado, login_na_tela

OPERADORA = ("amil", "Amil")


def _erro(motivo: str) -> ErroLogin:
    from . import Amil
    return ErroLogin(mensagem_login(motivo, OPERADORA[1], Amil.mensagens_login), motivo)


def _agora() -> datetime:
    return datetime.now().replace(microsecond=0)


def _minutos(de: str, ate: datetime) -> int | None:
    try:
        return int((ate - datetime.fromisoformat(de)).total_seconds() // 60)
    except (TypeError, ValueError):
        return None


def _sessao_viva(s) -> None:
    """A sessão do portal segue aberta agora: guarda quando (para medir quanto ela dura) e diz há quanto tempo é."""
    pasta = s.cfg["saida"]["pasta"]
    dados = aprendido(pasta)
    agora = _agora()
    if dados.get("sessao_login_em"):
        s.log.info(f"Sessão do portal aberta: não precisa entrar de novo (login feito há "
                   f"{_minutos(dados['sessao_login_em'], agora)} min).")
    else:
        s.log.info("Sessão do portal aberta: não precisa entrar de novo.")
    aprender(pasta, "sessao_viva_em", agora.isoformat())


def _sessao_nova(s, com_codigo: bool) -> None:
    """Login feito: registra o começo da sessão e quanto durou a anterior (entre a última vez em que o robô a viu aberta e
    agora; o portal pode tê-la encerrado antes, o robô só descobre quando volta)."""
    pasta = s.cfg["saida"]["pasta"]
    antes = aprendido(pasta)
    agora = _agora()
    if antes.get("sessao_login_em"):
        minimo = _minutos(antes["sessao_login_em"], datetime.fromisoformat(antes.get("sessao_viva_em") or antes["sessao_login_em"]))
        maximo = _minutos(antes["sessao_login_em"], agora)
        s.log.info(f"A sessão anterior durou de {minimo} a {maximo} min (do login até a última vez que o robô a viu aberta "
                   "/ até este novo login).")
        duracoes = list(antes.get("sessao_duracoes_min") or [])[-9:] + [[minimo, maximo]]
        aprender(pasta, "sessao_duracoes_min", duracoes)
    aprender(pasta, "sessao_login_em", agora.isoformat())
    aprender(pasta, "sessao_viva_em", agora.isoformat())
    s.log.info("Login feito" + (" (com código de verificação)." if com_codigo else " (o portal não pediu código)."))
    s.aviso("login_ok", sessao_ativa=False)


def _abrir_login(s) -> None:
    s.page.goto(s.cfg["urls"]["login"])
    s.page.wait_for_load_state("domcontentloaded")
    esperar_sem_carregando(s.page, 10)


def entrar(s, pode_parar: bool = True, insistir: bool = True) -> None:
    """Garante a sessão no portal. Com a sessão aberta (perfil do navegador), não digita nada."""
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if logado(page):
        _sessao_viva(s)
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not login_na_tela(page):
        _abrir_login(s)
    if logado(page):
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
        _tentar_login(s, cofre, login, parar)
    finally:
        login = None


def _preencher(page, campo, valor: str) -> None:
    campo.first.click()
    campo.first.fill(valor)


def _tentar_login(s, cofre, login: dict, parar) -> None:
    page, log = s.page, s.log
    if _visivel(page.get_by_text(sel.TEXTO_CAPTCHA)):
        raise _erro("captcha")
    s.aviso("login_entrando")
    log.info("Entrando no portal da Amil com o login guardado na engrenagem do robô.")
    esperar_ate(lambda: _visivel(sel.login_campo_usuario(page)) or _visivel(sel.login_campo_senha(page))
                or _visivel(sel.campo_codigo(page)), s.t("timeout_tela_ms") / 1000)
    s.mapa.registrar(page, "login", login_vazio=True)          # só com os campos vazios (calibra o login)
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    digitou = {"usuario": False, "senha": False}
    codigos = 0
    com_codigo = False
    recusa_antes = _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN))
    passo = "esperar a tela de login"
    try:
        while time.monotonic() < fim:
            if parar():
                raise Parado("login")
            if logado(page):
                _sessao_nova(s, com_codigo)
                return
            if _visivel(page.get_by_text(sel.TEXTO_CAPTCHA)):
                raise _erro("captcha")
            if _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)):
                raise _erro("troca_senha")
            if _visivel(sel.campo_codigo(page)):
                if codigos >= 3:
                    raise _erro("codigo")
                codigos += 1
                com_codigo = True
                _digitar_codigo(s)
                fim = time.monotonic() + limite                # o tempo recomeça depois do código
                continue
            if _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)) and not recusa_antes and (digitou["senha"]):
                time.sleep(0.8)                                # confirma com a página assentada
                if not logado(page) and _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)):
                    _recusado(s, cofre)
            if _visivel(sel.login_campo_usuario(page)) and not digitou["usuario"]:
                passo = "digitar o usuário"
                s.mapa.login_digitado = True
                page.evaluate("() => document.querySelectorAll('form, input').forEach(e => e.setAttribute('autocomplete', 'off'))")
                _preencher(page, sel.login_campo_usuario(page), login["usuario"])
                digitou["usuario"] = True
                if not _visivel(sel.login_campo_senha(page)):  # usuário e senha em duas páginas: avança
                    passo = "avançar depois do usuário"
                    sel.login_botao_entrar(page).first.click()
                    time.sleep(0.5)
                continue
            if _visivel(sel.login_campo_senha(page)) and not digitou["senha"]:
                passo = "digitar a senha"
                s.mapa.login_digitado = True
                _preencher(page, sel.login_campo_senha(page), login["senha"])
                digitou["senha"] = True
                passo = "Entrar"
                sel.login_botao_entrar(page).first.click()
                time.sleep(0.5)
                continue
            time.sleep(0.3)
    except (ErroLogin, Parado):
        raise
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui fazer o passo '{passo}' na tela de login ({type(e).__name__}).")
        raise _erro("falha") from None
    if digitou["senha"] and login_na_tela(page):
        raise _erro("sem_resposta")
    raise _erro("falha")


def _recusado(s, cofre) -> None:
    cofre.marcar_recusadas()
    s.log.error("O portal recusou o login guardado. O robô não tenta de novo até a senha ser guardada outra vez.")
    raise _erro("recusadas")


def _digitar_codigo(s) -> None:
    """O portal manda o código de 8 dígitos por e-mail: pede na tela do Newport e digita. O código nunca vai para o log."""
    page, log = s.page, s.log
    log.info("O portal pediu o código de verificação de 8 dígitos (chega por e-mail, vale 15 min); pedindo na tela do Newport.")
    codigo = s.pedir_codigo() if s.pedir_codigo else None
    codigo = re.sub(r"\D", "", codigo or "")
    if not codigo:
        raise _erro("codigo")
    lembrar_segredos(codigo)
    try:
        esperar_visivel(sel.campo_codigo(page), 5000, "campo do código de verificação", "login")
        sel.campo_codigo(page).first.fill(codigo)
        botao = sel.botao_verificar_codigo(page).first
        esperar_ate(botao.is_enabled, 3)               # o botão só acende com o código inteiro (quadro 01 -> 03)
        s.mapa.login_digitado = True
        botao.click()
    except Exception as e:  # noqa: BLE001
        log.error(f"Login: não consegui digitar o código de verificação ({type(e).__name__}).")
        raise _erro("falha") from None
    finally:
        codigo = None
    # espera a resposta do portal ao código: entra, ou o campo some/volta com a mensagem de código recusado
    fim = time.monotonic() + 10
    while time.monotonic() < fim:
        if logado(page):
            return
        if _visivel(page.get_by_text(sel.TEXTO_CODIGO_RECUSADO)):
            log.warning("O portal não aceitou o código de verificação; o robô pede de novo na tela do Newport.")
            return
        time.sleep(0.3)
