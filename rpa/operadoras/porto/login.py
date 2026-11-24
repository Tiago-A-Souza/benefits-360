"""Login automático da Porto (Corretor Online): CPF, senha e SUSEP do cofre NewportCotacoes/porto.

Regras:
- página pública → recusa localização/cookies → «Acessar o Corretor Online» → janela;
- na janela, CPF e senha (se o portal mostrar) e o dropdown da SUSEP só por clique;
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
from playwright.sync_api import TimeoutError as PWTimeout

from nucleo.navegador import ErroLogin, Parado

from . import seletores as sel
from .telas import (
    _visivel, esperar_ate, fechar_banners_entrada, logado, login_na_tela,
    primeiro_visivel, tela_susep,
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


def _abrir_janela_corretor(s, botao) -> None:
    page = s.page
    try:
        with page.expect_popup(timeout=8000) as info:
            botao.first.click(timeout=5000)
        nova = info.value
        nova.wait_for_load_state("domcontentloaded")
        s.page = nova
        _marcar(s, "janela do corretor online", "Janela do Corretor Online aberta.")
        return
    except PWTimeout:
        pass
    except Exception:  # noqa: BLE001
        try:
            botao.first.click(timeout=5000)
        except Exception:  # noqa: BLE001
            pass
    if not esperar_ate(lambda: _login_a_vista(s.page), 12):
        raise _erro("sem_janela_login")
    _marcar(s, "janela do corretor online", "Janela do Corretor Online aberta.")


def _abrir_login(s) -> None:
    """Página pública → recusa localização/cookies → «Acessar o Corretor Online» → janela de login."""
    _marcar(s, "abrindo login", "Abrindo a página pública do Corretor Online.")
    s.page.goto(s.cfg["urls"]["login"])
    s.page.wait_for_load_state("domcontentloaded")
    fechar_banners_entrada(s.page)
    _marcar(s, "abrindo login", "Primeira página da Porto aberta (localização recusada pelo navegador).",
            captura="entrada_porto")
    if _login_a_vista(s.page):
        return
    botao = primeiro_visivel(s.page, sel.botao_acessar_corretor)
    if not _visivel(botao):
        if not esperar_ate(lambda: _login_a_vista(s.page) or _visivel(
                primeiro_visivel(s.page, sel.botao_acessar_corretor)), s.t("timeout_tela_ms") / 1000):
            raise _erro("sem_botao_entrada")
        botao = primeiro_visivel(s.page, sel.botao_acessar_corretor)
        if _login_a_vista(s.page):
            return
    fechar_banners_entrada(s.page)
    _marcar(s, "abrindo login", "Clicando em Acessar o Corretor Online.")
    _abrir_janela_corretor(s, botao)
    fechar_banners_entrada(s.page)


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
    recusa_antes = _visivel(page.get_by_text(sel.TEXTO_RECUSA_LOGIN))
    try:
        while time.monotonic() < fim:
            if parar():
                raise Parado("login")
            page = s.page
            if _visivel(sel.captcha_desafio(page)):
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
                _marcar(s, "CPF e senha enviados", "CPF e senha enviados.")
                time.sleep(0.5)
                continue
            time.sleep(0.3)
    except (ErroLogin, Parado):
        raise
    except Exception as e:  # noqa: BLE001
        raise ErroLogin(_erro("falha").args[0], "falha") from None
    raise _erro("sem_resposta")
