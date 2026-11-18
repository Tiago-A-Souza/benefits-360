"""Uma função por tela do cotador.

Cada função espera a tela carregar, confere o que já está preenchido (no modo
"Copiar cotação" quase tudo vem pronto), preenche só o que falta e sai da tela.
Conferências que falham param ANTES da emissão.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path

from nucleo.modelo import CHAVE_POR_ROTULO, ROTULOS, PlanoAlvo, ResultadoPlano
from nucleo.navegador import (ErroDados, ErroFluxo, ErroLogin, clicar_texto, conferir_parar,
                              esperar_sair_da_rota, esperar_visivel, ligar_parar, sem_parar, visiveis)
from nucleo.saidas import copiar_para_destino, nome_pdf_arquivo, nome_pdf_destino
from nucleo.texto import formatar_cnpj, norm, so_digitos

from . import extracao as ex
from .cartao import PlanoNaTela
from . import seletores as sel
from .login import entrar, painel_visivel, tela_modulos_visivel
from .pedido import Pedido
from .telas import aceitar_cookies, esperar_sem_skeleton, esperar_tela, fechar_guia


@dataclass
class Sessao:
    cfg: dict
    log: object
    contexto: object
    page: object
    estado: object
    resultados: object
    mapa: object
    ensaio: bool
    avisar: object = None          # callable(tipo, **dados) para a tela acompanhar; opcional
    parar: object = None           # callable() -> True quando o corretor pediu para parar; opcional
    pedir_codigo: object = None    # callable() -> código de verificação digitado na tela (ou None)
    # Protocolos que o corretor pediu na tela para emitir de novo ("Emitir de novo mesmo assim"). Cada um
    # vale uma vez: sai do conjunto quando o robô grava "emitindo" da nova emissão.
    reemitir: set = field(default_factory=set)

    def __post_init__(self) -> None:
        ligar_parar(self.pediu_parar)

    def aviso(self, tipo: str, **dados) -> None:
        if self.avisar:
            try:
                self.avisar(tipo, **dados)
            except Exception:  # noqa: BLE001  (a tela nunca pode derrubar o robô)
                pass

    def pediu_parar(self) -> bool:
        try:
            return bool(self.parar and self.parar())
        except Exception:  # noqa: BLE001
            return False

    def tol(self) -> Decimal:
        return Decimal(str(self.cfg["conferencias"]["tolerancia_reais"]))

    def aliquota(self) -> Decimal:
        return Decimal(str(self.cfg["conferencias"]["aliquota_iof"]))

    def t(self, nome: str) -> int:
        return int(self.cfg["execucao"][nome])


@dataclass
class Andamento:
    base: Pedido                        # o pedido como veio (a coparticipação pode ser "as_duas")
    alvos: list[PlanoAlvo]              # cotações a fazer nesta execução, em ordem (com "Com e sem", 2 por plano)
    resolver_por_criterio: bool = False
    indice: int = 0
    razao_social: str = ""
    catalogo: list[PlanoNaTela] = field(default_factory=list)
    precos_salvos: set = field(default_factory=set)   # coparticipações cujos preços já foram para a planilha
    copart_na_tela: str = ""            # coparticipação que o filtro da tela Planos mostra agora
    plano_tela: PlanoNaTela | None = None
    resultado: ResultadoPlano | None = None
    copia: bool = False
    terminou: bool = False
    aguardando_emissao: bool = False    # True só entre o clique de emitir e a tela de protocolo

    @property
    def alvo(self) -> PlanoAlvo | None:
        return self.alvos[self.indice] if self.indice < len(self.alvos) else None

    @property
    def pedido(self) -> Pedido:
        """O pedido da cotação em andamento. Com "Com e sem", a versão (com ou sem coparticipação) do plano
        atual: é ela que vale para os filtros, as conferências do card e do resumo, o nome do PDF e o registro."""
        alvo = self.alvo
        copart = (alvo.versao if alvo is not None else "") or self.base.versoes_copart[0]
        return self.base.na_versao(copart)


def com_versoes(pedido: Pedido, alvos: list[PlanoAlvo]) -> list[PlanoAlvo]:
    """Com "Com e sem", cada plano vira duas cotações, nesta ordem: plano 1 com, plano 1 sem, plano 2 com..."""
    versoes = pedido.versoes_copart
    if len(versoes) == 1:
        return list(alvos)
    return [replace(alvo, versao=c, versao_texto=f"{c} coparticipação") for alvo in alvos for c in versoes]


def versao_no_nome(a: Andamento) -> str:
    """O que vai no nome do PDF quando o pedido tem as duas versões: "COM COPARTICIPACAO" / "SEM COPARTICIPACAO"."""
    if len(a.base.versoes_copart) == 1:
        return ""
    return f"{a.pedido.coparticipacao.upper()} COPARTICIPACAO"


def _rota(etapa: str) -> str:
    return dict(sel.ROTAS)[etapa]


def _continuar(s: Sessao, etapa: str, esperar_saida: bool = True, timeout_ms: int | None = None,
               antes_do_clique=None) -> None:
    page = s.page
    botao = esperar_visivel(sel.botao_continuar(page), 15000, "botão Continuar", etapa)
    fim = time.monotonic() + 15
    while not botao.is_enabled():
        conferir_parar(etapa)
        if time.monotonic() > fim:
            s.mapa.registrar(page, f"{etapa}_continuar_desabilitado", forcar=True)
            raise ErroFluxo("o botão Continuar continua desabilitado (falta preencher algo?)", etapa)
        time.sleep(0.25)
    fechar_guia(page)       # o tour "Guia de navegação" cobre o Continuar
    if antes_do_clique:
        antes_do_clique()   # ex.: gravar "emitindo" no registro imediatamente antes do clique
        with sem_parar():
            botao.click()
            if esperar_saida:
                esperar_sair_da_rota(page, _rota(etapa), timeout_ms or s.t("timeout_tela_ms"), etapa, "Continuar")
        return
    botao.click()
    if esperar_saida:
        esperar_sair_da_rota(page, _rota(etapa), timeout_ms or s.t("timeout_tela_ms"), etapa, "Continuar")


def _novo_resultado(s: Sessao, a: Andamento, plano: PlanoNaTela) -> ResultadoPlano:
    p = a.pedido
    return ResultadoPlano(pedido_id=p.id, linha=p.linha, cnpj=p.cnpj, plano=plano.nome,
                          acomodacao=plano.acomodacao, razao_social=a.razao_social,
                          preco_mensal=plano.preco, versao=p.coparticipacao)


# ============================ portal antigo ============================

def no_cotador(page) -> bool:
    """A página é uma tela do cotador novo: rota do cotador no caminho da URL ou o título "Comece por aqui"."""
    try:
        if page.is_closed():
            return False
        if any(pedaco in sel.caminho(page) for _, pedaco in sel.ROTAS):
            return True
        return bool(visiveis(page.get_by_text(sel.TITULOS["dados_empresa"])))
    except Exception:  # noqa: BLE001  (página navegando)
        return False


def assistente_novo(s: Sessao, page=None) -> bool:
    """O cotador está num assistente novo (Comece por aqui, CNPJ vazio e editável): já é um começo de pedido."""
    page = page or s.page
    try:
        if page.is_closed() or "/dados-empresa" not in sel.caminho(page):
            return False
        campo = sel.campo_cnpj(page)
        return bool(visiveis(campo)) and campo.is_editable() and not campo.input_value().strip()
    except Exception:  # noqa: BLE001
        return False


def tela_modulos(s: Sessao, a: Andamento) -> None:
    s.mapa.registrar(s.page, "modulos")
    clicar_texto(s.page, sel.TEXTO_CARD_PME, "card Cotação PME", etapa="modulos")
    _esperar_cotador(s, "Cotação PME", "modulos")


def tela_painel(s: Sessao, a: Andamento) -> None:
    """Painel "Estou em cotações" (PainelCotacao.aspx, 05/11): "NOVA COTAÇÃO" abre o cotador. Sem o cartão,
    "Selecionar outro módulo" leva à tela de módulos e o fluxo segue por ela."""
    page = s.page
    s.mapa.registrar(page, "painel")
    try:
        cartao = esperar_visivel(sel.cartao_nova_cotacao(page), 15000, "cartão NOVA COTAÇÃO", "painel")
    except ErroFluxo:
        s.log.warning("Não achei 'NOVA COTAÇÃO' no painel de cotações; indo pela tela de módulos.")
        esperar_visivel(sel.link_selecionar_modulo(page), 10000, "SELECIONAR OUTRO MÓDULO", "painel").click()
        if not _esperar_ate(lambda: tela_modulos_visivel(s.page), s.t("timeout_tela_ms") / 1000):
            raise ErroFluxo("'Selecionar outro módulo' não levou à tela de módulos", "painel") from None
        return
    s.log.info("Painel de cotações: NOVA COTAÇÃO.")
    cartao.click()
    _esperar_cotador(s, "NOVA COTAÇÃO", "painel")


def _esperar_cotador(s: Sessao, botao: str, etapa: str) -> None:
    # Portal 04/11: o cotador abriu, mas demorou mais que a espera fixa de 30 s e o robô desistiu já em
    # "Comece por aqui". Agora espera o tempo de tela até alguma aba (a mesma ou uma nova, depois de páginas
    # intermediárias) estar numa rota do cotador ou mostrar "Comece por aqui".
    fim = time.monotonic() + s.t("timeout_tela_ms") / 1000
    while time.monotonic() < fim:
        for aba in reversed(s.contexto.pages):
            if no_cotador(aba):
                if aba is not s.page:
                    aba.bring_to_front()
                    s.page = aba
                    s.log.info("O cotador abriu em uma aba nova; o robô passou a usar essa aba.")
                return
        if visiveis(sel.login_campo_cpf(s.page)):
            s.log.info("A sessão do portal tinha acabado: o portal pediu o login de novo.")
            return      # o fluxo identifica a tela de login e entra (o portal volta para o cotador depois)
        conferir_parar(etapa)
        time.sleep(0.25)
    raise ErroFluxo(f"clicar em '{botao}' não abriu o cotador", etapa)


# ============================ cotador novo ============================

def avisar_se_o_portal_mudou(s: Sessao) -> None:
    """Compara a versão (build) do cotador com a da última vez e avisa no log quando mudou: foi assim que o robô parou em
    15/11 sem ninguém saber que o portal tinha sido atualizado. Só informa; nunca muda o que o robô faz."""
    try:
        from nucleo.configuracao import aprendido, aprender
        srcs = s.page.eval_on_selector_all("script[src]", "els => els.map(e => e.getAttribute('src'))")
        build = ex.build_do_portal(srcs)
        if not build:
            return
        pasta = s.cfg["saida"]["pasta"]
        antes = aprendido(pasta).get("build_cotador")
        if antes == build:
            return
        if antes:
            s.log.warning("O PORTAL DA SULAMÉRICA FOI ATUALIZADO (a versão do cotador mudou desde a última execução). Se alguma "
                          f"tela falhar, comece por aqui. Antes: {antes} | Agora: {build}")
        else:
            s.log.info(f"Versão do cotador da SulAmérica registrada: {build}")
        aprender(pasta, "build_cotador", build)
    except Exception:  # noqa: BLE001  (é só um aviso)
        pass


def dados_empresa(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "dados_empresa"
    esperar_tela(page, etapa, s.cfg)
    avisar_se_o_portal_mudou(s)
    s.mapa.registrar(page, etapa)
    if p.vendedor:
        _ajustar_vendedor(s, p.vendedor)

    campo = esperar_visivel(sel.campo_cnpj(page), 15000, "campo CNPJ", etapa)
    atual = so_digitos(campo.input_value())
    if atual and atual != p.cnpj and not campo.is_editable():
        raise ErroFluxo(f"a cotação copiada é do CNPJ {formatar_cnpj(atual)}, mas o pedido é "
                        f"{formatar_cnpj(p.cnpj)}", etapa)
    if atual != p.cnpj:
        campo.click()
        campo.fill("")
        campo.press_sequentially(p.cnpj, delay=40)  # campo com máscara: digitar tecla a tecla
    else:
        s.log.info("CNPJ já preenchido (cotação copiada).")
    esperar_visivel(sel.msg_cnpj_valido(page), 30000, "mensagem 'CNPJ válido' (consulta da Receita)", etapa)
    esperar_visivel(page.get_by_text(sel.rx("Razão Social")), 30000, "dados da empresa", etapa)
    a.razao_social = ex.ler_razao_social(page.locator("body").inner_text())
    s.log.info(f"Empresa: {a.razao_social or '(razão social não lida)'} | {formatar_cnpj(p.cnpj)}")
    _continuar(s, etapa)


def _ajustar_vendedor(s: Sessao, desejado: str) -> None:
    page = s.page
    campo = esperar_visivel(sel.campo_vendedor(page), 15000, "campo Vendedor", "dados_empresa")
    def valor_atual() -> str:
        try:
            return campo.input_value()
        except Exception:  # noqa: BLE001  (pode não ser input)
            return campo.inner_text()

    # Portal 04/11: o vendedor aparece como "TESTE - LEONARDO TURYA" e foi configurado como
    # "TESTE-LEONARDO TURYA". O nome vale sem olhar espaços, hífens, acentos e maiúsculas.
    def chave(nome: str) -> str:
        return re.sub(r"[^a-z0-9]", "", norm(nome))

    atual = valor_atual()
    if chave(desejado) == chave(atual):
        return
    s.log.info(f"Trocando vendedor de '{atual}' para '{desejado}'.")
    campo.click()
    opcoes: list = []
    for digitar in (False, True):          # a lista pode só aparecer depois de digitar o nome
        if digitar:
            campo.fill(desejado)
        fim = time.monotonic() + 5
        while time.monotonic() < fim and not opcoes:
            opcoes = visiveis(page.get_by_role("option"))
            if not opcoes:
                time.sleep(0.2)
        if opcoes:
            break
    nomes = [" ".join((o.inner_text() or "").split()) for o in opcoes]
    certas = [o for o, nome in zip(opcoes, nomes) if chave(nome) == chave(desejado)]
    if len(certas) != 1:
        raise ErroFluxo(f"o vendedor '{desejado}' não está na lista do portal (a lista mostra: "
                        f"{', '.join(nomes) or 'nada'}). Corrija o vendedor na engrenagem do robô ou deixe vazio "
                        "para usar quem fez o login", "dados_empresa")
    certas[0].click()
    time.sleep(0.3)
    if chave(valor_atual()) != chave(desejado):
        raise ErroFluxo(f"o campo Vendedor ficou '{valor_atual()}', esperado '{desejado}'", "dados_empresa")


def cuidado_360(s: Sessao, a: Andamento) -> None:
    page, etapa = s.page, "cuidado_360"
    esperar_tela(page, etapa, s.cfg)
    s.mapa.registrar(page, etapa)
    desejado = "Sim" if a.pedido.cuidado_360 else "Não"
    opcao = esperar_visivel(sel.radio(page, desejado), 10000, f"opção '{desejado}' do Cuidado 360°", etapa)
    if not opcao.is_checked():
        opcao.check()
    _continuar(s, etapa, esperar_saida=False)
    # Com "Sim" aparece o modal de aceite dos termos; com "Não" pode não aparecer.
    fim = time.monotonic() + 8
    while time.monotonic() < fim:
        if _rota(etapa) not in page.url.lower():
            return
        botoes = visiveis(sel.botao_prosseguir(page))
        if botoes:
            s.mapa.registrar(page, "cuidado_360_modal")
            botoes[0].click()
            break
        time.sleep(0.25)
    esperar_sair_da_rota(page, _rota(etapa), s.t("timeout_tela_ms"), etapa, "Prosseguir")


def congenere(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "congenere"
    esperar_tela(page, etapa, s.cfg)
    s.mapa.registrar(page, etapa)
    if p.seguro_novo:
        caixa = esperar_visivel(sel.check_seguro_novo(page), 10000, "'Este é um seguro novo'", etapa)
        if not caixa.is_checked():
            caixa.check()
    else:
        # 06/11: primeiro o que o corretor digitou ("BRADESCO"); depois o nome do de-para da configuração.
        nomes = p.congeneres_para_tentar()
        ja = next((n for n in nomes if visiveis(sel.chip_congenere(page, n))), None)
        if ja:
            s.log.info(f"Congênere {ja} já selecionada (cotação copiada).")
        else:
            campo = esperar_visivel(sel.campo_congenere(page), 10000, "campo da congênere", etapa)
            for nome in nomes:
                campo.click()
                campo.fill("")
                campo.press_sequentially(nome, delay=50)
                opcao = _opcao_congenere(page, nome, 8)
                if opcao is None:
                    s.log.warning(f"A congênere '{nome}' não apareceu na lista do portal.")
                    continue
                opcao.click()
                esperar_visivel(sel.chip_congenere(page, nome), 10000, f"congênere {nome} selecionada", etapa)
                s.log.info(f"Congênere atual: {nome}.")
                break
            else:
                campo.fill("")
                raise ErroDados(f"a congênere '{' / '.join(nomes)}' não apareceu na lista do portal; digite o nome "
                                "como aparece no portal (ou ajuste os nomes das operadoras na engrenagem)", etapa)
    _continuar(s, etapa)


def _opcao_congenere(page, nome: str, segundos: float = 10):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        for loc in (sel.opcao_congenere(page, nome), page.get_by_text(sel.rx(nome, exato=True))):
            achados = visiveis(loc)
            if achados:
                return achados[0]
        time.sleep(0.25)
    return None


def vidas(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "vidas"
    esperar_tela(page, etapa, s.cfg)
    for rotulo in ROTULOS:
        desejado = p.vidas[rotulo]
        campo = esperar_visivel(sel.campo_faixa(page, rotulo), 10000, f"campo da faixa {rotulo}", etapa)
        valor = campo.input_value().strip()
        atual = int(valor) if valor.isdigit() else 0
        if atual != desejado:
            campo.click()
            campo.fill(str(desejado))
            campo.press("Tab")
    fim = time.monotonic() + 8
    lido = None
    while time.monotonic() < fim:
        textos = [el.inner_text() for el in visiveis(sel.status_vidas(page))]
        lido = next((n for n in (ex.ler_status_vidas(t) for t in textos) if n is not None), None)
        if lido == p.total_vidas:
            break
        time.sleep(0.25)
    s.mapa.registrar(page, etapa)
    if lido != p.total_vidas:
        raise ErroFluxo(f"o portal mostra {lido} vida(s) distribuída(s); a planilha tem {p.total_vidas}", etapa)
    _continuar(s, etapa)


def idades(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "idades"
    esperar_tela(page, etapa, s.cfg)
    s.mapa.registrar(page, etapa)
    faixas = ex.ler_faixas_idades(page.locator("body").inner_text())
    if not faixas:
        raise ErroFluxo("não consegui ler quais faixas pedem idade exata", etapa)
    for rotulo, (feitas, total) in faixas.items():
        if feitas >= total:
            continue
        lista = p.idades.get(rotulo) or []
        if len(lista) < total:
            raise ErroDados(f"o portal pede a idade exata de {total} vida(s) da faixa {rotulo}; "
                            f"preencha a coluna idades_{CHAVE_POR_ROTULO[rotulo]} na planilha", etapa)
        for idade in lista[feitas:total]:
            campo = esperar_visivel(sel.campo_idade(page), 10000, "campo Idade", etapa)
            campo.click()
            campo.fill(str(idade))
            botao = esperar_visivel(sel.botao_adicionar_idade(page), 10000, "botão Adicionar idade", etapa)
            fim = time.monotonic() + 5
            while not botao.is_enabled() and time.monotonic() < fim:
                time.sleep(0.2)
            botao.click()
            time.sleep(0.4)
        s.log.info(f"Idades informadas na faixa {rotulo}: {lista}")
    faixas = ex.ler_faixas_idades(page.locator("body").inner_text())
    faltando = [r for r, (f, t) in faixas.items() if f < t]
    s.mapa.registrar(page, f"{etapa}_preenchidas")
    if faltando:
        raise ErroFluxo(f"faixas ainda incompletas na tela de idades: {faltando}", etapa)
    _continuar(s, etapa)


# ---------------------------- planos ----------------------------

def _esperar_lista(page, timeout_ms: int = 30000) -> None:
    time.sleep(0.3)
    esperar_sem_skeleton(page, timeout_ms)
    fim = time.monotonic() + timeout_ms / 1000
    ultimo, estavel = -1, 0
    while time.monotonic() < fim:
        n = len(visiveis(sel.botoes_cards(page)))
        if n == 0 and visiveis(sel.texto_sem_planos(page)):
            return
        estavel = estavel + 1 if (n > 0 and n == ultimo) else 0
        if estavel >= 2:
            return
        ultimo = n
        time.sleep(0.3)
    raise ErroFluxo("a lista de planos não terminou de carregar", "planos")


class FiltroTravado(Exception):
    """O portal não deixou mudar um filtro (ex.: a coparticipação numa cotação copiada)."""


def _aplicar_filtros(s: Sessao, a: Andamento) -> None:
    page, p = s.page, a.pedido

    def ajustar(localizador, nome: str, marcado: bool) -> None:
        caixa = esperar_visivel(localizador(page, nome), 10000, f"filtro '{nome}'", "planos")
        if caixa.is_checked() != marcado:
            if not caixa.is_enabled():
                raise FiltroTravado(nome)
            caixa.set_checked(marcado)
            s.log.info(f"Filtro '{nome}': {'marcado' if marcado else 'desmarcado'}.")
            _esperar_lista(page)

    # O produto vem da configuração do robô. Se o portal não mostrar esse produto, o robô para
    # (falha fechada): cotar outro produto em silêncio seria pior do que não cotar.
    if p.produto:
        if not visiveis(sel.filtro_radio(page, p.produto)):
            raise ErroDados(f"o produto '{p.produto}' da configuração do robô não aparece no filtro "
                            "'Produto Saúde PME' do portal; confira o nome em Robôs > SulAmérica > Planos", "planos")
        ajustar(sel.filtro_radio, p.produto, True)
    ajustar(sel.filtro_radio, p.tipo_contratacao, True)
    outro_prazo = 12 if p.vigencia_meses == 24 else 24
    ajustar(sel.filtro_check, f"{p.vigencia_meses} meses", True)        # marca o desejado antes
    ajustar(sel.filtro_check, f"{outro_prazo} meses", False)            # e só então desmarca o outro
    com, sem = "Com coparticipação", "Sem coparticipação"
    desejada, outra = (com, sem) if p.coparticipacao == "com" else (sem, com)
    ajustar(sel.filtro_check, desejada, True)
    ajustar(sel.filtro_check, outra, False)
    a.copart_na_tela = p.coparticipacao


def _filtrar_e_ler(s: Sessao, a: Andamento) -> bool:
    """Acerta os filtros para a cotação atual e lê a lista de planos. False quando a cotação copiada não deixou
    trocar a coparticipação: o robô saiu da cotação e o fluxo refaz esta cotação do começo, sem cópia."""
    try:
        _aplicar_filtros(s, a)
    except FiltroTravado as e:
        if not a.copia:
            raise ErroFluxo(f"o portal não deixou mudar o filtro '{e}' na tela Planos", "planos") from None
        from nucleo.configuracao import aprender
        rotulo = a.alvo.rotulo_completo() if a.alvo else "esta cotação"
        s.log.warning(f"Na cotação copiada o portal não deixou mudar o filtro '{e}'. Saindo da cotação (mesma aba, "
                      f"sem login) para fazer {rotulo} por NOVA COTAÇÃO.")
        s.mapa.registrar(s.page, "planos_filtro_travado", forcar=True)
        aprender(s.cfg["saida"]["pasta"], "copia_trava_copart", True)   # da próxima vez, Nova cotação direto
        a.copia = False
        a.copart_na_tela = ""
        sair_da_cotacao(s)       # painel "Estou em cotações": o fluxo segue por NOVA COTAÇÃO (tela_painel)
        return False
    a.catalogo = _ler_catalogo(s)
    s.mapa.registrar(s.page, "planos")
    if not a.catalogo:
        raise ErroFluxo("nenhum plano na lista com esses filtros", "planos")
    p = a.pedido
    s.log.info(f"{len(a.catalogo)} plano(s) na lista ({p.coparticipacao} coparticipação): "
               + "; ".join(f"{x.nome} | {x.acomodacao} {x.preco}" for x in a.catalogo))
    if p.coparticipacao not in a.precos_salvos:
        s.resultados.precos(p.id, p.cnpj, [x.visto() for x in a.catalogo])
        a.precos_salvos.add(p.coparticipacao)
    return True


def _ler_pagina(s: Sessao, pagina: int) -> list[PlanoNaTela]:
    planos = []
    vistos: set[str] = set()
    for botao in visiveis(sel.botoes_cards(s.page)):
        texto = sel.card_do_botao(botao).inner_text()
        if texto in vistos:   # portal 04/11: cada card tem dois botões "Selecionar plano" (um sem texto, em cima)
            continue
        vistos.add(texto)
        if len([1 for l in texto.splitlines() if norm(l) in ("selecionar plano", "plano selecionado")]) > 1:
            raise ErroFluxo("o seletor de card pegou mais de um plano; ajuste card_do_botao em seletores.py",
                            "planos")
        plano = ex.ler_card_plano(texto, pagina)
        if plano:
            planos.append(plano)
    return planos


def _ir_para_pagina(s: Sessao, numero: int) -> None:
    botoes = visiveis(sel.botao_pagina(s.page, numero))
    if not botoes:
        raise ErroFluxo(f"não achei o botão da página {numero} na lista de planos", "planos")
    botoes[0].click()
    _esperar_lista(s.page)


def _ler_catalogo(s: Sessao) -> list[PlanoNaTela]:
    page = s.page
    _esperar_lista(page)
    catalogo = _ler_pagina(s, 1)
    pagina = 1
    while pagina < 20 and visiveis(sel.botao_pagina(page, pagina + 1)):
        pagina += 1
        _ir_para_pagina(s, pagina)
        catalogo += _ler_pagina(s, pagina)
    if pagina > 1:
        _ir_para_pagina(s, 1)
    return catalogo


def _tracos(texto: str) -> str:
    """'557 – AHO' e '557-AHO' viram '557 - aho' (o portal mistura traços)."""
    return re.sub(r"\s*[-–]\s*", " - ", norm(texto))


def _conferir_card(plano: PlanoNaTela, p: Pedido) -> None:
    """Falha fechada: se não der para ler a descrição ou a coparticipação do card, não seleciona."""
    d = norm(plano.descricao)
    problemas = []
    if not d:
        problemas.append("descrição (produto - contratação - vigência) não lida")
    else:
        if p.produto and not _tracos(d).startswith(_tracos(p.produto)):
            problemas.append(f"produto (esperado {p.produto})")
        if norm(p.tipo_contratacao) not in d:
            problemas.append(f"tipo de contratação (esperado {p.tipo_contratacao})")
        if f"{p.vigencia_meses} meses" not in d:
            problemas.append(f"vigência (esperado {p.vigencia_meses} meses)")
    if not plano.coparticipacao:
        problemas.append("coparticipação não lida")
    elif not norm(plano.coparticipacao).startswith(p.coparticipacao):
        problemas.append(f"coparticipação (esperado {p.coparticipacao})")
    if problemas:
        raise ErroFluxo(f"o card de {plano.nome} mostra '{plano.descricao} / {plano.coparticipacao}': "
                        f"problema em {', '.join(problemas)}", "planos")


def _selecionar_somente(s: Sessao, escolhido: PlanoNaTela) -> None:
    page = s.page
    for botao in visiveis(sel.botao_desmarcar_todos(page)):
        if botao.is_enabled():
            botao.click()
            _esperar_lista(page)
        break
    if escolhido.pagina != 1:
        _ir_para_pagina(s, escolhido.pagina)
    for botao in visiveis(sel.botoes_cards(page)):
        card = sel.card_do_botao(botao)
        plano = ex.ler_card_plano(card.inner_text(), escolhido.pagina)
        if plano and plano.nome == escolhido.nome and plano.acomodacao == escolhido.acomodacao:
            # Portal 04/11: o card tem dois botões "Selecionar plano"; o de cima não tem texto. O estado vem do
            # texto do card e o clique vai no botão que mostra "Selecionar plano".
            def selecionado() -> bool:
                return "plano selecionado" in norm(card.inner_text())

            if not selecionado():
                com_texto = [b for b in visiveis(sel.botoes_cards(card)) if norm(b.inner_text())]
                (com_texto[0] if com_texto else botao).click()
            fim = time.monotonic() + 8
            while time.monotonic() < fim:
                if selecionado():
                    return
                time.sleep(0.2)
            raise ErroFluxo(f"cliquei em {escolhido.nome} mas o card não ficou 'Plano selecionado'", "planos")
    raise ErroFluxo(f"não achei o card de {escolhido.nome} | {escolhido.acomodacao} para selecionar", "planos")


def _resolver_criterio(s: Sessao, a: Andamento) -> list[PlanoAlvo]:
    quantidade = int(a.pedido.criterio_quantidade or 1)
    ordenados = sorted(a.catalogo, key=lambda x: x.preco)[:quantidade]
    alvos = [PlanoAlvo(x.nome, x.acomodacao) for x in ordenados]
    s.log.info(f"Critério menor_preco ({quantidade}): {[x.rotulo() for x in alvos]}")
    return alvos


# O que dizer de uma cotação que o registro bloqueia (a tela usa estas frases para explicar).
MENSAGEM_REGISTRO = {
    "pdf_ok": "já concluída em execução anterior",
    "emitindo": "o robô clicou em emitir mas não confirmou o protocolo; confira em 'Cotações emitidas' no "
                "portal antes de liberar",
    "emitida": "protocolo emitido, PDF pendente: baixe à mão em 'Cotações emitidas' no portal",
    "pdf_manual": "protocolo emitido; baixe o PDF à mão em 'Cotações emitidas'",
}


def reemissao_pedida(s: Sessao, item: dict | None) -> bool:
    """O corretor pediu na tela para emitir de novo esta cotação, pelo protocolo que viu no aviso de "já
    emitida". Só vale para cotação concluída (pdf_ok): emissão incerta ou sem PDF continua bloqueada."""
    return (bool(item) and not s.ensaio and item.get("status") == "pdf_ok"
            and str(item.get("protocolo") or "") in s.reemitir)


