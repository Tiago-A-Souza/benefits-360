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
TEXTO_CAPTCHA = re.compile(r"n[aã]o sou (um )?rob[oô]|recaptcha|desafio", re.I)
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
    return page.get_by_label(re.compile(r"^cpf$", re.I)).or_(
        page.locator("input[name*=cpf i], input[id*=cpf i]"))


def login_campo_senha(page: Page) -> Locator:
    return page.locator("input[type=password]")


def login_botao_entrar(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^\s*(entrar|acessar)\s*$", re.I))


def captcha_desafio(page: Page) -> Locator:
    return page.get_by_text(TEXTO_CAPTCHA).or_(
        page.locator("iframe[src*='recaptcha'][src*='bframe'], iframe[src*='recaptcha/api2/anchor']"
                     ":not([src*='size=invisible'])"))


def susep_opcao(page: Page, codigo: str) -> Locator:
    return page.get_by_role("button", name=re.compile(rf"\b{re.escape(codigo)}\b", re.I)).or_(
        page.get_by_text(re.compile(rf"\b{re.escape(codigo)}\b", re.I)))


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
