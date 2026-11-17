"""TODOS os seletores do robô ficam aqui.

Na calibragem com o portal real, este é o arquivo a ajustar. Cada seletor foi
escrito a partir do vídeo do corretor (textos, placeholders, botões) e está
marcado com VALIDAR até ser conferido no site de verdade com `--mapear`.

Regras para quem ajustar:
- Prefira papel + nome visível (get_by_role) e textos fixos (get_by_text com rx()).
- Use rx() para textos: o portal mistura palavras com e sem acento.
- Textos que se repetem na página (ex.: "24 meses" aparece no filtro E em todos os
  cards) precisam ser buscados por papel (checkbox/radio), nunca só por texto.
- Evite caminhos posicionais (div[3]/span[2]).
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page

from nucleo.texto import rx


def rx_faixa(rotulo: str) -> re.Pattern:
    """'0 - 18' casa com '0 - 18', '0-18', '0 – 18'; '59+' casa com '59 +'."""
    if rotulo.endswith("+"):
        return re.compile(rf"^\s*{rotulo[:-1]}\s*\+\s*$")
    a, b = [x.strip() for x in rotulo.split("-")]
    return re.compile(rf"^\s*{a}\s*[-–]\s*{b}\s*$")


# ======================= Portal antigo (os11) =======================
# ---- login (o robô preenche com o login guardado na engrenagem; ver login.py) ----
# Portal real (mapa 03/11, OutSystems): um formulário só, sem iframe, campos já na página ao carregar.
# Os campos não têm <label>: o nome acessível vem do placeholder ("CPF", "E-mail", "Senha"). Sair do
# CPF, marcar "Ok, entendi!" e Entrar fazem cada um um POST AJAX para a própria LoginGeral.aspx (a
# página não recarrega).

def login_campo_cpf(page: Page) -> Locator:            # OK no portal 03/11 (placeholder "CPF")
    return page.get_by_role("textbox", name=rx("CPF", exato=True))


def login_campo_email(page: Page) -> Locator:          # OK no portal 03/11 (placeholder "E-mail")
    return page.get_by_role("textbox", name=rx("E-mail", exato=True))


def login_campo_senha(page: Page) -> Locator:          # OK no portal 03/11 (type=password, placeholder "Senha")
    return page.get_by_role("textbox", name=rx("Senha", exato=True))


def login_ok_entendi(page: Page) -> Locator:           # OK no portal 03/11
    # A caixa não tem nome acessível: "Ok, entendi!" é um <div class="aceite_texto"> logo depois dela.
    return page.get_by_text(rx("Ok, entendi!", exato=True)).locator(
        "xpath=preceding-sibling::input[@type='checkbox'][1]")


def login_botao_entrar(page: Page) -> Locator:         # OK no portal 03/11 (input submit "Entrar")
    return page.get_by_role("button", name=rx("Entrar", exato=True))


def login_mensagem_erro(page: Page) -> Locator:        # VALIDAR: mensagem do servidor (RichWidgets Feedback)
    return page.locator(".Feedback_Message_Error")


def login_validacao(page: Page) -> Locator:            # validação do próprio formulário (campo faltando)
    return page.locator(".ValidationMessage")


# Visto no portal 03/11 (.Feedback_Message_Error depois do Entrar): o CPF já está logado em outro lugar.
# Não é senha errada: o robô para e avisa, sem marcar o login como recusado.
TEXTO_ACESSO_ATIVO = rx("Já existe um acesso ativo")

# VALIDAR: as mensagens reais do portal. Na dúvida o robô trata como recusa (não tenta de novo).
TEXTO_LOGIN_RECUSADO = re.compile(
    r"(usu[aá]rio|senha|cpf|e-?mail|dados|login).{0,40}(inv[aá]lid|incorret|n[aã]o confere|n[aã]o encontrad)"
    r"|bloquead", re.I)
# No portal há um bloco escondido "REDEFINIR A SENHA" (wtCntExpiraSenha) que aparece quando a senha expira.
TEXTO_TROCA_SENHA = re.compile(
    r"(trocar|alterar|redefinir|cadastrar)\s.{0,25}senha|senha.{0,25}(expirou|expirada|vencida)", re.I)
# VALIDAR: bloco escondido no portal (wtCntSelEVEAAA) que pode aparecer depois do login.
TEXTO_SELECAO_CORRETORA = rx("Selecione sua Corretora ou EV")


def campo_codigo(page: Page) -> Locator:               # VALIDAR: código de verificação (SMS/e-mail)
    return page.locator("input[autocomplete='one-time-code' i]").or_(
        page.get_by_placeholder(re.compile(r"c[oó]digo|token", re.I)))


def botao_confirmar_codigo(page: Page) -> Locator:     # VALIDAR
    return page.get_by_role("button", name=re.compile(r"^\s*(confirmar|validar|enviar|entrar|continuar)\s*$", re.I))


def captcha(page: Page) -> Locator:                    # o robô para e avisa; nunca tenta resolver
    return page.locator("iframe[src*='recaptcha' i], iframe[src*='hcaptcha' i], iframe[src*='turnstile' i], "
                        "iframe[title*='captcha' i], img[src*='captcha' i], [id*='captcha' i], [class*='captcha' i]"
                        ).or_(page.get_by_text(rx("não sou um robô")))


TEXTO_TELA_MODULOS = rx("Selecione um módulo")         # visto no vídeo (00:12)
TEXTO_COOKIES = rx("ACEITO", exato=True)               # banner de cookies (00:00 e 01:15)
TEXTO_CARD_PME = rx("Cotação PME", exato=True)         # card "Cotação PME / 3 a 29 Vidas"
TEXTO_EMITIDA = rx("Cotação emitida com sucesso")      # 01:15
TEXTO_PROTOCOLO = rx("Protocolo Saúde")                # "Protocolo Saúde: nº 8601234"
TEXTO_BAIXAR = rx("Baixar cotação saúde", exato=True)  # botão laranja
TEXTO_COPIAR = rx("Copiar cotação", exato=True)
RX_COPIAR = rx("Copiar cotação")                       # VALIDAR: botão ou link, com ícone ao lado
TEXTO_MODAL_COPIAR = rx("Deseja copiar a cotação")     # modal "COPIAR COTAÇÃO"
TEXTO_SIM = rx("Sim", exato=True)


def modal_copiar(page: Page) -> Locator:
    """O dialog "Copiar Cotação" (mapa real 06/11), com o botão de fechar (X)."""
    return page.get_by_role("dialog", name=rx("Copiar cotação"))


def frame_modal_copiar(page: Page):
    """Mapa real 06/11: o modal é um dialog "Copiar Cotação" com um iframe (PopUpCotDuplicar.aspx?InIdCotacao=...)
    e é dentro dele que ficam "Deseja copiar a cotação?", NÃO e SIM."""
    return page.frame_locator("iframe[src*='PopUpCotDuplicar' i]")
TEXTO_VOLTAR_HOME = rx("Voltar para a home", exato=True)
# VALIDAR (05/11): nas 3 emissões reais o robô não achou "Voltar para a home" com o texto exato e ficou
# esperando. Aceita "Voltar para home", "Voltar para a home", "Voltar ao início", em botão, link ou texto.
RX_VOLTAR_HOME = re.compile(r"\bvoltar\s+(?:para\s+)?(?:ao\s+|a\s+|o\s+|[àá]\s+)?(?:home|in[ií]cio|p[aá]gina\s+inicial)\b", re.I)
TEXTO_NOVA_COTACAO = rx("Nova cotação", exato=True)
TEXTO_INICIAR_CONTRATACAO = rx("Iniciar contratação")  # o robô NUNCA clica aqui


# ======================= Cotador novo (SPA) =======================
# Cada tela tem rota própria; o robô decide a etapa pela URL.
ROTAS = [
    ("dados_empresa", "/dados-empresa"),
    ("cuidado_360", "/cuidado-cross"),
    ("congenere", "/congeneres"),
    ("vidas", "/vidas-saude"),
    ("idades", "/distribuicao-agravadas"),
    ("planos", "/precificacao-planos"),
    ("comparacao", "/comparacao-planos"),
    ("resumo", "/resumo-final"),
]
ROTA_EMITIDA = "simulador.aspx"
# Portal real 05/11: "Voltar para a Home" (tela da emissão) leva ao painel "ESTOU EM COTAÇÕES"
# (os11.../SaudeCotador/PainelCotacao.aspx): cartão "NOVA COTAÇÃO", contadores (em preenchimento,
# concluídas...), "VER TODAS AS COTAÇÕES", "SELECIONAR OUTRO MÓDULO" e o menu de 3 barras. VALIDAR o mapa.
ROTA_PAINEL = "painelcotacao.aspx"
TEXTO_PAINEL = rx("Estou em cotações")
# no painel, o cartão quebra em 2 linhas ("NOVA" / "COTAÇÃO"): o nome pode vir sem espaço entre as palavras
RX_NOVA_COTACAO = re.compile(r"\bnova\s*cota[cç][aã]o\b", re.I)
TEXTO_SELECIONAR_MODULO = rx("Selecionar outro módulo")


# ======================= Sair do portal (logout) =======================
# Mapa 01_login.html (05/11): no cabeçalho do portal antigo (VanillaTheme ... wtHeader ... wtWbbLoginInfo) há
# um menu lateral, aberto pelo ícone de 3 barras (a.menuLeft, id ...wtMenuLateral2), com o item
# "Sair do Cotador" (div.logout, id ...wtLogout, onclick OsAjax 'Click'). Antes do login o menu fica escondido.
# VALIDAR na tela de módulos logada (ela não vira mapa: tem a mesma URL do login).
TEXTO_SAIR_DO_PORTAL = rx("Sair do Cotador", exato=True)


def menu_do_portal(page: Page) -> Locator:
    return page.locator("a.menuLeft, [id$='wtMenuLateral2']")


def botao_sair_do_portal(page: Page) -> Locator:
    return page.locator("[id$='wtLogout'], div.logout").or_(page.get_by_text(TEXTO_SAIR_DO_PORTAL))


def _botao(page: Page, padrao: re.Pattern) -> Locator:
    """Botão, link ou texto com esse rótulo (o primeiro visível vale)."""
    return (page.get_by_role("button", name=padrao).or_(page.get_by_role("link", name=padrao))
            .or_(page.get_by_text(padrao)))


def botao_voltar_home(page: Page) -> Locator:
    return _botao(page, RX_VOLTAR_HOME)


def botao_nova_cotacao(page: Page) -> Locator:
    return _botao(page, TEXTO_NOVA_COTACAO)


def botao_copiar(page: Page) -> Locator:
    return _botao(page, RX_COPIAR)


def cartao_nova_cotacao(page: Page) -> Locator:
    return _botao(page, RX_NOVA_COTACAO)


def link_selecionar_modulo(page: Page) -> Locator:
    return _botao(page, TEXTO_SELECIONAR_MODULO)
ROTA_LOGIN = "logingeral.aspx"


def caminho(page_ou_url) -> str:
    """Só o caminho da URL, em minúsculas: a rota de uma tela nunca casa com um pedaço da consulta (?volta=...)."""
    url = page_ou_url if isinstance(page_ou_url, str) else page_ou_url.url
    return urlparse(url).path.lower()

TITULOS = {
    "dados_empresa": rx("Comece por aqui"),
    "cuidado_360": rx("Deseja adicionar o Cuidado 360"),
    "congenere": rx("De qual congênere"),
    "vidas": rx("Distribua as vidas da empresa"),
    "idades": rx("Especifique as idades"),
    "planos": rx("Planos disponíveis"),
    "comparacao": rx("Comparação de Planos"),
    "resumo": rx("Resumo da Simulação"),
    "emitida": TEXTO_EMITIDA,
}

TEXTO_ENVIADA = rx("Cotação enviada com sucesso")      # aparece SEM acento no portal
TEXTO_GERANDO = rx("Gerando proposta")


def skeletons(page: Page) -> Locator:                  # VALIDAR: classe real dos "esqueletos"
    return page.locator("[class*='skeleton' i], [class*='shimmer' i], [aria-busy='true']")


def botao_continuar(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Continuar", exato=True))


def botao_voltar(page: Page) -> Locator:               # VALIDAR: pode ser link
    return page.get_by_role("button", name=rx("Voltar", exato=True))


TEXTO_SAIR_COTACAO = rx("Sair da cotação", exato=True)

# Portal 04/11: "Sair da cotação" abre um modal (diálogo com fundo escuro que cobre a tela) com a pergunta
# abaixo e os botões "Cancelar", "Confirmar e sair" e "Close" (mapa 10_modal_sair): o robô clica no que confirma.
TEXTO_MODAL_SAIR = rx("Deseja realmente sair da cotação")
RX_CONFIRMA_SAIDA = re.compile(r"^\s*(sim|sair|confirmar|ok|sim,?\s*sair|confirmar e sair|sair da cota[cç][aã]o)\s*$", re.I)
RX_CANCELA = re.compile(r"cancelar|n[aã]o|voltar|fechar|close|continuar", re.I)


# Portal 04/11 (mapa 11_ERRO_comparacao): um tour "Guia de navegação" ("1 de 9", Pular/Próximo) abre por cima
# da tela e bloqueia o Continuar. O robô pula.
def guia_navegacao(page: Page) -> Locator:
    return page.get_by_role("dialog", name=rx("Guia de navegação"))


def botao_pular_guia(dialogo: Locator) -> Locator:
    return dialogo.get_by_role("button", name=rx("Pular", exato=True))


def modal_sair(page: Page) -> Locator:                  # VALIDAR
    return page.get_by_role("dialog").or_(page.get_by_role("alertdialog")).filter(has_text=TEXTO_MODAL_SAIR)

# ---- dados da empresa ----


def campo_cnpj(page: Page) -> Locator:
    return page.get_by_placeholder(rx("Digite o CNPJ"))


def msg_cnpj_valido(page: Page) -> Locator:
    return page.get_by_text(rx("CNPJ válido"))


def campo_vendedor(page: Page) -> Locator:             # VALIDAR: campo com "x" para limpar
    return page.get_by_role("combobox").first


def bloco_dados_empresa(page: Page) -> Locator:        # VALIDAR
    return page.get_by_text(rx("Dados da Empresa")).locator("xpath=following::*[1]")


# ---- Cuidado 360° ----


def radio(page: Page, nome: str) -> Locator:
    return page.get_by_role("radio", name=rx(nome, exato=True))


def botao_prosseguir(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Prosseguir", exato=True))


# ---- congênere ----


def campo_congenere(page: Page) -> Locator:
    return page.get_by_placeholder(rx("Digite para buscar"))


def opcao_congenere(page: Page, nome: str) -> Locator:  # VALIDAR: papel da lista de sugestões
    return page.get_by_role("option", name=rx(nome, exato=True))


def check_seguro_novo(page: Page) -> Locator:
    return page.get_by_role("checkbox", name=rx("Este é um seguro novo"))


def chip_congenere(page: Page, nome: str) -> Locator:  # VALIDAR: "NOTREDAME ×" dentro do campo
    return page.get_by_text(rx(nome, exato=True))


# ---- distribuição de vidas ----


def campo_faixa(page: Page, rotulo: str) -> Locator:   # VALIDAR: input logo depois do rótulo
    return page.get_by_text(rx_faixa(rotulo)).first.locator("xpath=following::input[1]")


def status_vidas(page: Page) -> Locator:               # "1/3 vidas (faltam 2)" / "3 vidas distribuídas"
    return page.get_by_text(re.compile(r"vidas?\s+distribu|faltam", re.I))


# ---- idades exatas ----


def campo_idade(page: Page) -> Locator:                # VALIDAR
    return page.get_by_text(rx("Idade", exato=True)).first.locator("xpath=following::input[1]")


def botao_adicionar_idade(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Adicionar idade"))


# ---- precificação / planos ----


def filtro_radio(page: Page, nome: str) -> Locator:
    return page.get_by_role("radio", name=rx(nome, exato=True))


def filtro_check(page: Page, nome: str) -> Locator:
    # Por papel: o texto "24 meses"/"Com coparticipação" também aparece em todos os cards.
    return page.get_by_role("checkbox", name=rx(nome, exato=True))


def botoes_cards(page: Page) -> Locator:
    return page.get_by_role("button", name=re.compile(r"^\s*(selecionar plano|plano selecionado)\s*$", re.I))


def card_do_botao(botao: Locator) -> Locator:
    # O card é o ancestral mais próximo do botão que contém o preço.
    return botao.locator("xpath=ancestor::*[contains(normalize-space(.), 'R$')][1]")


def botao_desmarcar_todos(page: Page) -> Locator:
    return page.get_by_role("button", name=rx("Desmarcar todos"))


def botao_pagina(page: Page, numero: int) -> Locator:  # VALIDAR: paginação "‹ 1 2 ›"
    return page.get_by_role("button", name=re.compile(rf"^\s*{numero}\s*$"))


def texto_sem_planos(page: Page) -> Locator:           # VALIDAR
    return page.get_by_text(re.compile(r"nenhum plano|0\s+op[cç][oõ]es", re.I))