def _ja_emitida(s: Sessao, a: Andamento, escolhido: PlanoNaTela) -> bool:
    """Bloqueia a mesma cotação real (CNPJ + parâmetros + plano do portal), qualquer que seja a grafia."""
    if s.ensaio:
        return False
    p = a.pedido
    chave = s.estado.chave(p, escolhido.nome, escolhido.acomodacao)
    if s.estado.pode_emitir(chave):
        return False
    item = s.estado.item(chave)
    if reemissao_pedida(s, item):
        return False
    situacao = "PULADO" if item["status"] == "pdf_ok" else "VERIFICAR"
    a.aguardando_emissao = False   # o portal voltou para a lista: a emissão incerta fica no registro ("emitindo")
    s.resultados.plano(ResultadoPlano(
        pedido_id=p.id, linha=p.linha, cnpj=p.cnpj, plano=escolhido.nome, acomodacao=escolhido.acomodacao,
        razao_social=a.razao_social, status=situacao, protocolo=item.get("protocolo", ""),
        pdf_arquivo=item.get("pdf", ""), pdf_destino=item.get("pdf_destino", ""),
        pdf_nome=item.get("nome_destino", ""), versao=p.coparticipacao,
        erro=f"mesma cotação já registrada: {MENSAGEM_REGISTRO.get(item['status'], item['status'])}; não emito de novo"))
    s.log.info(f"[{p.id}] {escolhido.nome} | {escolhido.acomodacao}: já registrada "
               f"({item['status']}, protocolo {item.get('protocolo', '-')}); pulando.")
    return True


