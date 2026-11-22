"""Login automático da Porto (Corretor Online): CPF + senha do cofre NewportCotacoes/porto e SUSEP da engrenagem.

Regras:
- só entra quando o portal pede; a sessão fica no perfil do navegador;
- nada do que é digitado vai para log, mapa, evento ou erro;
- recusado: para na primeira vez;
- reCAPTCHA ou 2FA: para e avisa. Nunca tenta burlar.
"""
from __future__ import annotations

import time
from datetime import datetime

from nucleo.configuracao import aprendido, aprender
from nucleo.credenciais import cofre as cofre_da_config, mensagem_login
from nucleo.navegador import ErroLogin, Parado

from . import seletores as sel
from .telas import _visivel, esperar_ate, logado, login_na_tela

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


def _abrir_login(s) -> None:
    s.page.goto(s.cfg["urls"]["login"])
    s.page.wait_for_load_state("domcontentloaded")


def _preencher(page, campo, valor: str) -> None:
    campo.first.click()
    campo.first.fill(valor)


def _escolher_susep(s) -> None:
    codigo = (s.cfg.get("padroes") or {}).get("susep") or "BX865J"
    if esperar_ate(lambda: _visivel(sel.susep_opcao(s.page, codigo)), s.t("timeout_tela_ms") / 1000):
        s.aviso("etapa", etapa="susep", pedido="", plano="")
        sel.susep_opcao(s.page, codigo).first.click()
        s.log.info(f"SUSEP escolhida: {codigo}.")
        esperar_ate(lambda: _visivel(s.page.locator("iframe#cotador")) or sel.caminho(s.page).startswith(sel.ROTA_HOME), 15)


def entrar(s, pode_parar: bool = True, insistir: bool = True) -> None:
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if logado(page) and not login_na_tela(page):
        _sessao_viva(s)
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not login_na_tela(page):
        _abrir_login(s)
    if logado(page) and not login_na_tela(page):
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


def _tentar_login(s, cofre, login: dict, parar) -> None:
    page, log = s.page, s.log
    if _visivel(sel.captcha_desafio(page)):
        raise _erro("captcha")
    s.aviso("login_entrando")
    log.info("Entrando no portal da Porto com o login guardado na engrenagem do robô.")
    esperar_ate(lambda: _visivel(sel.login_campo_cpf(page)) or _visivel(sel.login_campo_senha(page)),
                s.t("timeout_tela_ms") / 1000)
    s.mapa.registrar(page, "login", login_vazio=True)
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    digitou = {"cpf": False, "senha": False}
    recusa_antes = _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN))
    try:
        while time.monotonic() < fim:
            if parar():
                raise Parado("login")
            if _visivel(sel.captcha_desafio(page)):
                raise _erro("captcha")
            if _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)):
                raise _erro("troca_senha")
            if logado(page) and not login_na_tela(page):
                _sessao_nova(s)
                _escolher_susep(s)
                return
            if _visivel(sel.susep_opcao(page, (s.cfg.get("padroes") or {}).get("susep") or "BX865J")):
                _sessao_nova(s)
                _escolher_susep(s)
                return
            if _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)) and not recusa_antes and digitou["senha"]:
                time.sleep(0.8)
                if not logado(page) and _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN)):
                    cofre.marcar_recusadas()
                    raise _erro("recusadas")
            if _visivel(sel.login_campo_cpf(page)) and not digitou["cpf"]:
                s.mapa.login_digitado = True
                _preencher(page, sel.login_campo_cpf(page), login["cpf"])
                digitou["cpf"] = True
                continue
            if _visivel(sel.login_campo_senha(page)) and not digitou["senha"]:
                s.mapa.login_digitado = True
                _preencher(page, sel.login_campo_senha(page), login["senha"])
                digitou["senha"] = True
                sel.login_botao_entrar(page).first.click()
                time.sleep(0.5)
                continue
            time.sleep(0.3)
    except (ErroLogin, Parado):
        raise
    except Exception as e:  # noqa: BLE001
        raise ErroLogin(_erro("falha").args[0], "falha") from None
    raise _erro("sem_resposta")
