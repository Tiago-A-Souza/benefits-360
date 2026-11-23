"""Login automático da Porto (Corretor Online): CPF, senha e SUSEP do cofre NewportCotacoes/porto.

Regras:
- só entra quando o portal pede; a sessão fica no perfil do navegador;
- depois do CPF e da senha, escolhe o código SUSEP no dropdown (o mesmo guardado no login);
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
from .telas import _visivel, esperar_ate, logado, login_na_tela, tela_susep

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


def _codigo_susep(s, login: dict | None) -> str:
    """Código do cofre (Conexões); se faltar, o padrão da engrenagem. Aceita 'BX865J (P)'."""
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
    s.aviso("etapa", etapa="susep", pedido="", plano="")
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
    s.log.info("SUSEP escolhida na lista do portal.")
    botao = sel.susep_botao_seguir(page)
    if _visivel(botao):
        botao.first.click()
        time.sleep(0.4)
    esperar_ate(lambda: logado(page), 15)


def entrar(s, pode_parar: bool = True, insistir: bool = True) -> None:
    page, log = s.page, s.log
    parar = s.pediu_parar if pode_parar else (lambda: False)
    if logado(page) and not login_na_tela(page) and not tela_susep(page):
        _sessao_viva(s)
        s.aviso("login_ok", sessao_ativa=True)
        return
    if not login_na_tela(page) and not tela_susep(page):
        _abrir_login(s)
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


def _tentar_login(s, cofre, login: dict, parar, codigo_susep: str) -> None:
    page, log = s.page, s.log
    if _visivel(sel.captcha_desafio(page)):
        raise _erro("captcha")
    s.aviso("login_entrando")
    log.info("Entrando no portal da Porto com o login guardado na engrenagem do robô.")
    esperar_ate(lambda: _visivel(sel.login_campo_cpf(page)) or _visivel(sel.login_campo_senha(page))
                or tela_susep(page), s.t("timeout_tela_ms") / 1000)
    s.mapa.registrar(page, "login", login_vazio=True)
    limite = s.cfg["execucao"].get("timeout_login_ms", 60000) / 1000
    fim = time.monotonic() + limite
    digitou = {"cpf": False, "senha": False, "susep": False}
    recusa_antes = _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN))
    try:
        while time.monotonic() < fim:
            if parar():
                raise Parado("login")
            if _visivel(sel.captcha_desafio(page)):
                raise _erro("captcha")
            if _visivel(page.get_by_text(sel.TEXTO_TROCA_SENHA)):
                raise _erro("troca_senha")
            if logado(page) and not login_na_tela(page) and not tela_susep(page):
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