def planos(s: Sessao, a: Andamento) -> None:
    page, etapa = s.page, "planos"
    esperar_tela(page, etapa, s.cfg)
    _esperar_lista(page)
    a.copart_na_tela = ""
    if not _filtrar_e_ler(s, a):
        return

    if a.resolver_por_criterio and not a.alvos:
        escolhidos = _resolver_criterio(s, a)
        if not s.ensaio:
            s.estado.salvar_planos_resolvidos(a.base, [x.rotulo() for x in escolhidos])
        a.alvos = com_versoes(a.base, escolhidos)

    while a.alvo is not None:
        alvo, p = a.alvo, a.pedido
        if p.coparticipacao != a.copart_na_tela:
            # A próxima cotação é a outra versão (ex.: sem coparticipação): troca o filtro e lê a lista de novo.
            if not _filtrar_e_ler(s, a):
                return
        candidatos = [x for x in a.catalogo if alvo.casa_com(x.nome, x.acomodacao)]
        try:
            if not candidatos:
                lista = "; ".join(sorted({f"{x.nome} | {x.acomodacao}" for x in a.catalogo}))
                raise ErroDados(f"o plano '{alvo.rotulo()}' não está na lista com esses filtros. "
                                f"Disponíveis: {lista}", etapa)
            if len(candidatos) > 1:
                opcoes = ", ".join(f"{alvo.nome} | {x.acomodacao}" for x in candidatos)
                raise ErroDados(f"'{alvo.nome}' aparece {len(candidatos)} vezes ({opcoes}); "
                                "informe a acomodação na planilha", etapa)
            escolhido = candidatos[0]
            _conferir_card(escolhido, p)
        except ErroDados as e:
            # Plano com problema não trava os outros planos do mesmo pedido.
            r = ResultadoPlano(pedido_id=p.id, linha=p.linha, cnpj=p.cnpj, plano=alvo.nome,
                               acomodacao=alvo.acomodacao or "", razao_social=a.razao_social,
                               status="ERRO", erro=str(e), etapa_erro=etapa, versao=p.coparticipacao)
            s.resultados.plano(r)
            s.log.error(f"[{p.id}] {e}")
            a.indice += 1
            continue
        if _ja_emitida(s, a, escolhido):
            a.indice += 1
            continue
        _selecionar_somente(s, escolhido)
        a.plano_tela = escolhido
        a.resultado = _novo_resultado(s, a, escolhido)
        s.log.info(f"Plano selecionado: {escolhido.nome} | {escolhido.acomodacao} ({escolhido.preco})"
                   + (f", {p.coparticipacao} coparticipação." if len(a.base.versoes_copart) > 1 else "."))
        _continuar(s, etapa)
        return
    # Nenhum plano restante deu certo nesta tela: sair sem emitir.
    sair_ou_avisar(s)
    a.terminou = True


