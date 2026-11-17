"""Todos os seletores e textos do portal da Amil (vendasmil). Tudo marcado VALIDAR até o ensaio no portal real.

Fonte: codegen/amil_mapa_video.md e os quadros do vídeo. O portal é uma página só (SPA): sem iframes, no vídeo.
Prefira papel + nome acessível (como a tela mostra) a classes CSS. O robô NUNCA clica em "Criar Proposta", "Enviar por
E-mail", "+ Incluir Plano Médico" nem em nada das etapas Proposta e Implantada: não há seletor para eles aqui.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page

from nucleo.texto import rx

# ---- rotas (pelo caminho da URL) ----
ROTA_LOGIN = "/login"
ROTA_OPORTUNIDADE_NOVA = "/oportunidades-pme/cadastro"    # quadro 05: /oportunidades-pme/cadastro?id=<rascunho>
ROTA_OPORTUNIDADE = "/oportunidades/"                      # quadro 09: /oportunidades/<id>?origem=cadastro-pme
ROTA_COTACAO = "/cotacoes/"                                # quadro 10: /cotacoes/<id> (Vínculo, Planos e Revisar)


def caminho(page: Page) -> str:
    try:
        return urlparse(page.url).path.lower()
    except Exception:  # noqa: BLE001
        return ""


# ---- textos ----
TEXTO_CODIGO_ENVIADO = rx("Código de verificação enviado")             # quadro 01
TEXTO_MENU_OPORTUNIDADE_PME = rx("Criar Oportunidade PME")                    # quadro 04 (menu lateral): sessão aberta
TEXTO_RECUSA_LOGIN = re.compile(r"(usu[aá]rio|e-?mail|senha|credenciais?).{0,60}(inv[aá]lid|incorret|n[aã]o confere)"
                                r"|(inv[aá]lid|incorret).{0,40}(usu[aá]rio|e-?mail|senha|credenciais?)", re.I)
TEXTO_CODIGO_RECUSADO = re.compile(r"c[oó]digo.{0,40}(inv[aá]lid|incorret|expirou|expirado)", re.I)
TEXTO_CAPTCHA = re.compile(r"n[aã]o sou (um )?rob[oô]|captcha", re.I)
TEXTO_TROCA_SENHA = re.compile(r"(trocar|redefinir|alterar|atualizar) (a )?senha|senha expirou", re.I)
TEXTO_CONSULTANDO_CNPJ = rx("Consultando CNPJ")                        # quadro 06
TEXTO_CARREGANDO = re.compile(r"Carregando|Verificando (CNAE|corretora|cobertura)|Gerando PDF", re.I)
TEXTO_COLIGACAO = rx("Haverá Coligação")
TEXTO_PDF_GERADO = rx("PDF Gerado")                                    # quadro 21 (aviso)
TEXTO_CONCLUIDA = re.compile(r"Cota[cç][aã]o conclu[ií]da com sucesso|Status da Cota[cç][aã]o\s*Conclu[ií]da", re.I)
TEXTO_BAIXAR_PDF = rx("Baixar PDF")
TEXTO_GERANDO_PDF = rx("Gerando PDF")
TEXTO_CRIAR_COTACAO = rx("Criar Cotação")
TEXTO_CONTINUAR = rx("Continuar")
TEXTO_CONCLUIR_OPORTUNIDADE = rx("Concluir Oportunidade")
TEXTO_CONCLUIR_COTACAO = rx("Concluir Cotação")                        # PONTO SEM VOLTA (gera o PDF e fecha a cotação)
TEXTO_REVISAR = rx("Revisar Cotação")
TEXTO_VINCULO = rx("Vínculo de Vendas")
TEXTO_SELECIONAR_PLANOS = rx("Selecionar Planos")
TEXTO_COTACOES_DA_OPORTUNIDADE = rx("Cotações da Oportunidade")


# ---- login (a 1ª etapa não aparece no vídeo: VALIDAR com o mapa 01_login) ----
def login_campo_usuario(page: Page) -> Locator:
    return page.get_by_role("textbox", name=re.compile(r"e-?mail|usu[aá]rio|login|cpf", re.I)).or_(
        page.locator("input[type=email], input[autocomplete=username], input[name*=user i], input[name*=email i]"))


def login_campo_senha(page: Page) -> Locator:
    return page.locator("input[type=password]")


def login_botao_entrar(page: Page) -> Locator:
    # "Iniciar Sessão" é o botão do vendasmil real (print do corretor, 12/11); os outros cobrem a 1ª etapa em duas páginas
    return page.get_by_role("button", name=re.compile(
        r"^\s*(iniciar sess[aã]o|entrar|acessar|continuar|login|avan[cç]ar)\s*$", re.I))


def campo_codigo(page: Page) -> Locator:                               # quadro 01: placeholder 00000000
    return page.get_by_placeholder("00000000").or_(page.get_by_label(rx("Código de verificação")))


def botao_verificar_codigo(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Verificar código"))


# ---- menu e oportunidade ----
def menu_criar_oportunidade_pme(page: Page) -> Locator:               # quadro 04
    return page.get_by_role("link", name=TEXTO_MENU_OPORTUNIDADE_PME).or_(page.get_by_role("button", name=TEXTO_MENU_OPORTUNIDADE_PME)) \
        .or_(page.get_by_text(TEXTO_MENU_OPORTUNIDADE_PME))


def coligacao_radio(page: Page, sim: bool) -> Locator:                # quadro 05: "Haverá Coligação?" Sim / Não (o 1º grupo)
    return page.get_by_role("radio", name=rx("Sim" if sim else "Não", exato=True)).first


def campo_cnpj(page: Page) -> Locator:
    return page.get_by_placeholder("00.000.000/0000-00")


def campo_razao_social(page: Page) -> Locator:
    # o rótulo do portal não está ligado ao input (mapa 02_ERRO_oportunidade, 12/11): o campo se acha pelo name do HTML
    return page.locator("input[name=razaoSocial]").or_(page.get_by_label(rx("Razão Social")))


def campo_nome_fantasia(page: Page) -> Locator:
    return page.locator("input[name=nomeEmpresa]").or_(page.get_by_label(rx("Nome Fantasia")))


def botao_concluir_oportunidade(page: Page) -> Locator:
    return page.get_by_role("button", name=TEXTO_CONCLUIR_OPORTUNIDADE)


def botao_criar_cotacao(page: Page) -> Locator:                        # quadro 09/23: um no painel e outro na lista
    return page.get_by_role("button", name=TEXTO_CRIAR_COTACAO)


def linha_da_cotacao(page: Page, cot: str) -> Locator:                 # quadro 23: ID, valor, vidas, status, olho
    return page.locator("tr, [role=row]").filter(has_text=cot)


def botao_ver_cotacao(linha: Locator) -> Locator:                      # o ícone de olho (Ações)
    return linha.get_by_role("button").or_(linha.get_by_role("link")).or_(linha.locator("svg, img, i")).first


# ---- vínculo de vendas (quadros 10 e 11) ----
def combo_corretor(page: Page) -> Locator:
    return page.get_by_role("combobox", name=rx("Nome do Corretor")).or_(page.get_by_text(rx("Selecione um corretor")))


def corretor_ja_escolhido(page: Page, nome: str) -> Locator:
    """O campo do corretor já preenchido é um botão com o nome e um "×" (aria de 12/11: button "EDLAINE ABREU SOARES ×");
    só conta o botão dentro do conteúdo principal e com o nome pedido."""
    return page.locator("main button").filter(has_text=rx(nome))


def busca_corretor(page: Page) -> Locator:
    return page.get_by_placeholder(re.compile(r"Digite nome ou c[oó]digo do corretor", re.I))


def opcoes_da_lista(page: Page) -> Locator:
    return page.get_by_role("option")


def combo_supervisor(page: Page) -> Locator:
    return page.get_by_role("combobox", name=rx("Nome do Supervisor"))


def botao_anterior(page: Page) -> Locator:                    # "← Anterior" no alto da Criar Cotação (print do corretor, 12/11)
    return page.get_by_role("button", name=re.compile(r"^\s*\W*\s*anterior\s*$", re.I)).or_(
        page.get_by_text(re.compile(r"^\s*\W?\s*Anterior\s*$", re.I)))


def botao_continuar(page: Page) -> Locator:
    return page.get_by_role("button", name=TEXTO_CONTINUAR)


# ---- selecionar planos (quadros 12 a 16) ----
def select_plano(page: Page) -> Locator:
    """O <select> "Plano:" (quadro 13: lista nativa do navegador)."""
    return page.get_by_label(re.compile(r"^\s*Plano\s*:?\s*$", re.I)).or_(
        page.locator("select").filter(has=page.locator("option", has_text=re.compile(r"^\s*Selecione", re.I))).first)


def grade(page: Page) -> Locator:
    """A grade das 10 faixas: linhas "Qtd. Vidas", "Valor por Vida" e "Subtotal"."""
    return page.locator("table").filter(has_text=rx("Qtd. Vidas")).filter(has_text=rx("Valor por Vida")).last


def linha_da_grade(page: Page, rotulo: str) -> Locator:
    return grade(page).locator("tr").filter(has_text=rx(rotulo)).first


def campos_de_vidas(page: Page) -> Locator:                            # os 10 campos "Qtd. Vidas"
    return linha_da_grade(page, "Qtd. Vidas").locator("input")


def celulas_da_linha(page: Page, rotulo: str) -> Locator:
    return linha_da_grade(page, rotulo).locator("td, th")


def checkbox_dental(page: Page) -> Locator:                            # quadro 16: "Aderir" ✓ DENTAL BRONZE PJ PROMO
    return page.locator("tr, [role=row]").filter(has_text=re.compile(r"DENTAL", re.I)).get_by_role("checkbox").first


TEXTO_ADITIVO = rx("AMIL RESGATE SAÚDE I")


# ---- revisar e concluir (quadros 17 a 22) ----
def botao_concluir_cotacao(page: Page) -> Locator:
    return page.get_by_role("button", name=TEXTO_CONCLUIR_COTACAO)


def botao_baixar_pdf(page: Page) -> Locator:
    return page.get_by_role("button", name=TEXTO_BAIXAR_PDF)


def link_da_oportunidade(page: Page, opp: str) -> Locator:             # painel da direita: "OPP-5147302" (link)
    return page.get_by_role("link", name=re.compile(re.escape(opp), re.I))


# ---- sair (quadro 04: botão "Sair" no pé do menu lateral) ----
def botao_sair(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Sair", exato=True)).or_(page.get_by_text(rx("Sair", exato=True))).first
