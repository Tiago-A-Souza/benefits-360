"""TODOS os seletores do robô da Bradesco ficam aqui.

Escritos a partir do vídeo do corretor (codegen/bradesco_mapa_video.md) e do simulador; todos marcados VALIDAR
até a calibragem no portal real (ensaio com "Guardar print de cada tela").

Regras (as mesmas da SulAmérica):
- prefira papel + nome visível e textos fixos com rx() (o portal mistura palavras com e sem acento);
- botões de escolha (Compulsória/Opcional, Sim/Não...) são achados pelo rótulo do campo e depois pelo nome;
- nada posicional (div[3]/span[2]);
- as páginas antigas (cálculo e "Alterar Cotação", EEEM-EmissaoExpressa) ficam dentro de um iframe: o robô procura
  o quadro que tem o texto da tela (telas.quadro_com), e as funções aqui recebem a página OU o quadro.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Locator

from nucleo.texto import rx


def caminho(page) -> str:
    try:
        return urlparse(page.url).path.lower()
    except Exception:  # noqa: BLE001
        return ""


# ======================= login (Portal de Negócios e nidp) =======================
# 1ª etapa (vídeo [01]): "CPF/CNPJ" + Continuar. 2ª etapa (login.bradescoseguros.com.br/nidp): senha. VALIDAR as duas.
ROTA_LOGIN = "/pnegocios2/wps/portal/portaldenegociosnovo"
ROTA_NIDP = "/nidp/"


# O Playwright não aceita "/" dentro da regex do nome: "CPF/CNPJ" vira cpf, qualquer separador, cnpj.
RX_CPF_CNPJ = re.compile(r"cpf\W{0,3}(ou\s+)?cnpj", re.I)


def login_campo_documento(lugar) -> Locator:           # OK no portal 07/11
    # Portal real 07/11: <input id="CpfCnpjTelaInicial" placeholder="Digite aqui seu CPF ou CNPJ">, sem <label>
    # (o "CPF/CNPJ" em cima é só texto). O nome acessível é o placeholder.
    return lugar.locator("#CpfCnpjTelaInicial").or_(lugar.get_by_role("textbox", name=RX_CPF_CNPJ))


def login_botao_continuar(lugar) -> Locator:           # OK no portal 07/11 (button#tag_Home_Login-Continuar)
    return lugar.locator("#tag_Home_Login-Continuar").or_(lugar.get_by_role("button", name=rx("Continuar", exato=True)))


def botao_rejeitar_cookies(lugar) -> Locator:          # OK no portal 07/11 (banner de cookies na 1ª tela)
    return lugar.locator("#adopt-reject-all-button").or_(
        lugar.get_by_role("button", name=rx("Rejeitar cookies não necessários")))


def login_campo_documento_nidp(lugar) -> Locator:      # OK no portal 07/11: o CPF/CNPJ da página da senha (nidp)
    return lugar.locator("#input_cpf_cnpj")


def login_campo_senha(lugar) -> Locator:               # VALIDAR (a etapa da senha não aparece no vídeo)
    return lugar.locator("input[type=password i]")


def login_botao_entrar(lugar) -> Locator:              # VALIDAR
    return lugar.get_by_role("button", name=re.compile(r"^\s*(entrar|acessar|continuar|login)\s*$", re.I))


def login_mensagem_erro(lugar) -> Locator:             # VALIDAR
    return lugar.get_by_role("alert")


def campo_codigo(lugar) -> Locator:                    # VALIDAR: código de verificação (token)
    return lugar.locator("input[autocomplete='one-time-code'], input[name*=codigo i], input[id*=codigo i], "
                         "input[name*=token i], input[id*=token i], input[name*=otp i]")


def botao_confirmar_codigo(lugar) -> Locator:          # VALIDAR
    return lugar.get_by_role("button", name=re.compile(r"^\s*(confirmar|validar|enviar|continuar|entrar)\s*$", re.I))


def captcha(lugar) -> Locator:                          # VALIDAR
    # Portal real 07/11: a 1ª tela tem um reCAPTCHA INVISÍVEL (só o selo "reCAPTCHA", iframe anchor com size=invisible).
    # Ele não pede nada: não é captcha para o robô parar. Captcha de verdade = a janela do desafio (bframe) visível
    # ou um reCAPTCHA de caixinha ("Não sou um robô").
    return lugar.locator("iframe[src*='recaptcha'][src*='bframe'], iframe[src*='recaptcha/api2/anchor']"
                         ":not([src*='size=invisible']), iframe[src*=hcaptcha], .g-recaptcha:not([data-size=invisible])")


TEXTO_LOGIN_RECUSADO = re.compile(
    r"(usu[aá]rio|senha|cpf|cnpj|dados|login).{0,40}(inv[aá]lid|incorret|n[aã]o confere|n[aã]o encontrad|"
    r"n[aã]o cadastrad)|bloquead", re.I)
TEXTO_TROCA_SENHA = re.compile(r"(trocar|alterar|redefinir|cadastr\w*)\s.{0,25}senha|senha.{0,25}(expirou|expirada|vencida)",
                               re.I)

# ======================= portal logado =======================
ROTA_AREA_LOGADA = "/arealogada/"
ROTA_COTADOR = "/saude/cotacoes/cotacao-spg"


def menu_saude(lugar) -> Locator:                       # OK no portal 07/11
    # O menu do topo é <a>SAÚDE</a> SEM href (Angular): não tem papel de link. Texto exato em maiúsculas (há outro
    # "Saúde" na página).
    return lugar.get_by_text(re.compile(r"^\s*SA[ÚU]DE\s*$"))


def menu_cotacoes(lugar) -> Locator:                    # vídeo [03] e portal 15/11: subnav do Painel Saúde
    # Texto no HTML: "Cotações" (CSS uppercase faz parecer COTAÇÕES). É um <div openmenuoptions>, não um <a>.
    # Sem o Acesso rápido favoritado, este é o caminho que o RPAV3 usava depois do atalho.
    item = lugar.locator("[openmenuoptions]").filter(has_text=re.compile(r"cota[cç][oõ]es", re.I))
    texto = lugar.get_by_text(re.compile(r"^\s*Cota[cç][oõ]es\s*$", re.I))
    return item.or_(texto)


def link_cotacao_spg(lugar) -> Locator:                 # OK no portal 07/11; 18/11 também pelo texto do submenu
    # Acesso rápido: o card "Cotação SPG" com o link "Conferir" (href .../saude/cotacoes/cotacao-spg).
    # Submenu COTAÇÕES: o próprio item "Cotação SPG" é o <a> (vídeo [03]).
    href = lugar.locator("a[href*='/cotacoes/cotacao-spg']")
    texto = lugar.get_by_role("link", name=re.compile(r"cota[cç][aã]o\s+spg", re.I))
    return href.or_(texto)


# Na página da Cotação SPG o portal abre a área de trabalho antiga num iframe (wwws.../EEEM-EmissaoExpressa,
# "Acompanhamento de Processos"). O cotador novo sai do menu Ações -> "Iniciar Nova Cotação SPG" (07/11).
LINK_NOVA_COTACAO_SPG = "a[href*='iniciarNovaCotacao']"
TEXTO_ERRO_403 = rx("AuthorizationFailed")     # 07/11: a Cotação SPG aberta direto pelo endereço


def aviso_do_portal(lugar) -> Locator:
    """Modal de campanha ("Seguros Friday") que está na frente da tela. O locator_handler só pode
    ver o visível: um `.modal-aviso` escondido no DOM fazia o Playwright reentrar no handler."""
    aberto = lugar.locator("div.modal.pn-modal.in[role=dialog], div.modal.pn-modal.show[role=dialog]")
    aviso = lugar.locator("div.modal.pn-modal.modal-aviso").filter(visible=True)
    return aberto.or_(aviso)


def aviso_do_portal_fechar(lugar) -> Locator:           # portal 07/11 e 18/11: close / btn-close / ícone fechar
    return aviso_do_portal(lugar).locator(
        "button.close, button.btn-close, button[aria-label='Close' i], button[aria-label='Fechar' i], "
        ".icon-nav-fechar")


def menu_usuario(lugar) -> Locator:                     # OK no portal 07/11: o nome da corretora no topo
    return lugar.locator("bspn-user-menu .bspn-user-menu_title").or_(
        lugar.get_by_role("button", name=rx("Menu do usuário")))


def link_sair(lugar) -> Locator:                        # OK no portal 07/11: <p>Sair</p> no menu do usuário
    return lugar.locator("bspn-user-menu p").filter(has_text=re.compile(r"^\s*Sair\s*$")).or_(
        lugar.get_by_role("link", name=re.compile(r"^\s*(sair|logout)\s*$", re.I)))


TEXTO_LOGADO = rx("NEWPORT CONSULTORIA")               # o topo do portal logado (vídeo [02])

# ======================= cotador novo (SPG) =======================
TITULOS = {   # o que diz que a tela está pronta (VALIDAR cada um)
    "inicio": rx("Cotador de planos SPG"),
    "empresa": rx("Qual o CNPJ ou CAEPF da empresa contratante"),
    "grupos": rx("Selecione a categoria funcional do grupo"),
    "regiao": rx("Região Indicada"),
    "personalizar": rx("Você pode personalizar ainda mais"),
    "configuracao": rx("Configurações de Planos e Condições Comerciais"),
    "resultado": rx("Grupo 1 - Saúde"),
    "complementares": rx("Dados complementares"),
}


def botao(lugar, nome: str) -> Locator:
    """Botão pelo nome (sem acento, maiúsculas, com ou sem "›" no fim)."""
    return lugar.get_by_role("button", name=re.compile(rf"^\s*{rx(nome).pattern}\s*[›>]?\s*$", re.I))


def botao_produto_saude(lugar) -> Locator:              # OK no portal 07/11: um card, não um <button>
    return botao(lugar, "Saúde e conjugado").or_(lugar.get_by_text(rx("Saúde e conjugado", exato=True)))


def campo_cnpj(lugar) -> Locator:                       # VALIDAR (vídeo [05]: campo ao lado de "Consultar")
    return lugar.get_by_role("textbox", name=rx("CNPJ"))


def caixa_razao_social(lugar) -> Locator:               # VALIDAR: a razão social aparece numa caixa depois de Consultar
    return lugar.locator(".razao, [class*=razao i], [class*=empresa i]")


def campo_faixa(lugar, rotulo: str) -> Locator:         # OK no portal 07/11: "19 a 23" ... "54 a 58"
    # div.input-vidas-content com <label>19 a 23</label> (sem "for") e <input type="number"> (sem nome acessível)
    rotulo_rx = re.compile(rf"^\s*{re.escape(rotulo)}\s*$")
    return lugar.locator("div.input-vidas-content").filter(
        has=lugar.locator("label").filter(has_text=rotulo_rx)).locator("input").or_(
        lugar.get_by_role("textbox", name=rx(rotulo, exato=True)))


def botao_abrir_faixa(lugar, rotulo: str) -> Locator:   # OK no portal 07/11: <a class="btn-59mais"> com o "+"
    rotulo_rx = re.compile(rf"^\s*{re.escape(rotulo)}\s*$")
    return lugar.locator("a.btn-59mais").filter(
        has=lugar.locator(".btn-59mais__label").filter(has_text=rotulo_rx)).or_(
        lugar.get_by_role("button", name=re.compile(rf"(informar|adicionar).*{rx(rotulo).pattern}", re.I)))


TITULO_IDADES = {"0 - 18": rx("Indique as pessoas entre 00 a 18 anos"),       # VALIDAR
                 "59+": rx("Indique as pessoas com 59 anos ou mais")}         # VALIDAR (não aparece no vídeo)
LINK_MAIS_PESSOAS = rx("adicionar mais pessoas")
# Quantidade de cada idade: portal real 07/11 input[formcontrolname=vidas]; simulador: textbox "Quantidade"
CAMPO_QTD_IDADE = "input[formcontrolname=vidas], input[aria-label=Quantidade]"
# Opções de uma lista aberta: ng-select do portal real (div.ng-option) ou role=option (simulador)
OPCOES_LISTA = ".ng-dropdown-panel .ng-option:not(.ng-option-disabled), [role=option]"
TEXTO_PESSOAS_TOTAL = rx("Pessoas no total")
TEXTO_MENOR_DE_1 = rx("Menor de 1 ano")

# rótulos das faixas no cotador novo, pela ordem do núcleo (nucleo.modelo.ROTULOS)
FAIXAS_NOVO = {"0 - 18": "00 a 18", "19 - 23": "19 a 23", "24 - 28": "24 a 28", "29 - 33": "29 a 33",
               "34 - 38": "34 a 38", "39 - 43": "39 a 43", "44 - 48": "44 a 48", "49 - 53": "49 a 53",
               "54 - 58": "54 a 58", "59+": "59 ou mais"}
# rótulos nas páginas antigas (tabela do cálculo e Alterar Cotação)
FAIXAS_ANTIGO = {"0 - 18": "Até 18 anos", "19 - 23": "19 a 23", "24 - 28": "24 a 28", "29 - 33": "29 a 33",
                 "34 - 38": "34 a 38", "39 - 43": "39 a 43", "44 - 48": "44 a 48", "49 - 53": "49 a 53",
                 "54 - 58": "54 a 58", "59+": "59 adiante"}

# Configurações de Planos e Condições Comerciais (vídeo [10][11][12]): rótulos dos campos, VALIDAR
ROTULO_ADESAO = "Modalidade de Adesão"
ROTULO_COBERTURA = "Cobertura"
ROTULO_PAGAMENTO = "Modalidade de Pagamento"
ROTULO_TITULARES = "Possui mais de 1 titular"
ROTULO_FOLHA = "Desconto - Folha de Pagamento Bradesco"
ROTULO_COMISSAO = "Desconto de comissionamento"
ROTULO_SUCURSAL = "Número da Sucursal"
ROTULO_CORRETOR = "Código do Corretor"
ROTULO_ACOMODACAO = "Acomodação"
ROTULO_COPART = "Coparticipação"
ROTULO_CATEGORIA = "Selecione a categoria funcional do grupo"


def aba(lugar, nome: str) -> Locator:                   # OK no portal 07/11: tab "Contrato icone", tab "Grupo 1"
    comeca = re.compile(rf"^\s*{rx(nome).pattern}(\s*icone)?\s*$", re.I)
    return lugar.get_by_role("tab", name=comeca).or_(lugar.get_by_role("button", name=rx(nome, exato=True)))


def combobox(lugar, rotulo: str) -> Locator:            # VALIDAR: as listas "Selecione" do cotador novo
    return lugar.get_by_role("combobox", name=rx(rotulo))


def opcoes_abertas(lugar) -> Locator:
    return lugar.get_by_role("option")


# Resultado ("Recomendação de Planos", portal real 07/11)
# Card de saúde: div.card.planos-saude > label.label-custom-radio (papel radio, "Checked/Unchecked <plano> R$ x") >
# h3.planos-saude__titulo "Nacional Plus" + p.planos-saude__descricao "R$ 4.565,59". Reembolso nos Benefícios:
# "Reembolso Completo (4x tabela)". Dental: div.card.planos-dental (o Padrão Doc 1 já vem marcado, card-selected).
def cards_saude(lugar) -> Locator:                      # OK no portal 07/11
    return lugar.locator("div.card.planos-saude")


def cards_dental(lugar) -> Locator:                     # OK no portal 07/11
    return lugar.locator("div.card.planos-dental")


def titulo_do_card(card) -> Locator:                    # OK no portal 07/11: nome e preço (h3 com o <p> do preço)
    return card.locator(".planos-saude__titulo, .planos-dental__titulo")


def radio_do_card(card) -> Locator:                     # OK no portal 07/11: o label (papel radio) seleciona o card
    return card.locator("label").first


def botao_valores_faixa(card) -> Locator:               # VALIDAR: "Valores por faixa etária" + botão "Ações"
    # o bloco mais interno com o texto e um botão (o filtro "has" relativo ao card não funciona: usa :has() do CSS)
    return card.locator("div:has(button)").filter(has_text=rx("Valores por faixa etária")).last.locator("button")


def setas_do_carrossel(lugar, titulo: str) -> Locator:  # OK no portal 07/11: "Arrow right" e "Arrow left"
    # Os dois botões ficam no cabeçalho do carrossel ("Grupo 1 - Saúde:"); a direção de cada um não importa: o robô
    # tenta os dois.
    cabecalho = lugar.locator("div").filter(has=lugar.get_by_text(rx(titulo))).filter(
        has=lugar.locator("button img[alt^='Arrow']")).last
    return cabecalho.locator("button")


TITULO_CARROSSEL_SAUDE = "Grupo 1 - Saúde"


RX_REEMBOLSO = re.compile(r"\((\d+)\s*x\s*tabela\)", re.I)        # "Reembolso Completo (4x tabela)"
TEXTO_INICIAR_COTACAO = "Iniciar cotação"
TEXTO_CALCULAR = "Calcular"
TEXTO_AVANCAR = "Avançar"
TEXTO_PULAR = "Pular"
TEXTO_CONSULTAR = "Consultar"

# Dados complementares (vídeo [16]-[20])
ROTULO_EMAIL_CORRETORA = "E-mail da corretora"
ROTULO_CELULAR_CORRETORA = "Celular (opcional)"
ROTULO_ANGARIACAO = "Angariação"
ROTULO_CORRETAGEM = "Corretagem"
ROTULO_CPF_INTERMEDIARIO = "CPF"
ROTULO_RAMO = "Ramo de atividade"
TEXTO_GERAR_PROCESSO = "Gerar processo"
ABAS_COMPLEMENTARES = ("Corretora", "Intermediário", "Transferência Bradesco", "Processo")


def campo_texto(lugar, rotulo: str) -> Locator:         # VALIDAR
    return lugar.get_by_role("textbox", name=rx(rotulo))


def nome_intermediario(lugar) -> Locator:               # OK no portal 07/11: o nome que o portal completa pelo CPF
    return lugar.locator("[formcontrolname=nomeResponsavel], #inome")


# Campos dos Dados complementares (portal real 07/11): sem nome acessível, pelo formcontrolname. As quatro abas ficam
# na página ao mesmo tempo (só a aberta aparece): o robô usa só os visíveis.
def campo_email_corretora(lugar) -> Locator:
    return lugar.locator("input[formcontrolname=email]").or_(lugar.get_by_role("textbox", name=rx("E-mail da corretora")))


def campo_celular_corretora(lugar) -> Locator:
    return lugar.locator("input[type=tel][formcontrolname=celular]").or_(
        lugar.get_by_role("textbox", name=rx("Celular (opcional)")))


def campo_cpf_intermediario(lugar) -> Locator:
    return lugar.locator("input[formcontrolname=cpfIntermediario]").or_(
        lugar.get_by_role("textbox", name=rx("CPF", exato=True)))


def campo_email_intermediario(lugar) -> Locator:
    return lugar.locator("input[formcontrolname=emailIntermediario]").or_(
        lugar.get_by_role("textbox", name=rx("E-mail (opcional)")))


def radio(lugar, nome: str) -> Locator:
    return lugar.get_by_role("radio", name=rx(nome, exato=True))


# ======================= páginas antigas (EEEM, dentro de iframe) =======================
TEXTO_CALCULO = rx("Cálculo de Seguro SPG")             # vídeo [21]
TEXTO_ALTERAR = rx("Dados da Cotação")                  # vídeo [24]
TEXTO_NUMERO_PROCESSO = rx("Número do Processo")
RX_NUMERO_PROCESSO = re.compile(r"N[uú]mero\s+do\s+Processo\s*:?\s*(\d{6,})", re.I)
RX_PROCESSO_MODAL = re.compile(r"Processo\s*#\s*(\d{6,})", re.I)   # vídeo [27]
# Portal real 10/11: a janela do cotador logo depois do Gerar processo: "Processo 16097787 gerado! Tipo de reembolso:
# Específico Você será redirecionado para as próximas etapas do Emissão Expressa SPG."
RX_PROCESSO_GERADO = re.compile(r"Processo\s*#?\s*(\d{6,})\s+gerado", re.I)
TEXTO_ALTERAR_COTACAO = "Alterar Cotação"


def campo_identificador_calculo(lugar) -> Locator:     # OK no portal 07/11: obrigatório para o Imprimir (até 60)
    # "Identifique o cálculo a ser armazenado *": sem ele o Imprimir responde "O identificador do cálculo deve ser
    # preenchido." numa caixa de OK.
    return lugar.locator("input[name='cotacao.calculo.identificador']").or_(
        lugar.get_by_role("textbox", name=rx("Identifique o cálculo")))


def caixa_alerta(lugar) -> Locator:                     # OK no portal 07/11: a caixa de aviso das páginas antigas
    return lugar.locator("#box-alertbox")
TEXTO_IMPRIMIR = "Imprimir"
TEXTO_FINALIZAR = rx("Finalizar Cálculo")              # o robô NUNCA clica (só confere que existe)


# Janelas informativas (40 dias, "Processo #N"...): o robô só fecha por um botão OK/Entendi/Fechar dentro de uma
# janela (nunca "Continuar", "Confirmar" ou outro). Portal real 07/11: depois do Gerar processo uma janela com OK
# cobria a tela e o robô não fechava (VALIDAR com o mapa "janela_ok").
RX_BOTAO_OK = re.compile(r"^\s*(ok|ok,?\s*entendi|entendi|fechar)\s*!?\s*$", re.I)
# Portal real 07/11: na página do cálculo, div#box-alertbox (sobre o fundo #box-overlayer) com button#box-button-ok
CONTAINERS_JANELA = ("#box-alertbox, .modal, [role=dialog], [role=alertdialog], .ui-dialog, .swal2-popup, .mat-dialog-container, "
                     ".mat-mdc-dialog-container, .cdk-overlay-pane, .popup, .alert, .modal-dialog")


def botoes_ok(lugar) -> Locator:
    janela = lugar.locator(CONTAINERS_JANELA)
    return lugar.locator("#box-button-ok").or_(janela.get_by_role("button", name=RX_BOTAO_OK)).or_(
        janela.locator("button, a, input[type=button], input[type=submit], [role=button]").filter(has_text=RX_BOTAO_OK))


# Portal real 10/11 (mapa 18_alterar_form_2): os selects do Alterar Cotação, pelo name. O rótulo é só uma célula da
# tabela e o mesmo texto ("Plano Saúde") também está numa tabela escondida (spg_minimizado) que vem antes.
NOMES_SELECT_ANTIGO = {"Plano Saúde": "rede.codigo", "Acomodação": "acomodacao.acmdEscolhidas",
                       "Coparticipação": "fatorModerador.codigo"}


def select_antigo(lugar, rotulo: str) -> Locator:       # OK no portal 10/11 (pelo name); o resto é para o simulador
    """O select do formulário antigo: pelo name do portal real; se não houver, pelo rótulo ligado ao campo
    (label for / aria-label); por último, o 1º select depois da célula VISÍVEL do rótulo."""
    nome = NOMES_SELECT_ANTIGO.get(rotulo)
    for candidato in ([lugar.locator(f"select[name='{nome}']")] if nome else []) + [lugar.get_by_label(rx(rotulo))]:
        try:
            if candidato.count():
                return candidato
        except Exception:  # noqa: BLE001  (quadro carregando)
            pass
    celula = re.compile(rx(rotulo).pattern.join([r"^\s*", r"\s*\*?\s*$"]), re.IGNORECASE)
    return lugar.get_by_text(celula).filter(visible=True).locator("xpath=following::select[1]")


ROTULO_PLANO_ANTIGO = "Plano Saúde"
ROTULO_ACOMODACAO_ANTIGO = "Acomodação"
ROTULO_COPART_ANTIGO = "Coparticipação"
