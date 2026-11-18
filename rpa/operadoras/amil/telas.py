"""Ajudas de tela do portal da Amil: esperas, listas, avisos e a sessão. Sem regra de negócio."""
from __future__ import annotations

import re
import time

from nucleo.navegador import ErroFluxo, conferir_parar, visiveis
from nucleo.texto import norm

from . import seletores as sel


class SessaoCaiu(ErroFluxo):
    """O portal mandou de volta para o login no meio do trabalho."""


def _visivel(loc) -> bool:
    try:
        return bool(visiveis(loc))
    except Exception:  # noqa: BLE001  (página navegando)
        return False


def login_na_tela(page) -> bool:
    """A página é o login: pelo caminho (/login), ou com o campo de senha ou o de código à vista."""
    try:
        if page.is_closed():
            return False
        if sel.caminho(page).startswith(sel.ROTA_LOGIN):
            return True
        return _visivel(sel.login_campo_senha(page)) or _visivel(sel.campo_codigo(page))
    except Exception:  # noqa: BLE001
        return False


def logado(page) -> bool:
    """O portal logado: fora do /login, com o menu lateral ("Criar Oportunidade PME") à vista."""
    try:
        if page.is_closed() or login_na_tela(page):
            return False
        return _visivel(page.get_by_text(sel.TEXTO_MENU_OPORTUNIDADE_PME)) or any(
            p in sel.caminho(page) for p in (sel.ROTA_OPORTUNIDADE, sel.ROTA_COTACAO, sel.ROTA_OPORTUNIDADE_NOVA))
    except Exception:  # noqa: BLE001
        return False


def esperar_ate(condicao, segundos: float, intervalo: float = 0.25) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            if condicao():
                return True
        except Exception:  # noqa: BLE001  (tela mudando)
            pass
        conferir_parar()
        time.sleep(intervalo)
    try:
        return bool(condicao())
    except Exception:  # noqa: BLE001
        return False


def esperar_sem_carregando(page, segundos: float = 30) -> None:
    """Espera acabarem o "Carregando…" e os avisos de verificação entre as telas (mapa, Seção 5.7)."""
    esperar_ate(lambda: not _visivel(page.get_by_text(sel.TEXTO_CARREGANDO)), segundos)


def fechar_avisos(page) -> None:
    """Fecha os avisos (toasts) do canto superior direito: "PDF Gerado", "Cotação concluída com sucesso!"..."""
    try:
        avisos = page.locator("[role=alert], [role=status], [class*=toast i], [class*=snackbar i]")
        for botao in visiveis(avisos.get_by_role("button"))[:4]:
            botao.click(timeout=2000)
    except Exception:  # noqa: BLE001
        pass


def texto_da_pagina(page, limite: int = 60000) -> str:
    try:
        return (page.locator("body").inner_text(timeout=5000) or "")[:limite]
    except Exception:  # noqa: BLE001
        return ""


def opcoes_do_select(campo) -> list[str]:
    return [" ".join(o.split()) for o in campo.locator("option").all_inner_texts()]


def escolher_no_select(campo, texto: str, descricao: str, etapa: str) -> str:
    """<select> nativo: escolhe a opção de texto exato (sem acento, sem maiúsculas). Não achou: para e mostra o que viu."""
    opcoes = opcoes_do_select(campo)
    alvo = norm(texto)
    escolhida = next((o for o in opcoes if norm(o) == alvo), None)
    if escolhida is None:
        vistas = [o for o in opcoes if not norm(o).startswith("selecione")]
        raise ErroFluxo(f"'{texto}' não está na lista '{descricao}' do portal. Nomes que o robô viu: "
                        f"{'; '.join(vistas[:80])}", etapa)
    campo.select_option(label=escolhida)
    return escolhida


def escolher_na_lista(page, abrir, texto: str, descricao: str, etapa: str, busca=None, segundos: float = 10) -> str:
    """Lista aberta por clique (quadro 10): abre, digita para filtrar (se há busca) e escolhe a opção que contém o texto.
    O corretor aparece como "30227287860 - EDLAINE ABREU SOARES": vale o texto contido, sem acento nem maiúsculas."""
    abrir.first.click()
    if busca is not None and esperar_ate(lambda: _visivel(busca), 3):
        busca.first.fill(texto)
    alvo = norm(texto)
    achada = {}

    def candidatas():
        # no portal real as opções do corretor não são role=option (print do corretor, 12/11): vale também o menor
        # elemento visível com o texto ("30227287860 – EDLAINE ABREU SOARES"); campo digitado não conta (value não é texto)
        return visiveis(sel.opcoes_da_lista(page)) or visiveis(page.get_by_text(re.compile(re.escape(texto), re.I)))

    def procurar() -> bool:
        for o in candidatas():
            t = " ".join(o.inner_text().split())
            if alvo in norm(t):
                achada["opcao"], achada["texto"] = o, t
                return True
        return False

    if not esperar_ate(procurar, segundos):
        vistas = []
        try:
            vistas = [" ".join(o.inner_text().split()) for o in candidatas()[:40]]
        except Exception:  # noqa: BLE001
            pass
        raise ErroFluxo(f"'{texto}' não está na lista '{descricao}' do portal. Nomes que o robô viu: "
                        f"{'; '.join(vistas) or '(lista vazia)'}", etapa)
    achada["opcao"].click()
    return achada["texto"]


def ajustar_mapa(mapa, page) -> None:
    """O Mapeador do núcleo toma por "tela de código de verificação" qualquer tela com um campo visível cujo nome ou
    placeholder tenha "código", "verifica"... Na Amil o Vínculo de Vendas tem "Digite nome ou código do corretor" e
    "Verificando corretora...": ficava sem mapa (12/11). Aqui, só nesta operadora, a tela é de código quando o campo do
    código de 8 dígitos do login (placeholder 00000000) está visível; fora disso vale o resto da regra do núcleo (login:
    URL do login ou campo de senha). A tela de código de verificação de verdade continua sem mapa."""
    from urllib.parse import urlparse
    from nucleo.navegador import _JS_CAMPO_SENHA
    original = getattr(mapa, "tela_sensivel", None)
    if original is None:
        return

    def tela_sensivel(pagina):
        achado = original(pagina)
        if achado != "codigo":
            return achado
        try:
            if _visivel(sel.campo_codigo(pagina)):
                return "codigo"
            if mapa.path_login and urlparse(pagina.url).path.rstrip("/").lower() == mapa.path_login:
                return "login"
            return "login" if any(f.evaluate(_JS_CAMPO_SENHA) for f in pagina.frames) else None
        except Exception:  # noqa: BLE001
            return "login"
    mapa.tela_sensivel = tela_sensivel