def _esperar_conteudo(s: Sessao, etapa: str, pronto, descricao: str) -> str:
    """O cotador troca a URL e o texto da região de status ("Comparação de Planos") ANTES de desenhar a tela nova: com o
    computador ocupado (3 robôs juntos, 15/11) o corpo continuou o da tela anterior e o robô leu uma tabela que ainda não
    existia ("faixas ausentes"). Lê de novo, até `timeout_tela_ms`, até o conteúdo da tela aparecer. Devolve o texto da
    página; se o tempo acabar devolve o último e quem chamou confere (falha fechada, como antes)."""
    page = s.page
    limite = s.cfg["execucao"].get("timeout_tela_ms", 60000) / 1000
    inicio = time.monotonic()
    texto = ""
    leituras = falhas = 0
    while True:
        leituras += 1
        try:
            texto = page.locator("body").inner_text()
        except Exception:  # noqa: BLE001  (página trocando de tela, ou ocupada demais para responder)
            texto, falhas = "", falhas + 1
        if pronto(texto) or time.monotonic() - inicio >= limite:
            break
        conferir_parar(etapa)
        time.sleep(0.5)
    espera = time.monotonic() - inicio
    if espera >= 2:
        s.log.info(f"{descricao}: a tela já mostrava o título, mas o conteúdo levou {espera:.0f} s para aparecer"
                   + ("" if pronto(texto) else " (não apareceu no tempo da tela)")
                   + f" [{leituras} leituras, {falhas} sem resposta, {len(texto)} caracteres na última].")
    return texto


