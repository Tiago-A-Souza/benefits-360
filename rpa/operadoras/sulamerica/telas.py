"""Esperas e atalhos específicos das telas da SulAmérica."""
from __future__ import annotations

import logging
import time

from playwright.sync_api import Page

from nucleo.navegador import ErroFluxo, conferir_parar, esperar_sumir, esperar_visivel, visiveis

from . import seletores as sel


def esperar_sem_skeleton(page: Page, timeout_ms: int = 30000) -> None:
    esperar_sumir(page, sel.skeletons, timeout_ms)


_COM_TOUR: list[Page] = []   # páginas onde o robô já pula o tour sozinho


def pular_tour_sempre(page: Page) -> None:
    """Antes de qualquer ação (clique, digitação), se o tour "Guia de navegação" estiver aberto por cima da tela,
    o Playwright clica em Pular primeiro. O tour aparece com atraso, entre uma conferência e um clique."""
    if any(p is page for p in _COM_TOUR):
        return
    guia = sel.guia_navegacao(page)
    page.add_locator_handler(guia, lambda: sel.botao_pular_guia(guia).first.click())
    _COM_TOUR.append(page)


class TelaReiniciou(Exception):
    """Depois de recarregar a tela travada o portal voltou ao começo (o estado do assistente só existe na aba): o fluxo
    retoma o pedido de onde o portal está. Só antes do resumo, com nada emitido."""


# Telas ANTES do resumo: nada foi emitido e recarregar a página é seguro. No resumo e depois dele o robô nunca recarrega.
_RECARREGAVEIS = {"cuidado_360", "congenere", "vidas", "idades", "planos", "comparacao"}
_ESPERA_ANTES_DE_RECARREGAR_S = 15          # teto; com `timeout_tela_ms` menor vale 20% dele (no mínimo 5 s)


def esperar_tela(page: Page, etapa: str, cfg: dict) -> None:
    """Espera o título da tela. 15/11: com vários robôs rodando juntos o portal novo às vezes trocava a URL e a barra de
    navegação mas deixava o corpo da tela anterior para sempre (sem requisição pendente, sem erro de JavaScript, a página
    desenhando quadros normalmente); passados 150 s o robô desistia. Antes do resumo (nada emitido), se o título não vier em
    15 s, recarrega a página uma vez, como o corretor faria com F5, e espera o resto do tempo."""
    pular_tour_sempre(page)
    timeout = cfg["execucao"].get("timeout_tela_ms", 60000)
    titulo = page.get_by_text(sel.TITULOS[etapa])
    antes = int(min(_ESPERA_ANTES_DE_RECARREGAR_S * 1000, max(5000, timeout * 0.2)))
    if etapa not in _RECARREGAVEIS or timeout <= antes:
        esperar_visivel(titulo, timeout, f"título da tela {etapa}", etapa)
    else:
        try:
            esperar_visivel(titulo, antes, f"título da tela {etapa}", etapa)
        except ErroFluxo:
            logging.getLogger("cotacao.sulamerica").warning(
                f"A tela {etapa} não apareceu em {antes // 1000} s (o portal trocou a URL mas manteve o "
                "corpo da tela anterior); recarregando a página uma vez (nada foi emitido).")
            page.reload(wait_until="domcontentloaded")
            _esperar_titulo_ou_reinicio(page, titulo, etapa, timeout - antes)
    esperar_sem_skeleton(page, timeout)
    fechar_guia(page)


def _esperar_titulo_ou_reinicio(page: Page, titulo, etapa: str, timeout_ms: int) -> None:
    """Depois do F5: o título da tela veio (segue) ou o portal voltou a outra tela, em geral o começo ("Comece por aqui"),
    com o assistente vazio (levanta TelaReiniciou). Nem uma coisa nem outra no prazo: ErroFluxo, como antes."""
    rota = next((pedaco for nome, pedaco in sel.ROTAS if nome == etapa), "")
    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        if visiveis(titulo):
            return
        if rota and rota not in sel.caminho(page) and visiveis(page.get_by_text(sel.TITULOS["dados_empresa"])):
            raise TelaReiniciou(etapa)
        conferir_parar(etapa)
        time.sleep(0.5)
    raise ErroFluxo(f"não encontrei 'título da tela {etapa}' na tela em {timeout_ms // 1000}s", etapa)


def fechar_guia(page: Page) -> bool:
    """O cotador abre um tour "Guia de navegação" por cima da tela (bloqueia os cliques): clica em Pular."""
    try:
        for dialogo in visiveis(sel.guia_navegacao(page)):
            for botao in visiveis(sel.botao_pular_guia(dialogo)):
                botao.click()
                esperar_sumir(page, sel.guia_navegacao, 5000)
                return True
    except Exception:  # noqa: BLE001  (o tour some sozinho às vezes)
        pass
    return False


def aceitar_cookies(page: Page) -> None:
    try:
        for el in visiveis(page.get_by_text(sel.TEXTO_COOKIES)):
            el.click(timeout=3000)
            break
    except Exception:  # noqa: BLE001
        pass
