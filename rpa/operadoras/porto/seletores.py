"""Todos os seletores e textos do portal da Porto. Tudo marcado VALIDAR até o ensaio no portal real.

Fonte: codegen/porto_mapa_video.md, Seções 2 a 6. O cotador fica num iframe. O robô NUNCA tem seletor
que clique em Elaborar proposta, Adicionar à Proposta, Remissão, Editar ou Duplicar orçamento.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import FrameLocator, Locator, Page

from nucleo.texto import rx

# ---- rotas ----
ROTA_LOGIN = "/login"
ROTA_SUSEP = "/susep"
ROTA_HOME = "/homepage"
ROTA_COTAR = "/cotar"


def caminho(lugar) -> str:
    try:
        return urlparse(lugar.url).path.lower()
    except Exception:  # noqa: BLE001
        return ""


def iframe_cotador(page: Page) -> FrameLocator:
    return page.frame_locator("iframe#cotador")


# ---- textos (VALIDAR) ----
TEXTO_RECUSA_LOGIN = re.compile(r"(cpf|senha|credenciais?).{0,60}(inv[aá]lid|incorret)"
                                r"|(inv[aá]lid|incorret).{0,40}(cpf|senha)", re.I)
# Só o desafio de verdade. O modal da Porto traz "O Recaptcha serve para a sua maior segurança" — isso não é desafio.
TEXTO_CAPTCHA = re.compile(r"n[aã]o sou (um )?rob[oô]|resolva o (re)?captcha|desafio (do |de )?(re)?captcha", re.I)
# Selo do Google no rodapé. Não confundir com o texto de ajuda «O Recaptcha serve para…».
TEXTO_PROTEGIDO_RECAPTCHA = re.compile(r"protegido pel[oa]s? reCAPTCHA", re.I)
# Clique automatizado no ENTRAR: o portal recusa sem ser senha errada.
TEXTO_BLOQUEIO_AUTOMACAO = re.compile(
    r"motivos de seguran[cç]a.{0,80}validar seu acesso|n[aã]o conseguimos validar seu acesso", re.I)
TEXTO_TROCA_SENHA = re.compile(r"(trocar|redefinir|alterar) (a )?senha|senha expirou", re.I)
TEXTO_CRIAR_NOVA = rx("Criar nova cotação")
TEXTO_DADOS_INICIAIS = rx("Dados iniciais")
TEXTO_PRODUTO_VIDAS = re.compile(r"Produto e vidas|Informe se esta empresa possui plano anterior", re.I)
TEXTO_COMISSAO = re.compile(r"Selecione uma das op[cç][oõ]es de comiss[aã]o|regras de agenciamento", re.I)
TEXTO_SELECIONAR_PLANO = rx("Selecionar o plano")
TEXTO_GERAR_ORCAMENTO = rx("Gerar orçamento")
TEXTO_ERRO_PDF = rx("Erro ao gerar PDF")
TEXTO_IMPRIMIR = rx("Imprimir cotação")
TEXTO_CALCULADA = re.compile(r"cota[cç][aã]o n[ºo°]?\s*\d+\s+foi calculada", re.I)
TEXTO_CEP_INVALIDO = rx("Insira um CEP válido")
TEXTO_FALTAM_VIDAS = re.compile(r"Quantidade de vidas.+(Faltam|Ultrapassou)", re.I)
TEXTO_BANNER_DUVIDAS = rx("Está com dúvidas sobre como utilizar o novo sistema de cotação")
TEXTO_EMITIR_SEM_MED = rx("Emitir Sem Medicamentos")
TEXTO_VISUALIZAR = rx("Visualizar")
TEXTO_PAGINA_PRINCIPAL = rx("Ir para página principal")


# ---- login (VALIDAR) ----
def login_campo_cpf(page: Page) -> Locator:
    """Modal «Acesse o Corretor Online»: #logonPrincipal (name=logon, title=logon).

    Não é #logonSenha (recuperar senha): esse tem title=CPF e o get_by_label ia preenchê-lo.
    """
    return page.locator(
        "#logonPrincipal, #cpf, input[name='cpf' i], "
        "input[data-gtm-name='cpf'][autocomplete='username']"
    )


def login_campo_senha(page: Page) -> Locator:
    return page.locator("input[type=password]")


def login_botao_entrar(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^\s*(entrar|acessar)\s*$", re.I))


# Primeira página pública (corretor.portoseguro.com.br/corretoronline): o login só abre depois deste clique.
_RX_BOTAO_CORRETOR = re.compile(r"acess[ae]r?\s+o\s+corretor\s+online", re.I)
_RX_RECUSAR_COOKIES = re.compile(
    r"recusar(\s+cookies)?|rejeitar(\s+cookies)?|não aceitar|continuar sem (aceitar|cookies)", re.I)
_RX_BLOQUEAR_LOCAL = re.compile(r"^(bloquear|agora não|não permitir)$", re.I)


def botao_acessar_corretor(lugar) -> Locator:
    """O portal real usa <button> no header e abre um modal; o simulador pode ser link."""
    return lugar.get_by_role("button", name=_RX_BOTAO_CORRETOR).or_(
        lugar.get_by_role("link", name=_RX_BOTAO_CORRETOR))


def botao_recusar_cookies(lugar) -> Locator:
    return lugar.get_by_role("button", name=_RX_RECUSAR_COOKIES)


def botao_bloquear_localizacao(lugar) -> Locator:
    return lugar.get_by_role("button", name=_RX_BLOQUEAR_LOCAL)


def captcha_desafio(page: Page) -> Locator:
    """Desafio visível («Não sou um robô»). Sem iframe: is_visible no reCAPTCHA trava o Playwright."""
    return page.get_by_text(TEXTO_CAPTCHA)


def login_recaptcha_protege(page: Page) -> bool:
    """Selo/iframe do reCAPTCHA (inclusive invisível). Só count(): is_visible no iframe trava."""
    try:
        if page.locator(
            "iframe[src*='recaptcha' i], iframe[title*='reCAPTCHA' i], .grecaptcha-badge"
        ).count() > 0:
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return page.get_by_text(TEXTO_PROTEGIDO_RECAPTCHA).count() > 0
    except Exception:  # noqa: BLE001
        return False


TEXTO_ACESSE_CORRETOR = re.compile(r"Acesse o Corretor Online", re.I)
_RX_PLACEHOLDER_SUSEP = re.compile(r"^selecione", re.I)


class SusepNaoEncontrada(ValueError):
    """O código guardado não está na lista visível. `rotulos` são os textos das opções (para mascarar)."""

    def __init__(self, rotulos: list[str]):
        self.rotulos = [r for r in rotulos if r]
        super().__init__("susep_nao_encontrada")


def normalizar_susep(texto: str) -> str:
    """Ignora maiúsculas, espaços e o sufixo ' (P)'. 'aaaaaa (P)' → 'AAAAAA'."""
    bruto = re.sub(r"\s+", " ", (texto or "").strip())
    bruto = re.sub(r"\s*\(\s*P\s*\)\s*$", "", bruto, flags=re.I)
    return re.split(r"[\s(/]", bruto.upper(), 1)[0]


def mascarar_susep(texto: str) -> str:
    """Primeiros e últimos caracteres do código; o sufixo (P) só indica o tipo da opção."""
    bruto = (texto or "").strip()
    codigo = normalizar_susep(bruto)
    if not codigo:
        return ""
    if len(codigo) <= 2:
        masc = "*" * len(codigo)
    elif len(codigo) <= 4:
        masc = codigo[0] + ("*" * (len(codigo) - 2)) + codigo[-1]
    else:
        masc = codigo[:2] + ("*" * (len(codigo) - 4)) + codigo[-2:]
    if re.search(r"\(\s*P\s*\)", bruto, re.I):
        return f"{masc} (P)"
    return masc


def mensagem_susep_ausente(rotulos: list[str]) -> str:
    visiveis = [mascarar_susep(r) for r in rotulos if normalizar_susep(r)]
    lista = ", ".join(visiveis) if visiveis else "(nenhuma opção visível)"
    return (
        "O código SUSEP guardado no robô não está na lista do portal. "
        f"As opções disponíveis são: {lista}. "
        "O campo SUSEP do robô precisa ser um deles."
    )


def susep_select(page: Page) -> Locator:
    return page.locator("select#susep, select[name*=susep i], select[id*=susep i]")


def susep_caixa(page: Page) -> Locator:
    return page.get_by_role("combobox", name=re.compile(r"susep", re.I)).or_(
        page.get_by_label(re.compile(r"susep", re.I))).or_(
        page.locator("#susep-caixa, [aria-label='SUSEP' i]")).or_(
        susep_select(page))


def susep_opcao(page: Page, codigo: str) -> Locator:
    alvo = normalizar_susep(codigo)
    rx = re.compile(rf"\b{re.escape(alvo)}\b", re.I)
    return (page.get_by_role("option", name=rx).or_(
        page.locator(f"[data-susep='{alvo}' i]")).or_(
        page.locator("#susep-lista [role=option], #susep-lista li")))


def susep_botao_seguir(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^\s*(continuar|confirmar|entrar|ok)\s*$", re.I))


def _select_nativo_visivel(page: Page) -> Locator | None:
    loc = susep_select(page)
    try:
        if loc.count() and loc.first.is_visible():
            return loc.first
    except Exception:  # noqa: BLE001
        return None
    return None


def _pares_do_select(loc: Locator) -> list[dict]:
    try:
        pares = loc.evaluate(
            "el => [...el.options].map(o => ({value: (o.value||'').trim(), "
            "label: (o.textContent||'').trim()}))"
        )
        return pares or []
    except Exception:  # noqa: BLE001
        return []


def _opcoes_reais(pares: list[dict]) -> list[dict]:
    reais = []
    for p in pares:
        rotulo = (p.get("label") or "").strip()
        valor = (p.get("value") or "").strip()
        if not rotulo and not valor:
            continue
        if _RX_PLACEHOLDER_SUSEP.match(rotulo):
            continue
        reais.append({"value": valor, "label": rotulo or valor})
    return reais


def listar_rotulos_susep(page: Page) -> list[str]:
    nativo = _select_nativo_visivel(page)
    if nativo is not None:
        return [p["label"] for p in _opcoes_reais(_pares_do_select(nativo))]
    try:
        return page.evaluate(
            """() => [...document.querySelectorAll('[role=option], [data-susep], #susep-lista li')]
                .map(e => (e.getAttribute('data-susep') || e.textContent || '').trim())
                .filter(t => t && !/^selecione/i.test(t))"""
        ) or []
    except Exception:  # noqa: BLE001
        return []


def _esperar_opcoes_select(page: Page, timeout_ms: int) -> None:
    page.wait_for_function(
        """() => {
            const s = document.querySelector('select#susep, select[name*=susep i], select[id*=susep i]');
            return !!(s && [...s.options].some(o => (o.value || '').trim()));
        }""",
        timeout=timeout_ms,
    )


def _esperar_opcoes_menu(page: Page, timeout_ms: int) -> None:
    page.wait_for_function(
        """() => document.querySelectorAll('[role=option], [data-susep], #susep-lista li').length > 0""",
        timeout=timeout_ms,
    )


def _escolhe_no_select(loc: Locator, codigo: str, rotulos: list[str]) -> None:
    reais = _opcoes_reais(_pares_do_select(loc))
    if len(reais) == 1:
        loc.select_option(value=reais[0]["value"], timeout=5000)
        return
    for p in reais:
        if normalizar_susep(p["value"]) == codigo or normalizar_susep(p["label"]) == codigo:
            loc.select_option(value=p["value"], timeout=5000)
            return
    raise SusepNaoEncontrada(rotulos)


def _escolhe_no_menu(page: Page, codigo: str, rotulos: list[str]) -> None:
    itens = page.locator("[role=option], [data-susep], #susep-lista li")
    n = itens.count()
    if n == 1:
        itens.first.click(timeout=5000)
        return
    for i in range(n):
        item = itens.nth(i)
        try:
            data = (item.get_attribute("data-susep") or "").strip()
            texto = (item.inner_text(timeout=1000) or "").strip()
        except Exception:  # noqa: BLE001
            continue
        if normalizar_susep(data) == codigo or normalizar_susep(texto) == codigo:
            item.click(timeout=5000)
            return
    raise SusepNaoEncontrada(rotulos)


def escolher_susep(page: Page, codigo: str, timeout_ms: int = 15000) -> None:
    """Abre o dropdown, espera as opções e clica na que bate com o código.

    Nunca digita no campo. <select> nativo: select_option pelo valor/rótulo normalizado.
    Menu personalizado: clique para abrir e clique na opção. Uma única opção: usa ela.
    """
    alvo = normalizar_susep(codigo)
    if not alvo:
        raise SusepNaoEncontrada([])
    try:
        nativo = _select_nativo_visivel(page)
        if nativo is not None:
            _esperar_opcoes_select(page, timeout_ms)
            _escolhe_no_select(nativo, alvo, listar_rotulos_susep(page))
            return
        caixa = susep_caixa(page)
        if caixa.count():
            caixa.first.click(timeout=5000)
        _esperar_opcoes_menu(page, timeout_ms)
        _escolhe_no_menu(page, alvo, listar_rotulos_susep(page))
    except SusepNaoEncontrada:
        raise
    except Exception as e:  # noqa: BLE001
        if "closed" in str(e).lower() or "destroy" in str(e).lower():
            return
        raise SusepNaoEncontrada(listar_rotulos_susep(page)) from None


# ---- cotador (lugar = iframe ou página) ----
def botao_criar_nova(lugar) -> Locator:
    return lugar.get_by_role("button", name=TEXTO_CRIAR_NOVA).or_(lugar.get_by_text(TEXTO_CRIAR_NOVA))


def campo_cnpj(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"cnpj", re.I)).or_(lugar.locator("input[name*=cnpj i]"))


def botao_proximo(lugar) -> Locator:
    return lugar.get_by_role("button", name=re.compile(r"^\s*pr[oó]ximo\s*$", re.I))


def campo_total_vidas(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"vidas|quantidade total", re.I)).or_(
        lugar.locator("input[name*=vidas i], input#total-vidas"))


def select_plano_anterior(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"plano anterior", re.I)).or_(
        lugar.locator("select#plano-anterior, select[name*=anterior i]"))


def select_comissao(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"comiss[aã]o", re.I)).or_(lugar.locator("select#comissao"))


def checkbox_agenciamento(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"de acordo com as regras de agenciamento", re.I)).or_(
        lugar.locator("input#agenciamento, input[name*=agenc i]"))


def radio_acomodacao(lugar, texto: str) -> Locator:
    return lugar.get_by_role("radio", name=re.compile(rf"^{re.escape(texto)}$", re.I)).or_(
        lugar.get_by_text(re.compile(rf"^{re.escape(texto)}$", re.I)))


def radio_copart(lugar, texto: str) -> Locator:
    return lugar.get_by_role("radio", name=re.compile(rf"{re.escape(texto)}", re.I))


def botao_plano(lugar, nome: str) -> Locator:
    return lugar.locator(f'button[data-plano="{nome}"]')


def nomes_dos_planos(lugar) -> list[str]:
    try:
        return [n for n in lugar.locator("button[data-plano]").evaluate_all(
            "els => els.map(e => e.getAttribute('data-plano') || '')") if n]
    except Exception:  # noqa: BLE001
        return []


def botao_gerar_orcamento(lugar) -> Locator:
    """PONTO SEM VOLTA. Só chamar se o ensaio estiver desligado e a emissão liberada."""
    return lugar.get_by_role("button", name=TEXTO_GERAR_ORCAMENTO)


def botao_emitir_sem_medicamentos(lugar) -> Locator:
    return lugar.get_by_role("button", name=TEXTO_EMITIR_SEM_MED)


def botao_imprimir(lugar) -> Locator:
    return lugar.get_by_role("button", name=TEXTO_IMPRIMIR)


def botao_fechar_erro_pdf(lugar) -> Locator:
    return lugar.get_by_role("button", name=re.compile(r"^\s*fechar\s*$", re.I))


def botao_pagina_principal(lugar) -> Locator:
    return lugar.get_by_role("button", name=TEXTO_PAGINA_PRINCIPAL).or_(
        lugar.get_by_text(TEXTO_PAGINA_PRINCIPAL))


def busca_lista(lugar) -> Locator:
    return lugar.get_by_label(re.compile(r"buscar|cnpj|n[úu]mero", re.I)).or_(
        lugar.locator("input#busca-cotacao"))


def botao_visualizar(lugar) -> Locator:
    return lugar.get_by_role("button", name=TEXTO_VISUALIZAR)


def botao_sair(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^\s*sair\s*$", re.I))


def fechar_banner(lugar) -> Locator:
    return lugar.get_by_role("button", name=re.compile(r"fechar|x", re.I)).filter(
        has=lugar.get_by_text(TEXTO_BANNER_DUVIDAS))
