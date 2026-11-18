"""Esperas e atalhos das telas da Bradesco: quadro (iframe) das páginas antigas, botões de escolha, listas
"Selecione" e modais de OK."""
from __future__ import annotations

import re
import time

from nucleo.navegador import ErroFluxo, conferir_parar, visiveis
from nucleo.texto import norm, rx

from . import seletores as sel


class SessaoCaiu(ErroFluxo):
    """O portal mostrou o login no meio do pedido (a sessão acabou)."""


def _visivel(loc) -> bool:
    try:
        return bool(visiveis(loc))
    except Exception:  # noqa: BLE001  (página navegando)
        return False


def login_na_tela(page) -> bool:
    """A página é o login (1ª etapa, CPF/CNPJ) ou a senha (nidp)."""
    try:
        if page.is_closed():
            return False
        return (_visivel(sel.login_campo_documento(page)) or sel.ROTA_NIDP in sel.caminho(page)
                or (sel.ROTA_LOGIN in sel.caminho(page) and not _visivel(page.get_by_text(sel.TEXTO_LOGADO))))
    except Exception:  # noqa: BLE001
        return False


def lugares(page) -> list:
    """A página e os quadros (iframes) dela, nesta ordem."""
    try:
        return [page] + [f for f in page.frames if f is not page.main_frame]
    except Exception:  # noqa: BLE001
        return [page]


def descrever(page, limite: int = 160) -> str:
    """Onde o robô está, para o log de uma espera que estourou: caminho e o começo do texto de cada quadro do portal.
    Nunca valores digitados (só o que a tela mostra); passa por ocultar()."""
    from urllib.parse import urlparse

    from nucleo.credenciais import ocultar
    partes = []
    try:
        for n, quadro in enumerate(lugares(page)):
            try:
                url = urlparse(quadro.url)
                if "bradesco" not in url.netloc and "127.0.0.1" not in url.netloc and "localhost" not in url.netloc:
                    continue
                texto = " ".join((quadro.evaluate("() => document.body ? document.body.innerText : ''") or "").split())
                partes.append(f"[{'página' if n == 0 else f'quadro {n}'}] {url.path or '/'} :: {ocultar(texto[:limite]) or '(vazio)'}")
            except Exception as e:  # noqa: BLE001
                partes.append(f"[quadro {n}] ({type(e).__name__})")
    except Exception as e:  # noqa: BLE001
        return f"(não consegui descrever a tela: {type(e).__name__})"
    return " | ".join(partes) or "(sem quadros do portal)"


def quadro_com(page, padrao: re.Pattern, timeout_ms: int, descricao: str, etapa: str):
    """A página ou o quadro (iframe) que mostra o texto. As páginas antigas (cálculo, Alterar Cotação) ficam num
    iframe no portal real (barra de rolagem própria no vídeo); o simulador faz igual."""
    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        for lugar in lugares(page):
            if _visivel(lugar.get_by_text(padrao)):
                return lugar
        if login_na_tela(page):
            raise SessaoCaiu("o portal pediu o login de novo (a sessão acabou)", etapa)
        conferir_parar(etapa)
        time.sleep(0.25)
    raise ErroFluxo(f"não encontrei '{descricao}' na tela em {timeout_ms // 1000}s. Tela: {descrever(page)}", etapa)


def esperar(page, padrao: re.Pattern, timeout_ms: int, descricao: str, etapa: str):
    """Espera o texto na página (cotador novo). Se o login aparecer no caminho, levanta SessaoCaiu."""
    return quadro_com(page, padrao, timeout_ms, descricao, etapa)


def grupo_de(lugar, rotulo: str):
    """O bloco do campo: o menor elemento que tem o rótulo e botões ou uma lista (ex.: "Modalidade de Adesão")."""
    padrao = rx(rotulo)
    return lugar.locator("div, fieldset, section, li").filter(has=lugar.get_by_text(padrao)).filter(
        has=lugar.locator("button, [role=button], [role=combobox], select, input")).last


def pressionado(botao) -> bool:
    """Botão de escolha marcado (aria-pressed/aria-checked/aria-selected, ou a classe "ativo/selecionado")."""
    try:
        for attr in ("aria-pressed", "aria-checked", "aria-selected"):
            if (botao.get_attribute(attr) or "").lower() == "true":
                return True
        classe = (botao.get_attribute("class") or "").lower()
        return bool(re.search(r"\b(active|ativo|selected|selecionad\w*|checked|marcad\w*)\b", classe))
    except Exception:  # noqa: BLE001
        return False


