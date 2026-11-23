"""Esperas e iframe do cotador da Porto. Sem regra de negócio."""
from __future__ import annotations

import re
import time

from nucleo.navegador import ErroFluxo, conferir_parar, visiveis

from . import seletores as sel


class SessaoCaiu(ErroFluxo):
    """O portal pediu o login de novo no meio do trabalho."""


def _visivel(loc) -> bool:
    try:
        return bool(visiveis(loc))
    except Exception:  # noqa: BLE001
        return False


def tela_susep(page) -> bool:
    """Dropdown da SUSEP depois do CPF/senha — ainda não está dentro do cotador."""
    try:
        if page.is_closed() or _visivel(page.locator("iframe#cotador")):
            return False
        if _visivel(sel.login_campo_senha(page)):
            return False
        path = sel.caminho(page)
        if path.startswith(sel.ROTA_HOME):
            return False
        if path.startswith(sel.ROTA_SUSEP):
            return True
        if _visivel(sel.susep_caixa(page)) or _visivel(sel.susep_select(page)):
            return True
        return _visivel(page.get_by_text(sel.TEXTO_ACESSE_CORRETOR)) and _visivel(
            page.get_by_text(re.compile(r"^susep$", re.I))
        )
    except Exception:  # noqa: BLE001
        return False


def login_na_tela(page) -> bool:
    try:
        if page.is_closed():
            return False
        return _visivel(sel.login_campo_senha(page)) or sel.caminho(page).startswith(sel.ROTA_LOGIN)
    except Exception:  # noqa: BLE001
        return False


def logado(page) -> bool:
    try:
        if page.is_closed() or login_na_tela(page) or tela_susep(page):
            return False
        path = sel.caminho(page)
        return path.startswith(sel.ROTA_HOME) or path.startswith("/novocol") \
            or _visivel(page.locator("iframe#cotador")) or _visivel(page.get_by_text("EDLAINE"))
    except Exception:  # noqa: BLE001
        return False


def esperar_ate(condicao, segundos: float, intervalo: float = 0.25) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            if condicao():
                return True
        except Exception:  # noqa: BLE001
            pass
        conferir_parar()
        time.sleep(intervalo)
    try:
        return bool(condicao())
    except Exception:  # noqa: BLE001
        return False


def cotador(page):
    """O iframe do cotador, ou a própria página se o cotador já for a URL."""
    try:
        if page.locator("iframe#cotador").count():
            return sel.iframe_cotador(page)
    except Exception:  # noqa: BLE001
        pass
    return page


def texto_do_cotador(page, limite: int = 60000) -> str:
    lugar = cotador(page)
    try:
        return (lugar.locator("body").inner_text(timeout=5000) or "")[:limite]
    except Exception:  # noqa: BLE001
        try:
            return (page.locator("body").inner_text(timeout=5000) or "")[:limite]
        except Exception:  # noqa: BLE001
            return ""


def fechar_overlays(page) -> None:
    try:
        banner = page.get_by_text(sel.TEXTO_BANNER_DUVIDAS)
        if _visivel(banner):
            page.get_by_role("button", name=re.compile(r"fechar|ok|x", re.I)).first.click(timeout=2000)
    except Exception:  # noqa: BLE001
        pass
    try:
        lugar = cotador(page)
        if _visivel(lugar.get_by_text(sel.TEXTO_BANNER_DUVIDAS)):
            lugar.get_by_role("button", name=re.compile(r"fechar|ok|x", re.I)).first.click(timeout=2000)
    except Exception:  # noqa: BLE001
        pass