def comparacao(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "comparacao"
    esperar_tela(page, etapa, s.cfg)
    texto = _esperar_conteudo(s, etapa, lambda t: all(r in ex.ler_tabela_comparacao(t) for r in ROTULOS), "Comparação")
    s.mapa.registrar(page, etapa)
    if sum(1 for l in texto.splitlines() if norm(l).startswith("faixas")) > 1:
        raise ErroFluxo("há mais de um plano na comparação; o robô cota um plano por vez", etapa)
    linhas = {norm(l) for l in texto.splitlines()}
    if norm(a.plano_tela.nome) not in linhas:   # nome exato: "Especial Vital" não casa "Especial Vital R1"
        raise ErroFluxo(f"a comparação não mostra o plano {a.plano_tela.nome}", etapa)
    tabela = ex.ler_tabela_comparacao(texto)
    problemas = ex.conferir_tabela(tabela, p.vidas, a.plano_tela.preco, s.tol())
    if problemas:
        raise ErroFluxo("valores da comparação não batem: " + "; ".join(problemas), etapa)
    a.resultado.valores_por_vida = {r: v["valor_vida"] for r, v in tabela.items()}
    _continuar(s, etapa)


def resumo(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "resumo"
    esperar_tela(page, etapa, s.cfg)
    texto = _esperar_conteudo(s, etapa, lambda t: bool(re.search(r"Caracter[ií]sticas da Cota", t, re.I)), "Resumo")
    s.mapa.registrar(page, etapa)
    valores = ex.ler_resumo(texto)
    tabela = {r: {"qtd": p.vidas.get(r, 0), "valor_vida": v}
              for r, v in (a.resultado.valores_por_vida or {}).items()}
    iof_vida = ex.iof_por_vida(tabela, s.aliquota()) if tabela else None
    problemas = ex.conferir_resumo(valores, a.plano_tela.preco, s.aliquota(), s.tol(), iof_vida)
    if p.cnpj not in so_digitos(texto):
        problemas.append(f"o resumo não mostra o CNPJ {formatar_cnpj(p.cnpj)}")
    plano_resumo = ex.ler_plano_resumo(texto)
    if norm(plano_resumo) != norm(a.plano_tela.nome):
        problemas.append(f"o resumo mostra o plano '{plano_resumo}', esperado '{a.plano_tela.nome}'")
    problemas += ex.conferir_caracteristicas(ex.ler_caracteristicas(texto), p)
    if problemas:
        raise ErroFluxo("resumo não confere: " + "; ".join(problemas), etapa)
    r = a.resultado
    r.total_sem_iof, r.iof, r.total_com_iof = valores["total_sem_iof"], valores["iof"], valores["total"]

    if s.ensaio:
        r.status = "ENSAIO_OK"
        s.resultados.plano(r)
        s.log.info(f"ENSAIO: {r.plano} | {r.acomodacao}: {r.total_sem_iof} + IOF {r.iof} = {r.total_com_iof}. "
                   "Parando antes de emitir.")
        sair_ou_avisar(s)               # o ensaio deu certo: não sair da cotação não vira erro do plano
        a.terminou = True
        return

    chave = s.estado.chave(p, a.plano_tela.nome, a.plano_tela.acomodacao)
    item = s.estado.item(chave)
    substituir = str(item["protocolo"]) if reemissao_pedida(s, item) else None
    if not substituir and not s.estado.pode_emitir(chave):
        raise ErroFluxo(f"o registro diz que {a.plano_tela.nome} | {a.plano_tela.acomodacao} já foi "
                        "emitido; não emito de novo", etapa)

    def marcar_emitindo() -> None:
        obs = "clicou Continuar no resumo"
        if substituir:
            obs += f" (emitindo de novo a pedido do corretor; antes: protocolo {substituir})"
        s.estado.registrar(chave, p, a.plano_tela.nome, a.plano_tela.acomodacao, "emitindo",
                           obs=obs, pasta_destino=p.pasta_destino, substituir_protocolo=substituir)
        if substituir:
            s.reemitir.discard(substituir)   # uma vez só: o novo protocolo volta a bloquear
        a.aguardando_emissao = True

    s.log.info(f"Emitindo cotação de {a.plano_tela.nome} | {a.plano_tela.acomodacao}"
               + (f" de novo (antes: protocolo {substituir})..." if substituir else "..."))
    _continuar(s, etapa, timeout_ms=s.t("timeout_emissao_ms"), antes_do_clique=marcar_emitindo)


def emitida(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "emitida"
    if not a.aguardando_emissao or a.plano_tela is None:
        # Tela de emissão que não é deste pedido (ex.: sobrou da execução anterior): não toca nela.
        s.log.warning("Tela de cotação emitida sem emissão em andamento neste pedido; voltando ao início.")
        voltar_ao_inicio(s)
        return
    with sem_parar():
        esperar_visivel(page.get_by_text(sel.TEXTO_EMITIDA), s.t("timeout_tela_ms"),
                        "COTAÇÃO EMITIDA COM SUCESSO", etapa)
        texto = esperar_visivel(page.get_by_text(sel.TEXTO_PROTOCOLO), 15000, "Protocolo Saúde", etapa).inner_text()
        protocolo = ex.ler_protocolo(texto) or ex.ler_protocolo(page.locator("body").inner_text())
        if not protocolo:
            raise ErroFluxo("não consegui ler o número do protocolo", etapa)
        chave = s.estado.chave(p, a.plano_tela.nome, a.plano_tela.acomodacao)
        nome_destino = nome_pdf_destino(s.cfg, p.cnpj, protocolo, a.plano_tela.nome,
                                        a.plano_tela.acomodacao if _acomodacao_no_nome(a) else "",
                                        versao=versao_no_nome(a))
        s.estado.registrar(chave, p, a.plano_tela.nome, a.plano_tela.acomodacao, "emitida",
                           protocolo=protocolo, url_emissao=page.url, nome_destino=nome_destino)
        a.aguardando_emissao = False
    r = a.resultado
    r.protocolo = protocolo
    r.pdf_nome = nome_destino
    s.log.info(f"Cotação emitida: protocolo {protocolo}.")
    s.mapa.registrar(page, etapa)
    aceitar_cookies(page)

    arquivo = baixar_pdf(s, p.cnpj, protocolo, a.plano_tela.nome)
    destino = ""
    if p.pasta_destino:
        try:
            destino = copiar_para_destino(arquivo, p.pasta_destino, nome_destino,
                                          bool(s.cfg["saida"].get("substituir_no_destino", True)), s.log)
        except Exception as e:  # noqa: BLE001  (pasta fora do ar, arquivo aberto no leitor de PDF...)
            r.erro = f"PDF salvo em {arquivo}, mas a cópia para a pasta do cliente falhou: {e}"
            s.log.warning(r.erro)
    s.estado.registrar(chave, p, a.plano_tela.nome, a.plano_tela.acomodacao, "pdf_ok",
                       pdf=str(arquivo), pdf_destino=destino, nome_destino=nome_destino)
    r.status, r.pdf_arquivo, r.pdf_destino = "OK", str(arquivo), destino
    s.resultados.plano(r)

    if sel.ROTA_EMITIDA not in sel.caminho(page):
        s.log.warning(f"depois do PDF a aba principal saiu da tela da cotação emitida ({sel.caminho(page) or 'fechada'})")
    s.mapa.registrar(page, "emitida_pdf")   # o que ficou na tela depois do download (calibragem do fim)
    a.indice += 1
    a.plano_tela, a.resultado = None, None
    # Próxima cotação do pedido (outro plano ou a versão sem coparticipação): como o corretor no vídeo, na mesma
    # página, sem sair do portal nem fechar nada. COPIAR COTAÇÃO -> SIM -> "Comece por aqui" já preenchido.
    if a.alvo is not None and a.pedido.coparticipacao != p.coparticipacao and _copia_trava_copart(s):
        # Este portal já mostrou que a cópia não deixa trocar a coparticipação: NOVA COTAÇÃO, mesma aba, sem login.
        esperar_visivel(sel.botao_nova_cotacao(page), 15000, "botão Nova cotação", etapa).click()
        esperar_sair_da_rota(page, sel.ROTA_EMITIDA, s.t("timeout_tela_ms"), etapa, "Nova cotação")
        a.copia = False
        s.log.info(f"Próxima cotação: {a.alvo.rotulo_completo()}, por Nova cotação (neste portal a cópia não "
                   "deixa trocar a coparticipação).")
        return
    if a.alvo is not None:
        esperar_visivel(sel.botao_copiar(page), 15000, "botão Copiar cotação", etapa).click()
        sim = _sim_do_modal_copiar(s, etapa)
        if sim is None:
            # A sessão do portal acabou depois do PDF: não dá para copiar. Fecha o modal, volta ao começo (o portal
            # pede o login e o robô entra de novo) e faz a próxima cotação do começo, sem cópia.
            s.log.warning(f"A sessão do portal acabou antes de copiar a cotação; {a.alvo.rotulo_completo()} vai "
                          "ser feita do começo, depois do login.")
            for fechar in visiveis(sel.modal_copiar(page).get_by_role("button"))[:1]:
                fechar.click()
            a.copia = False
            voltar_ao_inicio(s)
            return
        s.mapa.registrar(page, "modal_copiar")
        sim.click()
        esperar_sair_da_rota(page, sel.ROTA_EMITIDA, s.t("timeout_tela_ms"), etapa, "Copiar cotação")
        a.copia = True
        s.log.info(f"Copiando a cotação para a próxima: {a.alvo.rotulo_completo()}.")
        return
    a.terminou = True
    try:
        voltar_ao_inicio(s)
    except Exception as e:  # noqa: BLE001  (o pedido já terminou bem; o próximo pedido se recompõe)
        s.log.warning(f"não consegui voltar à tela de módulos ({e}); o próximo pedido recompõe a tela")


def _sim_do_modal_copiar(s: Sessao, etapa: str):
    """O SIM do modal "Deseja copiar a cotação?". No portal real (06/11) a pergunta e os botões ficam num iframe
    dentro do dialog "Copiar Cotação"; o robô também aceita o modal direto na página."""
    page = s.page
    fim = time.monotonic() + 20
    while time.monotonic() < fim:
        for lugar in (sel.frame_modal_copiar(page), page):
            try:
                if visiveis(sel.login_campo_cpf(lugar)):
                    return None          # a sessão do portal caiu: o modal (ou a página) mostra o login
                if visiveis(lugar.get_by_text(sel.TEXTO_MODAL_COPIAR)):
                    botoes = visiveis(lugar.get_by_role("button", name=sel.TEXTO_SIM).or_(lugar.get_by_text(sel.TEXTO_SIM)))
                    if botoes:
                        return botoes[0]
            except Exception:  # noqa: BLE001  (iframe ainda carregando)
                pass
        time.sleep(0.25)
    raise ErroFluxo("não encontrei o SIM do modal 'Deseja copiar a cotação?' em 20s", etapa)


def _copia_trava_copart(s: Sessao) -> bool:
    """O portal já mostrou (portal.json) que, na cotação copiada, o filtro de coparticipação não muda."""
    from nucleo.configuracao import aprendido
    return bool(aprendido(s.cfg["saida"]["pasta"]).get("copia_trava_copart"))


def _acomodacao_no_nome(a: Andamento) -> bool:
    """True se o plano existe em mais de uma acomodação na lista do portal (ex.: Direto Nacional
    em Enfermaria e em Apartamento). Aí a acomodação entra no nome do PDF, senão um substituiria o outro."""
    nome = norm(a.plano_tela.nome)
    return len({norm(x.acomodacao) for x in a.catalogo if norm(x.nome) == nome}) > 1


def baixar_pdf(s: Sessao, cnpj: str, protocolo: str, plano: str) -> Path:
    page = s.page
    pasta = Path(s.cfg["saida"]["pasta"]) / "pdfs"
    pasta.mkdir(parents=True, exist_ok=True)
    with page.expect_download(timeout=int(s.cfg["execucao"].get("timeout_download_ms", 120000))) as info:
        clicar_texto(page, sel.TEXTO_BAIXAR, "botão Baixar cotação saúde", etapa="emitida")
    download = info.value
    destino = pasta / nome_pdf_arquivo(s.cfg, cnpj, protocolo, plano)
    download.save_as(str(destino))
    _conferir_pdf(destino, protocolo, s.log)
    s.log.info(f"PDF salvo: {destino} (nome original: {download.suggested_filename})")
    return destino


def _conferir_pdf(caminho: Path, protocolo: str, log) -> None:
    dados = caminho.read_bytes()
    if not dados.startswith(b"%PDF") or len(dados) < 500:
        raise ErroFluxo(f"o arquivo baixado não parece um PDF válido ({len(dados)} bytes)", "emitida")
    try:
        from pypdf import PdfReader
        texto = "\n".join((pg.extract_text() or "") for pg in PdfReader(str(caminho)).pages[:2])
        if protocolo not in so_digitos(texto):
            log.warning(f"o PDF não mostra o protocolo {protocolo} nas 2 primeiras páginas; confira o arquivo")
    except Exception as e:  # noqa: BLE001
        log.warning(f"não consegui ler o texto do PDF para conferir ({e})")


# ============================ navegação ============================

def _abas_vivas(s: Sessao) -> list:
    try:
        return [p for p in s.contexto.pages if not p.is_closed()]
    except Exception:  # noqa: BLE001
        return []


def _login_visivel(page) -> bool:
    try:
        return bool(visiveis(sel.login_campo_cpf(page)))
    except Exception:  # noqa: BLE001
        return False


def _esperar_comeco(s: Sessao) -> bool:
    """Espera alguma aba chegar ao começo: tela de módulos, assistente novo do cotador ou o login (sessão que
    caiu). Se for outra aba (ex.: o portal fechou a da emissão), o robô passa a usar essa."""
    fim = time.monotonic() + s.t("timeout_tela_ms") / 1000
    while time.monotonic() < fim:
        for aba in reversed(_abas_vivas(s)):
            login = _login_visivel(aba)
            if tela_modulos_visivel(aba) or painel_visivel(aba) or assistente_novo(s, aba) or login:
                if aba is not s.page:
                    s.log.info("O começo apareceu em outra aba; o robô passou a usar essa aba.")
                    aba.bring_to_front()
                    s.page = aba
                if login:
                    s.log.warning("Depois de voltar ao início o portal mostrou o login.")
                return True
        conferir_parar()
        time.sleep(0.3)
    return False


def voltar_ao_inicio(s: Sessao) -> None:
    """Depois da última cotação do pedido: "Voltar para a home" (tela de módulos) ou "Nova cotação" (assistente
    novo), o que a configuração preferir; se o botão preferido não estiver na tela, usa o outro. Nunca recarrega
    o login nem a página da emissão, e não fecha nada."""
    page = s.page
    botoes = [("Voltar para a home", sel.botao_voltar_home), ("Nova cotação", sel.botao_nova_cotacao)]
    if s.cfg["navegacao"].get("proxima_empresa") == "nova_cotacao":
        botoes.reverse()
    for i, (nome, achar) in enumerate(botoes):
        try:
            botao = esperar_visivel(achar(page), 10000 if i == 0 else 3000, f"botão {nome}", "emitida")
        except ErroFluxo:
            s.log.warning(f"Não achei o botão '{nome}' na tela da cotação emitida.")
            continue
        botao.click()
        if _esperar_comeco(s):
            return
        s.mapa.registrar(s.page, "volta_ao_inicio", forcar=True)
        raise ErroFluxo(f"'{nome}' não levou ao começo (tela {sel.caminho(s.page) or 'fechada'})", "emitida")
    s.mapa.registrar(page, "ERRO_volta_ao_inicio", forcar=True)
    raise ErroFluxo("não achei 'Voltar para a home' nem 'Nova cotação' na tela da cotação emitida", "emitida")


def _esperar_ate(condicao, segundos: float) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            if condicao():
                return True
        except Exception:  # noqa: BLE001  (página navegando)
            pass
        conferir_parar()
        time.sleep(0.2)
    return False


def sair_do_portal(s: Sessao, prazo_s: float = 30) -> bool:
    """Logout: "Sair do Cotador", no menu lateral do portal antigo. Antes volta à tela de módulos (saindo da
    cotação ou da tela da emissão; nunca recarrega o login) e depois espera o portal mostrar o login.
    Quem chama garante o robô parado: nunca no meio de uma cotação. True se saiu."""
    fim = time.monotonic() + prazo_s

    def resta() -> float:
        return max(0.5, fim - time.monotonic())

    page = s.page
    if _login_visivel(page):
        return True                       # a sessão do portal já tinha acabado

    def no_inicio(p) -> bool:            # tela de módulos ou painel de cotações: as duas têm o menu do portal
        return tela_modulos_visivel(p) or painel_visivel(p)

    if not no_inicio(page):
        if sel.ROTA_EMITIDA in sel.caminho(page):
            esperar_visivel(sel.botao_voltar_home(page), int(min(resta(), 10) * 1000),
                            "botão Voltar para a home", "sair").click()
        elif no_cotador(page):
            fechar_guia(page)
            esperar_visivel(page.get_by_role("button", name=sel.TEXTO_SAIR_COTACAO), int(min(resta(), 10) * 1000),
                            "botão Sair da cotação", "sair").click()
            _esperar_ate(lambda: _confirmar_saida(s) or no_inicio(s.page), min(resta(), 10))
        _esperar_ate(lambda: no_inicio(s.page) or _login_visivel(s.page), resta())
        page = s.page
    if _login_visivel(page):
        return True
    if not no_inicio(page):
        raise ErroFluxo(f"não cheguei à tela de módulos para sair ({sel.caminho(page) or 'tela em branco'})", "sair")
    botao = visiveis(sel.botao_sair_do_portal(page))
    if not botao:
        for menu in visiveis(sel.menu_do_portal(page))[:1]:
            menu.click()
            _esperar_ate(lambda: bool(visiveis(sel.botao_sair_do_portal(page))), min(resta(), 5))
        botao = visiveis(sel.botao_sair_do_portal(page))
    if botao:
        botao[0].click()
    else:
        escondido = sel.botao_sair_do_portal(page)
        if not escondido.count():
            raise ErroFluxo("não achei 'Sair do Cotador' no menu do portal", "sair")
        escondido.first.dispatch_event("click")    # o menu não abriu: o mesmo clique, direto no item
    return _esperar_ate(lambda: _login_visivel(s.page), resta())


def _confirmar_saida(s: Sessao) -> bool:
    """Modal "Deseja realmente sair da cotação?" aberto: clica no botão que confirma. False se não há modal."""
    page = s.page
    dialogos = visiveis(sel.modal_sair(page))
    if not dialogos:
        return False
    s.mapa.registrar(page, "modal_sair")
    botoes = [(b, " ".join((b.inner_text() or "").split())) for b in visiveis(dialogos[0].get_by_role("button"))]
    escolha = [b for b, nome in botoes if sel.RX_CONFIRMA_SAIDA.search(nome)]
    if len(escolha) != 1:
        escolha = [b for b, nome in botoes if nome and not sel.RX_CANCELA.search(nome)]
    if len(escolha) != 1:
        raise ErroFluxo("no modal 'Deseja realmente sair da cotação?' não achei um botão só para confirmar "
                        f"(botões: {', '.join(nome or '(sem texto)' for _, nome in botoes)})", "sair")
    escolha[0].click()
    return True


def sair_ou_avisar(s: Sessao) -> None:
    """Sai da cotação depois que o plano já foi registrado: se não der, só avisa (o próximo pedido confere)."""
    try:
        sair_da_cotacao(s)
    except ErroLogin:
        raise
    except ErroFluxo as e:
        s.log.warning(f"{e}. O próximo pedido só começa se a tela voltar ao início.")


def _saiu(s: Sessao) -> bool:
    return tela_modulos_visivel(s.page) or painel_visivel(s.page) or assistente_novo(s)


def sair_da_cotacao(s: Sessao) -> None:
    """Abandona o assistente sem emitir: volta à tela de módulos (ou a um assistente novo, vazio).

    De dentro do cotador, nunca volta à página de login: com a sessão viva o portal mostra o login de novo e
    recusa o segundo acesso ("Já existe um acesso ativo para esse CPF"). Se não conseguir sair, levanta
    ErroFluxo e deixa a sessão como está."""
    page = s.page

    def esperar(condicao, segundos: float) -> None:
        fim = time.monotonic() + segundos
        while time.monotonic() < fim and not condicao():
            time.sleep(0.2)

    for _ in range(4):
        if _saiu(s):
            return
        fechar_guia(page)
        if sel.ROTA_EMITIDA in sel.caminho(page):
            voltar_ao_inicio(s)
            return
        if _confirmar_saida(s):
            esperar(lambda: _saiu(s), 15)
            continue
        sair = visiveis(page.get_by_role("button", name=sel.TEXTO_SAIR_COTACAO))
        if sair:
            sair[0].click()
            esperar(lambda: _saiu(s) or bool(visiveis(sel.modal_sair(page))), 5)   # o modal aparece por cima
            continue
        voltar = visiveis(sel.botao_voltar(page))      # ex.: o resumo não tem "Sair da cotação"
        if not voltar:
            break
        antes = page.url
        voltar[0].click()
        esperar(lambda: page.url != antes, 5)
        esperar_sem_skeleton(page, 5000)
    if _saiu(s):
        return
    if no_cotador(page):
        raise ErroFluxo("não consegui sair da cotação (a sessão do portal continua aberta)", "sair")
    # Fora do cotador e fora da tela de módulos (página em branco, sessão expirada): o login resolve; com
    # a sessão do portal viva, entrar() acha a tela de módulos e não digita nada. No meio de um pedido,
    # "acesso ativo" para o robô na hora (não insiste).
    entrar(s, insistir=False)