def escolher(lugar, rotulo: str, opcao: str, etapa: str, timeout_ms: int = 10000) -> bool:
    """Marca a opção (botão) do campo, se ainda não estiver marcada. True se clicou."""
    grupo = grupo_de(lugar, rotulo)
    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        # botão de escolha (aria-pressed) ou, no portal real 07/11, <button role="radio" aria-checked>
        botoes = visiveis(grupo.get_by_role("button", name=rx(opcao, exato=True)).or_(
            grupo.get_by_role("radio", name=rx(opcao, exato=True))))
        if botoes:
            if pressionado(botoes[0]):
                return False
            botoes[0].click()
            return True
        conferir_parar(etapa)
        time.sleep(0.2)
    raise ErroFluxo(f"não encontrei a opção '{opcao}' em '{rotulo}'", etapa)


def desmarcar_todas(lugar, rotulo: str) -> None:
    """Desmarca as opções marcadas de um campo de liga/desliga (ex.: Desconto de comissionamento)."""
    grupo = grupo_de(lugar, rotulo)
    for b in visiveis(grupo.get_by_role("button")):
        if pressionado(b):
            b.click()


def escolher_combo(lugar, rotulo: str, texto: str, etapa: str, digitar: str = "", exato: bool = False,
                   timeout_ms: int = 10000) -> str:
    """Lista "Selecione": abre (digitando o começo, se pedir) e clica na opção que começa com `texto` (ou é igual a
    ele, com exato=True). Portal real 07/11: as listas são ng-select SEM nome acessível (achadas pelo rótulo do campo)
    e as opções são div.ng-option. Devolve a opção escolhida."""
    alvo = norm(texto)

    def bate(valor: str) -> bool:
        n = norm(valor)
        return bool(n) and (n == alvo if exato else n.startswith(alvo))

    nomeada = lugar.get_by_role("combobox", name=rx(rotulo))
    grupo = grupo_de(lugar, rotulo)
    fim = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < fim:
        caixas = visiveis(nomeada) or visiveis(grupo.get_by_role("combobox"))
        if caixas and caixas[0].is_enabled():
            caixa = caixas[0]
            atuais = [caixa.input_value()] + [x.inner_text() for x in visiveis(grupo.locator(".ng-value-label, .ng-value"))]
            for valor in atuais:
                if bate(valor):
                    return " ".join(valor.split())
            caixa.click()
            if digitar:
                caixa.fill("")
                caixa.press_sequentially(digitar, delay=60)
            fim_lista = time.monotonic() + 6
            while time.monotonic() < fim_lista:
                for op in visiveis(lugar.locator(sel.OPCOES_LISTA)):
                    if bate(op.inner_text()):
                        escolhida = " ".join(op.inner_text().split())
                        op.click()
                        return escolhida
                time.sleep(0.2)
            opcoes = "; ".join(" ".join(o.inner_text().split()) for o in visiveis(lugar.locator(sel.OPCOES_LISTA))[:12])
            raise ErroFluxo(f"'{texto}' não está na lista '{rotulo}' (opções: {opcoes or 'nenhuma'})", etapa)
        time.sleep(0.25)
    raise ErroFluxo(f"a lista '{rotulo}' não apareceu (ou continua desabilitada)", etapa)


def escolher_select(lugar, rotulo: str, texto: str, etapa: str, comeca: bool = False) -> str:
    """<select> do formulário antigo: escolhe a opção pelo texto (sem acento, maiúsculas). Devolve a escolhida."""
    campo = sel.select_antigo(lugar, rotulo).first
    opcoes = [" ".join(o.split()) for o in campo.locator("option").all_inner_texts()]
    alvo = norm(texto)
    escolhida = next((o for o in opcoes if norm(o) == alvo), None)
    if escolhida is None and comeca:
        escolhida = next((o for o in opcoes if norm(o).startswith(alvo)), None)
    if escolhida is None:
        raise ErroFluxo(f"'{texto}' não está na lista '{rotulo}' (opções: {'; '.join(opcoes)})", etapa)
    campo.select_option(label=escolhida)
    return escolhida


def fechar_modais_ok(page, segundos: float = 3) -> list[str]:
    """Clica OK nos modais que aparecerem (ex.: "válido por 40 dias", "Processo #N"), em qualquer quadro. Devolve o
    texto de cada modal fechado (o robô confere o número do processo nele)."""
    textos: list[str] = []
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        achou = False
        for lugar in lugares(page):
            try:
                for ok in visiveis(sel.botoes_ok(lugar))[:1]:
                    try:
                        caixa = ok.locator("xpath=ancestor::*[@role='dialog' or contains(@class,'modal')][1]")
                        textos.append(" ".join(caixa.inner_text(timeout=2000).split()))
                    except Exception:  # noqa: BLE001
                        pass
                    ok.click(timeout=5000)
                    achou = True
                    fim = time.monotonic() + segundos     # pode vir outro modal logo depois
                    time.sleep(0.3)
            except Exception:  # noqa: BLE001  (quadro recarregando)
                pass
        if not achou:
            time.sleep(0.25)
    return textos
