"""Uma função por tela do portal da Bradesco (Cotação SPG).

Ordem (vídeo do corretor): portal -> Saúde e conjugado -> CNPJ -> grupos e vidas -> região -> Pular ->
Configurações (Contrato, Grupo 1) -> Calcular -> Resultado (plano + dental) -> Iniciar cotação -> Dados
complementares -> **Gerar processo** -> cálculo (página antiga) -> Imprimir (PDF). Os planos seguintes do mesmo
pedido saem de **Alterar Cotação** -> Calcular, no mesmo processo.

Pontos sem volta: "Gerar processo" (cria o Número do Processo) e o "Calcular" do Alterar Cotação (cria um cálculo
no processo). Antes de cada um o robô grava "emitindo" no registro (nucleo.estado, com fsync). O robô NUNCA clica
em "Finalizar Cálculo" nem em nada que envie proposta ou inicie contratação.
"""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path

from nucleo.credenciais import cofre as cofre_da_config
from nucleo.estado import Estado
from nucleo.modelo import ROTULOS, PlanoAlvo, PlanoVisto, ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, ErroLogin, conferir_parar, esperar_visivel, ligar_parar, visiveis
from nucleo.saidas import copiar_para_destino, nome_pdf_arquivo, nome_pdf_destino
from nucleo.texto import formatar_cnpj, norm, rx, so_digitos

from . import extracao as ex
from . import seletores as sel
from .cartao import CardPlano
from .login import entrar, logado
from .pedido import NOME_PROCESSO, Pedido, Processo
from .telas import (SessaoCaiu, escolher, escolher_combo, escolher_select, esperar, fechar_modais_ok, login_na_tela,
                    pressionado, quadro_com)


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
    avisar: object = None
    parar: object = None
    pedir_codigo: object = None
    reemitir: set = field(default_factory=set)
    lugar: object = None           # onde está a tela do cotador: a página ou o quadro (iframe) dela

    def __post_init__(self) -> None:
        ligar_parar(self.pediu_parar)

    def onde(self):
        """A página ou o quadro (iframe) da tela atual do cotador. Portal real 07/11: o cotador fica em iframes
        dentro do portal (wwws.../EEEM-EmissaoExpressa e, dentro dele, saudeexterno.../eeem-fed-simulacao-cotacao)."""
        try:
            if self.lugar is not None and not self.lugar.is_detached():
                return self.lugar
        except Exception:  # noqa: BLE001  (a página não tem is_detached: é ela mesma)
            if self.lugar is not None:
                return self.lugar
        return self.page

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
    base: Pedido
    alvos: list[PlanoAlvo]
    resolver_por_criterio: bool = False
    indice: int = 0
    razao_social: str = ""
    catalogo: list[CardPlano] = field(default_factory=list)
    card: CardPlano | None = None          # o card escolhido no Resultado (1º cálculo)
    processo: str | None = None            # Número do Processo, depois do "Gerar processo"
    resultado: ResultadoPlano | None = None
    aguardando: bool = False               # entre o clique sem volta (Gerar processo / Calcular) e ler o cálculo
    grupo_na_tela: tuple = ()              # (acomodação, coparticipação) com que o Resultado foi calculado
    processo_visto: str | None = None      # o número que a janela "Processo N gerado!" mostrou (antes do cálculo)
    terminou: bool = False

    @property
    def alvo(self) -> PlanoAlvo | None:
        return self.alvos[self.indice] if self.indice < len(self.alvos) else None

    @property
    def pedido(self) -> Pedido:
        alvo = self.alvo
        copart = (alvo.versao if alvo is not None else "") or self.base.versoes_copart[0]
        return self.base.na_versao(copart)


def com_versoes(pedido: Pedido, alvos: list[PlanoAlvo]) -> list[PlanoAlvo]:
    """Com "Com e sem", cada plano vira dois cálculos, nesta ordem: plano 1 com, plano 1 sem, plano 2 com..."""
    versoes = pedido.versoes_copart
    if len(versoes) == 1:
        return list(alvos)
    return [replace(alvo, versao=c, versao_texto=f"{c} coparticipação") for alvo in alvos for c in versoes]


def versao_no_nome(a: Andamento) -> str:
    if len(a.base.versoes_copart) == 1:
        return ""
    return f"{a.pedido.coparticipacao.upper()} COPARTICIPACAO"


def chave_processo(s: Sessao, pedido: Pedido) -> str:
    return s.estado.chave(Processo(pedido), NOME_PROCESSO, "")


def chave_calculo(s: Sessao, a: Andamento) -> str:
    return s.estado.chave(a.pedido, a.alvo.nome, a.alvo.acomodacao)


MENSAGEM_REGISTRO = {
    "pdf_ok": "já concluída em execução anterior",
    "emitindo": "o robô clicou no botão que gera o cálculo e não confirmou; confira em 'Acompanhar processos' no "
                "portal antes de liberar",
    "emitida": "cálculo gerado, PDF pendente: imprima à mão pelo processo no portal ('Acompanhar processos')",
    "pdf_manual": "cálculo gerado; imprima o PDF à mão pelo processo no portal",
}


def _resultado(a: Andamento, alvo: PlanoAlvo | None = None, **campos) -> ResultadoPlano:
    alvo = alvo or a.alvo
    p = a.base.na_versao(alvo.versao) if alvo.versao else a.pedido
    return ResultadoPlano(pedido_id=p.id, linha=p.linha, cnpj=p.cnpj, plano=alvo.nome, acomodacao=alvo.acomodacao or "",
                          razao_social=a.razao_social, versao=p.coparticipacao, **campos)


def _parar_se_pediu(s: Sessao, a: Andamento, etapa: str) -> None:
    from nucleo.navegador import Parado
    if s.pediu_parar() and not a.aguardando:
        raise Parado(etapa)


def _aviso_etapa(s: Sessao, a: Andamento, etapa: str) -> None:
    _parar_se_pediu(s, a, etapa)
    s.aviso("etapa", etapa=etapa, pedido=a.base.id, plano=a.alvo.rotulo_completo() if a.alvo else "",
            indice=a.indice, total=len(a.alvos))


# ============================ portal ============================

def _mapa(s: Sessao, etapa: str, forcar: bool = False) -> None:
    """Print da página (Mapeador do núcleo) e o HTML e a árvore de CADA quadro (iframe) do portal: o print e o HTML
    da página não mostram o que está dentro dos iframes (o cotador fica em dois, um dentro do outro). Nunca numa tela
    de login."""
    if not (s.mapa.ativo or forcar) or login_na_tela(s.page):
        return
    base = s.mapa.registrar(s.page, etapa, forcar=forcar)
    if base is None:
        return
    from nucleo.credenciais import ocultar
    for n, quadro in enumerate([f for f in s.page.frames if f is not s.page.main_frame], start=1):
        try:
            if "bradesco" not in quadro.url and "127.0.0.1" not in quadro.url and "localhost" not in quadro.url:
                continue                      # reCAPTCHA e outros de fora
            Path(f"{base}_quadro{n}.html").write_text(ocultar(quadro.content()), encoding="utf-8")
            arvore = quadro.locator("body").aria_snapshot()
            Path(f"{base}_quadro{n}.aria.txt").write_text(ocultar(f"URL: {quadro.url}\n\n{arvore}"), encoding="utf-8")
        except Exception:  # noqa: BLE001
            s.log.warning(f"mapear: o quadro {n} não foi gravado")


def _esperar_ate(condicao, segundos: float) -> bool:
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        try:
            if condicao():
                return True
        except Exception:  # noqa: BLE001
            pass
        conferir_parar()
        time.sleep(0.25)
    return False


def _cotador_aberto(s: Sessao):
    """A página ou o quadro (iframe) que mostra "Cotador de planos SPG" com o botão Saúde e conjugado."""
    from .telas import lugares
    for lugar in lugares(s.page):
        try:
            if visiveis(lugar.get_by_text(sel.TITULOS["inicio"])) and visiveis(sel.botao_produto_saude(lugar)):
                return lugar
        except Exception:  # noqa: BLE001  (quadro carregando)
            pass
    return None


# Tira o cartaz de campanha do DOM (Seguros Friday). O clique no X às vezes não chega: o Chrome põe
# "mostrar notificações" por cima, ou o Bootstrap não esconde o modal. Sem isto o locator handler do
# Playwright fica em loop e o Parar também não vale.
# Portal real 18/11: o cartaz é uma <img> (innerText sem "Friday") e o Bootstrap só chama .modal('show')
# no window.load — se o robô esperar visível, o modal nasce DEPOIS da primeira limpeza. Tira o
# .modal-aviso mesmo escondido e grava o cookie para não reabrir.
_JS_TIRAR_CAMPANHA = """() => {
  try {
    const cb = document.querySelector('.modal-aviso #checkbox-view, #checkbox-view');
    if (cb && !cb.checked) {
      cb.checked = true;
      cb.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }
  } catch (e) {}
  try { document.cookie = 'exibirModalComunicacao=false; path=/; max-age=2592000'; } catch (e) {}
  const alvos = document.querySelectorAll('.modal-aviso, [id^="modal-comunicacao"]');
  for (const el of alvos) {
    try { if (window.jQuery) window.jQuery(el).modal('hide'); } catch (e) {}
    el.classList.remove('in', 'show');
    el.style.display = 'none';
    el.setAttribute('aria-hidden', 'true');
  }
  document.querySelectorAll('.modal-backdrop').forEach(e => e.remove());
  document.body.classList.remove('modal-open');
}"""


def fechar_avisos(page, so_se_aberto: bool = False) -> None:
    """Fecha os avisos do portal que cobrem a tela (ex.: o modal de campanha "Seguros Friday").

    `so_se_aberto=True` não mexe no DOM se o cartaz não está na frente: o Angular recria o
    `.modal-aviso`, e remover o nó a cada 250 ms derrubava a página (18/11, Chrome fechou sozinho)."""
    conferir_parar("portal")
    if so_se_aberto:
        try:
            if not visiveis(sel.aviso_do_portal(page)):
                return
        except Exception:  # noqa: BLE001
            return
    try:
        for fechar in visiveis(sel.aviso_do_portal_fechar(page))[:3]:
            try:
                fechar.click(timeout=800, force=True)
            except Exception:  # noqa: BLE001  (o overlay do Chrome intercepta o clique)
                pass
            time.sleep(0.15)
    except Exception:  # noqa: BLE001
        pass
    try:
        page.evaluate(_JS_TIRAR_CAMPANHA)
    except Exception:  # noqa: BLE001
        pass
    try:
        if visiveis(sel.aviso_do_portal(page)):
            page.keyboard.press("Escape")
    except Exception:  # noqa: BLE001
        pass


def _pagina_fechou(erro: BaseException) -> bool:
    return "has been closed" in str(erro).lower() or "target page" in str(erro).lower()


def _abrir_cotacao_spg(page, tempo: float, log=None, url_cotador: str = "") -> None:
    """Painel Saúde → Cotação SPG. No RPAV3 de 15/11 o atalho do Acesso rápido existia; neste login os
    4 slots estão vazios e o submenu Angular (`bspn-fed-sub-menus-out`) fica sem itens. Depois de alguns
    segundos sem menu, abre a Cotação SPG pelo endereço da área logada (em 07/11 o deep link sem sessão
    dava 403; aqui a sessão já está em /saude/)."""
    fechar_avisos(page)
    fim = time.monotonic() + tempo
    comeco = time.monotonic()
    proximo_menu = 0.0
    proximo_aviso = 0.0
    tentou_endereco = False
    while time.monotonic() < fim:
        conferir_parar("portal")
        try:
            fechar_avisos(page, so_se_aberto=True)
            if sel.ROTA_COTADOR in sel.caminho(page) and not _erro_403(page):
                return
            if _erro_403(page):
                if log:
                    log.warning("Painel Saúde: a Cotação SPG pelo endereço deu 403; volto ao Painel Saúde.")
                page.go_back()
                tentou_endereco = True
                time.sleep(0.5)
                continue
            links = visiveis(sel.link_cotacao_spg(page))
            if links:
                if log:
                    log.info("Painel Saúde: abrindo Cotação SPG.")
                links[0].click()
                return
            n_href = 0
            try:
                n_href = page.locator("a[href*='/cotacoes/cotacao-spg']").count()
            except Exception:  # noqa: BLE001
                n_href = 0
            if time.monotonic() >= proximo_menu:
                menus = visiveis(sel.menu_cotacoes(page))
                # Cotações é um toggle: se o dropdown já mostra o item, clicar de novo FECHA o menu
                # e o robô fica no Painel Saúde com Acesso rápido vazio (portal 24/11).
                if menus:
                    if log:
                        log.info("Painel Saúde: menu Cotações.")
                    try:
                        menus[0].hover(timeout=1500)
                    except Exception:  # noqa: BLE001
                        pass
                    try:
                        menus[0].click(timeout=1500)
                    except Exception:  # noqa: BLE001
                        pass
                    proximo_menu = time.monotonic() + 2.5
                    # O item pode aparecer no mesmo ciclo (dropdown federado sem href).
                    itens = visiveis(sel.link_cotacao_spg(page))
                    if itens:
                        if log:
                            log.info("Painel Saúde: abrindo Cotação SPG.")
                        itens[0].click()
                        return
                elif (not tentou_endereco and url_cotador and time.monotonic() - comeco >= 6
                      and sel.ROTA_AREA_LOGADA in sel.caminho(page)):
                    tentou_endereco = True
                    if log:
                        log.info("Painel Saúde: o submenu Cotações não montou; abrindo a Cotação SPG pelo endereço.")
                    page.goto(url_cotador, wait_until="domcontentloaded")
                    continue
                elif log and time.monotonic() >= proximo_aviso:
                    n_menu = page.locator("[openmenuoptions]").count()
                    log.info(f"Painel Saúde: esperando Cotações (atalho={n_href}, itens de menu={n_menu}).")
                    proximo_aviso = time.monotonic() + 8
        except SessaoCaiu:
            raise
        except Exception as e:  # noqa: BLE001
            if _pagina_fechou(e):
                raise SessaoCaiu("a janela do portal foi fechada", "portal") from None
            raise
        time.sleep(0.25)
    raise ErroFluxo(
        f"não encontrei 'Cotação SPG' (Acesso rápido nem o menu Cotações) na tela em {int(tempo)}s",
        "portal")


def _erro_403(page) -> bool:
    """A página "Error 403: AuthorizationFailed" do portal (deep link sem passar pelo menu, 07/11)."""
    try:
        return bool(visiveis(page.get_by_text(sel.TEXTO_ERRO_403)))
    except Exception:  # noqa: BLE001
        return False


_VIGIADAS: list = []


def _vigiar_avisos(page) -> None:
    """Antes de qualquer clique na página, se o aviso de campanha estiver aberto, o Playwright fecha primeiro."""
    if any(p is page for p in _VIGIADAS):
        return
    try:
        page.add_locator_handler(sel.aviso_do_portal(page).first, lambda: fechar_avisos(page))
        _VIGIADAS.append(page)
    except Exception:  # noqa: BLE001
        pass


def ir_ao_cotador(s: Sessao, a: Andamento) -> None:
    """Portal real: menu SAÚDE -> submenu COTAÇÕES -> Cotação SPG (vídeo [03]). O card do Acesso rápido
    ("Conferir") é atalho só se o corretor tiver favoritado — neste login não está. A página da Cotação SPG
    abre a área de trabalho antiga num iframe (EEEM); o cotador novo sai de Ações -> "Iniciar Nova Cotação
    SPG" e abre em outro iframe ("Cotador de planos SPG")."""
    from .telas import lugares
    _aviso_etapa(s, a, "portal")
    if login_na_tela(s.page) or not logado(s.page):
        entrar(s)
    tempo = s.t("timeout_tela_ms") / 1000
    lugar = _cotador_aberto(s)
    if lugar is not None:
        s.lugar = lugar
        return
    page = s.page
    _vigiar_avisos(page)
    # Portal real 07/11: abrir a Cotação SPG direto pelo endereço dá "Error 403: AuthorizationFailed"; o caminho é o
    # menu (a home demora a carregar: "Carregando..."). Com o 403 na tela, volta à home e tenta o menu de novo.
    for tentativa in range(2):
        if sel.ROTA_COTADOR in sel.caminho(page) and not _erro_403(page):
            break
        try:
            if _erro_403(page) and tentativa:
                entrar(s)                    # sessão do robô inválida: apaga os cookies e entra de novo
                page = s.page
            if _erro_403(page) or sel.ROTA_AREA_LOGADA not in sel.caminho(page):
                s.log.warning("O portal respondeu 'AuthorizationFailed'; voltando à home do portal."
                              if _erro_403(page) else "Voltando à home do portal.")
                page.goto(s.cfg["urls"]["home"])
            fechar_avisos(page)
            esperar_visivel(sel.menu_saude(page), int(tempo * 1000), "menu SAÚDE", "portal").click()
            fechar_avisos(page)
            _mapa(s, "saude")
            _abrir_cotacao_spg(page, tempo, s.log, s.cfg.get("urls", {}).get("cotador", ""))
            break
        except ErroFluxo:
            if login_na_tela(s.page):
                raise SessaoCaiu("o portal pediu o login de novo", "portal") from None
            if tentativa:
                raise
    fim = time.monotonic() + tempo
    clicou = False
    while time.monotonic() < fim:
        conferir_parar("portal")
        fechar_avisos(s.page, so_se_aberto=True)
        lugar = _cotador_aberto(s)
        if lugar is not None:
            break
        if login_na_tela(s.page):
            raise SessaoCaiu("o portal pediu o login de novo", "portal")
        if not clicou:
            for quadro in lugares(s.page):
                try:
                    link = quadro.locator(sel.LINK_NOVA_COTACAO_SPG)
                    if link.count():
                        s.lugar = quadro
                        _mapa(s, "acompanhamento")
                        s.log.info("Cotação SPG: Ações -> Iniciar Nova Cotação SPG.")
                        link.first.evaluate("a => a.click()")     # item do menu Ações (abre ao passar o mouse)
                        clicou = True
                        break
                except Exception:  # noqa: BLE001  (quadro carregando)
                    pass
        time.sleep(0.5)
    else:
        raise ErroFluxo("o Cotador de planos SPG não abriu" + ("" if clicou else " (não achei 'Iniciar Nova Cotação "
                                                                                 "SPG' no menu Ações)"), "portal")
    s.lugar = lugar
    _mapa(s, "cotador")


def produto(s: Sessao, a: Andamento) -> None:
    sel.botao_produto_saude(s.onde()).first.click()
    s.lugar = esperar(s.page, sel.TITULOS["empresa"], s.t("timeout_tela_ms"), "tela do CNPJ", "empresa")


# ============================ cotador novo ============================

def _avancar(s: Sessao, etapa: str, nome: str = sel.TEXTO_AVANCAR, proxima: str | None = None) -> None:
    page = s.onde()
    botao = esperar_visivel(sel.botao(page, nome), 15000, f"botão {nome}", etapa)
    if not _esperar_ate(botao.is_enabled, 15):
        raise ErroFluxo(f"o botão {nome} continua desabilitado (falta preencher algo?)", etapa)
    botao.click()
    if proxima:
        try:
            s.lugar = esperar(s.page, sel.TITULOS[proxima], s.t("timeout_tela_ms"), f"tela seguinte ({proxima})",
                              etapa)
        except SessaoCaiu:
            raise
        except ErroFluxo:
            alertas = [" ".join(x.inner_text().split()) for x in visiveis(page.get_by_role("alert"))]
            raise ErroFluxo(f"depois de '{nome}' a tela não avançou" + (f" (o portal diz: {'; '.join(alertas)})"
                                                                       if alertas else ""), etapa) from None


def empresa(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "empresa"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "tela do CNPJ", etapa)
    _mapa(s, etapa)
    campo = esperar_visivel(sel.campo_cnpj(page), 15000, "campo CNPJ", etapa)
    if so_digitos(campo.input_value()) != p.cnpj:
        campo.click()
        campo.fill("")
        campo.press_sequentially(p.cnpj, delay=40)          # campo com máscara
    consultar = esperar_visivel(sel.botao(page, sel.TEXTO_CONSULTAR), 10000, "botão Consultar", etapa)
    _esperar_ate(consultar.is_enabled, 10)
    consultar.click()
    # Portal real 07/11: a razão social aparece numa caixa abaixo do campo e o "Avançar" se habilita.
    avancar = sel.botao(page, sel.TEXTO_AVANCAR)
    if not _esperar_ate(lambda: any(b.is_enabled() for b in visiveis(avancar)), 30):
        alertas = [" ".join(x.inner_text().split()) for x in visiveis(page.get_by_role("alert"))]
        raise ErroFluxo("a consulta do CNPJ não liberou o Avançar" + (f" (o portal diz: {'; '.join(alertas)})"
                                                                     if alertas else ""), etapa)
    a.razao_social = _razao_social(page)
    s.log.info(f"Empresa: {a.razao_social} | {formatar_cnpj(p.cnpj)}")
    _avancar(s, etapa, proxima="grupos")


def _razao_social(lugar) -> str:
    """A razão social que a consulta do CNPJ mostra: a caixa conhecida ou a 1ª linha depois de "Consultar"."""
    try:
        caixas = visiveis(sel.caixa_razao_social(lugar).filter(has_text=re.compile(r"\w")))
        if caixas:
            return " ".join(caixas[0].inner_text().split())
        linhas = [" ".join(l.split()) for l in lugar.locator("body").inner_text().splitlines() if l.strip()]
        depois = linhas[[norm(l) for l in linhas].index("consultar") + 1:]
        return next((l for l in depois if norm(l) not in ("voltar", "avancar", "‹ voltar", "avancar ›")), "")
    except Exception:  # noqa: BLE001
        return ""


def _texto_da_idade(idade: int) -> str:
    return "Menor de 1 ano" if idade == 0 else str(idade)


def grupos(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "grupos"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "tela dos grupos", etapa)
    escolher(page, sel.ROTULO_CATEGORIA, p.categoria, etapa)
    for rotulo in ROTULOS:
        qtd = int(p.vidas.get(rotulo, 0))
        novo = sel.FAIXAS_NOVO[rotulo]
        if rotulo in sel.TITULO_IDADES:
            if qtd:
                _idades_exatas(s, rotulo, p.idades.get(rotulo) or [])
            continue
        campo = esperar_visivel(sel.campo_faixa(page, novo), 10000, f"faixa {novo}", etapa)
        desejado = str(qtd) if qtd else ""
        if (campo.input_value() or "").strip() not in ({desejado, "0"} if not qtd else {desejado}):
            # Portal real 07/11: com fill o número aparece no campo mas o portal não conta; digitar e sair do campo conta.
            campo.click()
            campo.fill("")
            if desejado:
                campo.press_sequentially(desejado, delay=60)
            campo.press("Tab")
    _esperar_ate(lambda: _ler_total(page) in (None, p.total_vidas), 8)     # o contador do portal atualiza depois
    total = _ler_total(page)
    if total is not None and total != p.total_vidas:
        raise ErroFluxo(f"o portal conta {total} pessoa(s) no total; o pedido tem {p.total_vidas}", etapa)
    _mapa(s, etapa)
    _avancar(s, etapa, proxima="regiao")


def _ler_total(page) -> int | None:
    import re
    try:
        texto = " ".join(page.locator("body").inner_text().split())
        m = re.search(r"Pessoas\s+no\s+total\s*(\d+)", texto, re.I)
        return int(m.group(1)) if m else None
    except Exception:  # noqa: BLE001
        return None


def _idades_exatas(s: Sessao, rotulo: str, idades: list[int]) -> None:
    """00 a 18 e 59 ou mais: abre a lista ("+") e informa cada idade com a quantidade (vídeo [06]: Menor de 1 ano, 1)."""
    page, etapa = s.onde(), "grupos"
    titulo = sel.TITULO_IDADES[rotulo]
    if not visiveis(page.get_by_text(titulo)):
        esperar_visivel(sel.botao_abrir_faixa(page, sel.FAIXAS_NOVO[rotulo]), 10000,
                        f"botão para informar as pessoas de {sel.FAIXAS_NOVO[rotulo]}", etapa).click()
        esperar_visivel(page.get_by_text(titulo), 10000, f"lista de idades de {sel.FAIXAS_NOVO[rotulo]}", etapa)
    contagem: dict[int, int] = {}
    for i in idades:
        contagem[i] = contagem.get(i, 0) + 1
    # Portal real 07/11: o bloco "Indique as pessoas..." tem uma linha (div.form-59mais) por idade, com a Idade numa
    # lista ng-select (combobox pesquisável) e a Quantidade em input[formcontrolname=vidas].
    bloco = page.locator("div").filter(has=page.get_by_text(titulo)).filter(has=page.get_by_role("combobox")).last
    for n, (idade, qtd) in enumerate(sorted(contagem.items())):
        while len(visiveis(bloco.get_by_role("combobox"))) <= n:
            esperar_visivel(bloco.get_by_text(sel.LINK_MAIS_PESSOAS), 5000, "adicionar mais pessoas", etapa).click()
            time.sleep(0.3)
        combo = visiveis(bloco.get_by_role("combobox"))[n]
        _escolher_idade(page, combo, idade, rotulo, etapa)
        quantidade = visiveis(bloco.locator(sel.CAMPO_QTD_IDADE))[n]
        quantidade.click()
        quantidade.fill("")
        quantidade.press_sequentially(str(qtd), delay=60)
        quantidade.press("Tab")


def _bate_idade(texto: str, idade: int) -> bool:
    """"Menor de 1 ano" para 0; para as outras, o número (com ou sem "anos")."""
    t = norm(texto)
    if idade == 0:
        return t.startswith("menor de 1")
    return so_digitos(texto) == str(idade) and t.replace(str(idade), "").strip() in ("", "ano", "anos")


def _escolher_idade(page, combo, idade: int, rotulo: str, etapa: str) -> None:
    if (combo.evaluate("e => e.tagName") or "").lower() == "select":        # simulador / select comum
        opcoes = [" ".join(o.split()) for o in combo.locator("option").all_inner_texts()]
        texto = next((o for o in opcoes if _bate_idade(o, idade)), None)
        if texto is None:
            raise ErroDados(f"a idade {idade} não está na lista do portal ({sel.FAIXAS_NOVO[rotulo]})", etapa)
        combo.select_option(label=texto)
        return
    # ng-select (portal real 07/11): abre a lista SEM digitar (digitar "Menor" dava "Dados não encontrados") e clica na
    # opção (div.ng-option, sem papel de option). Se a lista for longa e a idade não estiver à vista, digita o número.
    opcoes_loc = page.locator(sel.OPCOES_LISTA)
    combo.click()
    for tentativa in range(2):
        fim = time.monotonic() + 5
        while time.monotonic() < fim:
            escolhida = next((o for o in visiveis(opcoes_loc) if _bate_idade(o.inner_text(), idade)), None)
            if escolhida is not None:
                escolhida.click()
                return
            time.sleep(0.25)
        if tentativa == 0 and idade:
            combo.fill("")
            combo.press_sequentially(str(idade), delay=60)
    vistas = "; ".join(" ".join(o.inner_text().split()) for o in visiveis(opcoes_loc)[:12])
    raise ErroDados(f"a idade {idade} não está na lista do portal ({sel.FAIXAS_NOVO[rotulo]}; opções: {vistas or 'nenhuma'})",
                    etapa)


def regiao(s: Sessao, a: Andamento) -> None:
    page, etapa = s.page, "regiao"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "Região Indicada", etapa)
    _mapa(s, etapa)
    _avancar(s, etapa, proxima="personalizar")


def personalizar(s: Sessao, a: Andamento) -> None:
    page, etapa = s.page, "personalizar"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "tela Personalizar", etapa)
    _mapa(s, etapa)
    _avancar(s, etapa, nome=sel.TEXTO_PULAR, proxima="configuracao")      # como o corretor: Pular


def configuracao(s: Sessao, a: Andamento) -> None:
    """Aba Contrato (adesão, cobertura, pagamento, titulares, descontos, sucursal, corretor) e aba Grupo 1
    (acomodação e coparticipação da versão da vez), depois Calcular (preços indicativos: nada oficial ainda)."""
    page, p, etapa = s.page, a.pedido, "configuracao"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "Configurações de Planos", etapa)
    sel.aba(page, "Contrato").first.click()
    escolher(page, sel.ROTULO_ADESAO, p.adesao, etapa)
    escolher(page, sel.ROTULO_COBERTURA, p.cobertura, etapa)
    escolher(page, sel.ROTULO_PAGAMENTO, "Faixa Etária", etapa)
    escolher(page, sel.ROTULO_TITULARES, "Sim" if p.mais_de_um_titular else "Não", etapa)
    _liga_desliga(page, sel.ROTULO_FOLHA, "Aplicar", p.desconto_folha, etapa)
    _desconto_comissao(page, p.desconto_comissao, etapa)
    escolher_combo(page, sel.ROTULO_SUCURSAL, p.sucursal, etapa)
    escolher_combo(page, sel.ROTULO_CORRETOR, p.codigo_corretor, etapa)
    _mapa(s, "contrato")
    sel.aba(page, "Grupo 1").first.click()
    acomodacao = a.alvo.acomodacao if a.alvo else str(s.cfg["padroes"].get("acomodacao", "Quarto"))
    escolher(page, sel.ROTULO_ACOMODACAO, acomodacao, etapa)
    escolher(page, sel.ROTULO_COPART, "Sim" if p.coparticipacao == "com" else "Não", etapa)
    a.grupo_na_tela = (acomodacao, p.coparticipacao)
    _mapa(s, "grupo")
    _avancar(s, etapa, nome=sel.TEXTO_CALCULAR, proxima="resultado")


def _liga_desliga(page, rotulo: str, nome: str, ligado: bool, etapa: str) -> None:
    from .telas import grupo_de
    grupo = grupo_de(page, rotulo)                 # portal real 07/11: <button role="radio">
    botoes = visiveis(grupo.get_by_role("button", name=rx(nome, exato=True)).or_(
        grupo.get_by_role("radio", name=rx(nome, exato=True))))
    if not botoes:
        raise ErroFluxo(f"não encontrei '{nome}' em '{rotulo}'", etapa)
    if pressionado(botoes[0]) != ligado:
        botoes[0].click()


def _desconto_comissao(page, desejado: str, etapa: str) -> None:
    from .telas import grupo_de
    grupo = grupo_de(page, sel.ROTULO_COMISSAO)
    for b in visiveis(grupo.get_by_role("button").or_(grupo.get_by_role("radio"))):
        nome = " ".join(b.inner_text().split())
        quer = bool(desejado) and norm(nome) == norm(desejado)
        if pressionado(b) != quer:
            b.click()


# ============================ resultado ============================

def _ler_card(el) -> tuple[str, object, int] | None:
    """(nome, preço, reembolso) de um card: o título tem o nome e o preço ("Nacional Plus R$ 4.565,59")."""
    try:
        titulos = visiveis(sel.titulo_do_card(el))
        texto = " ".join((titulos[0].inner_text() if titulos else "").split())
        nome = texto.split("R$")[0].strip()
        preco = ex.preco(texto)
        return (nome, preco, ex.reembolso_do_card(el.inner_text())) if nome and preco is not None else None
    except Exception:  # noqa: BLE001  (card trocando no carrossel)
        return None


def _cards_visiveis(page) -> list[tuple]:
    return [(el, lido) for el in visiveis(sel.cards_saude(page)) for lido in [_ler_card(el)] if lido]


def _girar(page, direcao: int) -> bool:
    """Clica numa das setas do carrossel de saúde (0 ou 1, na ordem da tela). True se os cards mudaram."""
    setas = sel.setas_do_carrossel(page, sel.TITULO_CARROSSEL_SAUDE)
    if setas.count() <= direcao or not setas.nth(direcao).is_visible() or not setas.nth(direcao).is_enabled():
        return False
    antes = [l for _, l in _cards_visiveis(page)]
    setas.nth(direcao).click()
    return _esperar_ate(lambda: [l for _, l in _cards_visiveis(page)] != antes, 5)


def ler_catalogo(s: Sessao, acomodacao: str) -> list[CardPlano]:
    """Todos os cards de saúde: os visíveis e os das outras páginas do carrossel (as duas setas, até acabar)."""
    page = s.onde()
    catalogo: list[CardPlano] = []
    vistos = set()

    def ler() -> None:
        for _, (nome, preco, reembolso) in _cards_visiveis(page):
            card = CardPlano(nome_card=nome, reembolso=reembolso, preco=preco, acomodacao=acomodacao)
            if card.chave() not in vistos:
                vistos.add(card.chave())
                catalogo.append(card)

    _esperar_ate(lambda: bool(_cards_visiveis(page)), 15)
    ler()
    for direcao in (0, 1):
        for _ in range(15):
            if not _girar(page, direcao):
                break
            ler()
    return catalogo


def _achar_card(s: Sessao, card: CardPlano):
    """Gira o carrossel até o card aparecer e devolve o elemento dele."""
    page = s.onde()

    def achar():
        for el, (nome, preco, reembolso) in _cards_visiveis(page):
            if norm(nome) == norm(card.nome_card) and reembolso == card.reembolso and preco == card.preco:
                return el
        return None

    el = achar()
    for direcao in (0, 1):
        for _ in range(15):
            if el is not None:
                return el
            if not _girar(page, direcao):
                break
            el = achar()
    if el is not None:
        return el
    raise ErroFluxo(f"o card {card.nome} sumiu do carrossel", "resultado")


def _marcado(el) -> bool:
    """Card selecionado: classe card-selected ou o radio marcado."""
    try:
        if "card-selected" in (el.get_attribute("class") or ""):
            return True
        radios = el.locator("input[type=radio]")
        return bool(radios.count()) and radios.first.is_checked()
    except Exception:  # noqa: BLE001
        return False


def _selecionar_card(el) -> None:
    if not _marcado(el):
        sel.radio_do_card(el).click()


def _valores_do_card(s: Sessao, el) -> dict:
    """"Valores por faixa etária" do card (para conferir a soma com o preço). Vazio se o card não mostrar."""
    try:
        botoes = visiveis(sel.botao_valores_faixa(el))
        if not botoes:
            s.log.info("O card não tem 'Valores por faixa etária' à vista; a soma por faixa não é conferida.")
            return {}
        botoes[0].click()
        _esperar_ate(lambda: bool(ex.ler_valores_card(el.inner_text())), 5)
        valores = ex.ler_valores_card(el.inner_text())
        if not valores:
            linhas = [" ".join(l.split()) for l in el.inner_text().splitlines() if "R$" in l or "a " in l][:14]
            s.log.info(f"Não li os valores por faixa etária do card; a soma por faixa não é conferida. Linhas do card: "
                       f"{linhas}")
            _mapa(s, "valores_faixa")
        return valores
    except Exception as e:  # noqa: BLE001
        s.log.info(f"Não li os valores por faixa etária do card ({type(e).__name__}); a soma por faixa não é conferida.")
        return {}


def _conferir_card(card: CardPlano, valores: dict, p: Pedido, tol: Decimal) -> list[str]:
    if not valores:
        return []
    problemas = []
    soma = Decimal("0")
    for rotulo in ROTULOS:
        q = int(p.vidas.get(rotulo, 0))
        if q and rotulo not in valores:
            problemas.append(f"o card não mostra o valor da faixa {rotulo}")
            continue
        soma += valores.get(rotulo, Decimal("0")) * q
    if not problemas and abs(soma - card.preco) > tol:
        problemas.append(f"a soma das faixas ({soma}) não bate com o preço do card ({card.preco})")
    return problemas


def _candidatos(a: Andamento, alvo: PlanoAlvo) -> list[CardPlano]:
    return [c for c in a.catalogo if norm(c.nome) == norm(alvo.nome) and norm(c.acomodacao) == norm(alvo.acomodacao)]


def resultado(s: Sessao, a: Andamento) -> None:
    """Lê o carrossel. Ensaio: registra o preço de cada plano pedido e para aqui (antes de "Iniciar cotação": nada
    oficial foi gerado). Emissão: escolhe o card do plano e o dental, confere e vai para Iniciar cotação."""
    page, etapa = s.page, "resultado"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "Resultado (Grupo 1 - Saúde)", etapa)
    _mapa(s, etapa)
    p = a.pedido
    acomodacao = a.grupo_na_tela[0]
    cab = ex.ler_cabecalho_resultado(page.locator("body").inner_text())
    if cab["cnpj"] and cab["cnpj"] != p.cnpj:
        raise ErroFluxo(f"o Resultado mostra o CNPJ {formatar_cnpj(cab['cnpj'])}; o pedido é {formatar_cnpj(p.cnpj)}",
                        etapa)
    if cab["pessoas"] is not None and cab["pessoas"] != p.total_vidas:
        raise ErroFluxo(f"o Resultado mostra {cab['pessoas']} pessoa(s); o pedido tem {p.total_vidas}", etapa)
    a.catalogo = ler_catalogo(s, acomodacao)
    if not a.catalogo:
        raise ErroFluxo("não consegui ler os planos do carrossel 'Grupo 1 - Saúde'", etapa)
    s.resultados.precos(p.id, p.cnpj, [c.visto(p.coparticipacao) for c in a.catalogo])
    s.log.info(f"Planos no portal ({acomodacao}, {p.coparticipacao} coparticipação): "
               + "; ".join(f"{c.nome} {c.preco}" for c in a.catalogo))
    if a.resolver_por_criterio and not a.alvos:
        n = int(a.base.criterio_quantidade or 1)
        escolhidos = [PlanoAlvo(c.nome, c.acomodacao) for c in sorted(a.catalogo, key=lambda c: c.preco)[:n]]
        if not s.ensaio:
            s.estado.salvar_planos_resolvidos(a.base, [x.rotulo() for x in escolhidos])
        a.alvos = com_versoes(a.base, escolhidos)
        s.log.info(f"Os {n} mais baratos: {[x.rotulo() for x in escolhidos]}")

    if s.ensaio:
        _ensaio(s, a)
        return

    a.card = None
    while a.alvo is not None:
        alvo, p = a.alvo, a.pedido
        if (norm(alvo.acomodacao), p.coparticipacao) != (norm(a.grupo_na_tela[0]), a.grupo_na_tela[1]):
            break                 # outra acomodação ou versão: o fluxo recomeça pelo cotador com ela
        candidatos = _candidatos(a, alvo)
        if len(candidatos) != 1:
            lista = "; ".join(f"{c.nome} | {c.acomodacao}" for c in a.catalogo)
            erro = (f"o plano '{alvo.rotulo()}' não está no Resultado. Disponíveis: {lista}" if not candidatos else
                    f"'{alvo.rotulo()}' aparece {len(candidatos)} vezes no Resultado")
            s.resultados.plano(_resultado(a, status="ERRO", erro=erro, etapa_erro=etapa))
            s.log.error(f"[{p.id}] {erro}")
            a.indice += 1
            continue
        if _ja_registrado(s, a):
            a.indice += 1
            continue
        card = candidatos[0]
        el = _achar_card(s, card)
        valores = _valores_do_card(s, el)
        problemas = _conferir_card(card, valores, p, s.tol())
        if problemas:
            raise ErroFluxo("o card não confere: " + "; ".join(problemas), etapa)
        _selecionar_card(el)                         # como o corretor: marca o card do plano
        if not _esperar_ate(lambda: _marcado(_achar_card(s, card)), 5):
            raise ErroFluxo(f"o card {card.nome} não ficou marcado", etapa)
        _dental(s, a.base.dental, etapa)
        a.card = card
        a.resultado = _resultado(a, preco_mensal=card.preco, valores_por_vida=valores)
        s.log.info(f"Plano escolhido: {card.nome} | {card.acomodacao} ({card.preco}), dental {a.base.dental}.")
        _avancar(s, etapa, nome=sel.TEXTO_INICIAR_COTACAO, proxima="complementares")
        return
    a.terminou = a.alvo is None


def _ensaio(s: Sessao, a: Andamento) -> None:
    """Ensaio: o preço de cada plano pedido nesta versão (coparticipação e acomodação), sem gerar nada."""
    acomodacao, versao = a.grupo_na_tela
    feitos = 0
    for i, alvo in enumerate(a.alvos):
        p = a.base.na_versao(alvo.versao) if alvo.versao else a.base
        if p.coparticipacao != versao or norm(alvo.acomodacao) != norm(acomodacao):
            continue
        candidatos = _candidatos(a, alvo)
        if len(candidatos) != 1:
            erro = f"o plano '{alvo.rotulo()}' não está no Resultado" if not candidatos else "plano repetido no Resultado"
            s.resultados.plano(_resultado(a, alvo, status="ERRO", erro=erro, etapa_erro="resultado"))
            continue
        card = candidatos[0]
        valores = _valores_do_card(s, _achar_card(s, card))
        problemas = _conferir_card(card, valores, p, s.tol())
        if problemas:
            s.resultados.plano(_resultado(a, alvo, status="ERRO", erro="o card não confere: " + "; ".join(problemas),
                                          etapa_erro="resultado", preco_mensal=card.preco))
            continue
        iof = ex.iof(card.preco, s.aliquota())
        s.resultados.plano(_resultado(a, alvo, status="ENSAIO_OK", preco_mensal=card.preco, total_sem_iof=card.preco,
                                      iof=iof, total_com_iof=card.preco + iof, valores_por_vida=valores))
        s.log.info(f"ENSAIO: {card.nome} | {card.acomodacao} ({versao} coparticipação): {card.preco} "
                   f"+ IOF {iof}. Parando antes de 'Iniciar cotação' (nada oficial foi gerado).")
        feitos += 1
    outras = [x for x in a.alvos if (x.versao or versao) != versao or norm(x.acomodacao) != norm(acomodacao)]
    if outras:
        s.log.info("No ensaio o robô lê um Resultado por pedido; sem ler agora: "
                   + ", ".join(x.rotulo_completo() for x in outras))
    a.terminou = True


def liberar_para_teste(s: Sessao, pedido: Pedido, alvos: list) -> None:
    """MODO DE TESTES (`teste_repetir`, só na calibragem; decisão do Tiago, 10/11: repetir a mesma cotação várias vezes é
    rotina de teste e o corretor não pode pedir a liberação a cada vez). Antes de olhar o registro, tira dele o processo
    e os cálculos desta empresa com estes parâmetros, qualquer que seja a situação (inclusive "emitindo"): o pedido
    gera um processo novo. É o mesmo "liberar" da tela: o item vai para "liberados" no estado.json (fica no histórico,
    com o número do processo). Roda uma vez por pedido, ANTES de gerar qualquer coisa: nunca solta o que esta execução
    acabou de registrar."""
    chaves = [chave_processo(s, pedido)]
    for alvo in alvos:
        versao = pedido.na_versao(alvo.versao) if alvo.versao else pedido
        achado = s.estado.procurar(versao, alvo)
        if achado is not None:
            chaves.append(achado[0])
    soltos = []
    for chave in dict.fromkeys(chaves):
        item = s.estado.item(chave)
        if item is not None and s.estado.liberar(chave):
            soltos.append(f"{item.get('plano') or '?'} ({item.get('status')}, processo {item.get('protocolo') or '-'})")
    if soltos:
        s.log.warning(f"[{pedido.id}] MODO DE TESTES: tirei do registro, sem conferir no portal: {'; '.join(soltos)}. "
                      "O pedido gera um processo novo. Desligue em Robôs > Bradesco antes de usar de verdade.")


def reemissao_pedida(s: Sessao, item: dict | None) -> bool:
    """O corretor pediu na tela para emitir de novo ("Emitir de novo mesmo assim", pelo número do processo que viu no
    aviso de "já emitida"). Só vale para o que está concluído (pdf_ok): processo ou cálculo incerto continua bloqueado.
    Na Bradesco, emitir de novo = um processo NOVO com os cálculos de novo (os antigos vão para "reemitidos")."""
    return (bool(item) and not s.ensaio and item.get("status") == "pdf_ok"
            and str(item.get("protocolo") or "") in s.reemitir)


def _substituir(s: Sessao, chave: str) -> str | None:
    """O protocolo a substituir no registro (emitir de novo a pedido do corretor) ou None."""
    item = s.estado.item(chave)
    return str(item["protocolo"]) if reemissao_pedida(s, item) else None


def _ja_registrado(s: Sessao, a: Andamento) -> bool:
    """2ª barreira: o cálculo deste plano (com o nome do portal) já está no registro."""
    if s.ensaio:
        return False
    chave = chave_calculo(s, a)
    if s.estado.pode_emitir(chave) or _substituir(s, chave):
        return False
    item = s.estado.item(chave)
    situacao = "PULADO" if item["status"] == "pdf_ok" else "VERIFICAR"
    s.resultados.plano(_resultado(a, status=situacao, protocolo=item.get("protocolo", ""), pdf_arquivo=item.get("pdf", ""),
                                  pdf_destino=item.get("pdf_destino", ""), pdf_nome=item.get("nome_destino", ""),
                                  erro="mesmo cálculo já registrado: "
                                       + MENSAGEM_REGISTRO.get(item["status"], item["status"])))
    return True


SEM_DENTAL = "Sem plano dental"


def _nome_do_dental(el) -> str:
    titulos = visiveis(sel.titulo_do_card(el))
    return " ".join((titulos[0].inner_text() if titulos else el.inner_text()).split()).split("R$")[0].strip()


def _dentais_marcados(s: Sessao) -> list[str]:
    """Os nomes dos cards de dental que estão marcados agora."""
    return [_nome_do_dental(el) for el in visiveis(sel.cards_dental(s.onde())) if _marcado(el)]


def _dental(s: Sessao, dental: str, etapa: str) -> None:
    """O dental do Resultado. O portal já vem com o Padrão Doc 1 marcado e, no vídeo (aos 69 s), o corretor clica em
    "Sem plano dental" antes de Iniciar cotação: o robô clica no que foi pedido e confere que só ele ficou marcado
    (com o dental errado o cálculo sai em outro layout). Grava no log o que veio marcado e o que ficou."""
    page = s.onde()
    veio = _dentais_marcados(s)
    s.log.info(f"Dental que veio marcado no portal: {', '.join(veio) or 'nenhum'}; pedido: {dental}.")
    for el in visiveis(sel.cards_dental(page)):
        if norm(_nome_do_dental(el)) != norm(dental):
            continue
        _selecionar_card(el)
        if not _esperar_ate(lambda: _marcado(el), 5):
            raise ErroFluxo(f"o dental '{dental}' não ficou marcado", etapa)
        ficou = _dentais_marcados(s)
        s.log.info(f"Dental que ficou marcado: {', '.join(ficou) or 'nenhum'}.")
        if [norm(x) for x in ficou] != [norm(dental)]:
            raise ErroFluxo(f"o dental pedido era '{dental}', mas ficou marcado: {', '.join(ficou) or 'nenhum'}", etapa)
        return
    raise ErroFluxo(f"não encontrei o dental '{dental}' no Resultado", etapa)


# ============================ dados complementares e Gerar processo ============================

def complementares(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.pedido, "complementares"
    _aviso_etapa(s, a, etapa)
    page = s.lugar = esperar(s.page, sel.TITULOS[etapa], s.t("timeout_tela_ms"), "Dados complementares", etapa)
    if not p.email_corretora:
        raise ErroDados("o portal pede o e-mail da corretora (assinatura da proposta): guarde na engrenagem do robô "
                        "Bradesco, tela Login (nada foi gerado no portal)", etapa)
    login = cofre_da_config(s.cfg, "bradesco").ler()
    if not login or not login.get("intermediario_cpf"):
        raise ErroLogin("Guarde o CPF do intermediário na engrenagem do robô Bradesco (tela Login).", "sem_credenciais")
    cpf = login["intermediario_cpf"]
    login = None

    sel.aba(page, "Corretora").first.click()
    texto = page.locator("body").inner_text() + " " + " ".join(_valores_dos_campos(page))
    if p.sucursal not in texto or p.codigo_corretor not in texto:
        s.log.warning(f"A aba Corretora não mostra a sucursal {p.sucursal} e o código {p.codigo_corretor} da "
                      "configuração; confira no mapa.")
    _preencher(page, sel.campo_email_corretora(page), p.email_corretora, "E-mail da corretora", etapa)
    if p.celular_corretora:
        _preencher(page, sel.campo_celular_corretora(page), p.celular_corretora, "Celular da corretora", etapa)
    escolher_combo(page, sel.ROTULO_ANGARIACAO, p.angariacao, etapa, exato=True)
    escolher_combo(page, sel.ROTULO_CORRETAGEM, p.corretagem, etapa, exato=True)
    _mapa(s, "corretora")

    sel.aba(page, "Intermediário").first.click()
    radios = visiveis(sel.radio(page, p.intermediario_papel))
    if radios and not radios[0].is_checked():
        radios[0].check()
    campo = esperar_visivel(sel.campo_cpf_intermediario(page), 10000,
                            "CPF do intermediário", etapa)
    if so_digitos(campo.input_value()) != so_digitos(cpf):
        campo.click()
        campo.fill("")
        campo.press_sequentially(so_digitos(cpf), delay=30)
        campo.press("Tab")
    cpf = None
    if not _esperar_ate(lambda: _nome_intermediario(page), 15):
        raise ErroFluxo("o portal não completou o nome do intermediário pelo CPF guardado (confira o CPF na "
                        "engrenagem, tela Login)", etapa)
    if p.intermediario_email:
        _preencher(page, sel.campo_email_intermediario(page), p.intermediario_email, "E-mail do intermediário", etapa)
    _mapa(s, "intermediario")

    sel.aba(page, "Transferência Bradesco").first.click()
    painel = page.get_by_role("tabpanel")
    resposta = rx("Sim" if p.transferencia else "Não", exato=True)        # portal real 07/11: radios
    botao = esperar_visivel(painel.get_by_role("radio", name=resposta).or_(painel.get_by_role("button", name=resposta)),
                            10000, "Transferência Bradesco (Sim/Não)", etapa)
    if not pressionado(botao):
        botao.click()

    sel.aba(page, "Processo").first.click()
    escolher_combo(page, sel.ROTULO_RAMO, p.ramo, etapa, digitar=p.ramo[:4], exato=True)
    _mapa(s, "processo")
    alertas = [" ".join(x.inner_text().split()) for x in visiveis(page.get_by_role("alert")) if x.inner_text().strip()]
    if alertas:
        raise ErroFluxo("o portal mostra um aviso antes de gerar o processo: " + "; ".join(alertas), etapa)
    gerar_processo(s, a)


def _valores_dos_campos(lugar) -> list[str]:
    """O que está escrito nos campos (inner_text não mostra o valor dos inputs)."""
    try:
        return lugar.evaluate("() => [...document.querySelectorAll('input, select, textarea')].map(e => e.value || '')")
    except Exception:  # noqa: BLE001
        return []


def _nome_intermediario(page) -> bool:
    """O portal completou o nome do intermediário pelo CPF (07/11: div[formcontrolname=nomeResponsavel])."""
    try:
        for el in visiveis(sel.nome_intermediario(page)):
            t = " ".join((el.inner_text() or "").split())
            if t and "encontrad" not in norm(t) and "invalid" not in norm(t):
                return True
    except Exception:  # noqa: BLE001
        pass
    return False


def _preencher(page, campo_loc, valor: str, descricao: str, etapa: str) -> None:
    campo = esperar_visivel(campo_loc, 10000, descricao, etapa)
    if campo.input_value() != valor:
        campo.click()
        campo.fill("")
        campo.press_sequentially(valor, delay=20)        # digitar: o portal valida ao digitar (Angular)
        campo.press("Tab")


def gerar_processo(s: Sessao, a: Andamento) -> None:
    """Ponto sem volta: "Gerar processo" cria o Número do Processo (válido 40 dias). Grava "emitindo" do processo
    e do 1º cálculo ANTES do clique. Se cair depois, o robô não gera outro: fica em "Conferir no portal"."""
    page, p, etapa = s.onde(), a.pedido, "complementares"
    chave_proc, chave_calc = chave_processo(s, a.base), chave_calculo(s, a)
    subst_proc, subst_calc = _substituir(s, chave_proc), _substituir(s, chave_calc)
    if not subst_proc and not s.estado.pode_emitir(chave_proc):
        raise ErroFluxo("o registro diz que o processo desta empresa já foi gerado; não gero outro", etapa)
    if not subst_calc and not s.estado.pode_emitir(chave_calc):
        raise ErroFluxo("o registro diz que este cálculo já foi feito; não gero outro processo", etapa)
    botao = esperar_visivel(sel.botao(page, sel.TEXTO_GERAR_PROCESSO), 10000, "botão Gerar processo", etapa)
    de_novo = f" (emitindo de novo a pedido do corretor; antes: processo {subst_proc})" if subst_proc else ""
    s.estado.registrar(chave_proc, Processo(a.base), NOME_PROCESSO, "", "emitindo", obs="clicou Gerar processo" + de_novo,
                       pasta_destino=p.pasta_destino, substituir_protocolo=subst_proc)
    s.estado.registrar(chave_calc, p, a.alvo.nome, a.alvo.acomodacao, "emitindo",
                       obs="1º cálculo (Gerar processo)" + de_novo, pasta_destino=p.pasta_destino,
                       substituir_protocolo=subst_calc)
    if subst_proc:
        s.log.info(f"Emitindo de novo a pedido do corretor: um processo novo (o anterior, {subst_proc}, fica no "
                   "histórico).")
    a.aguardando = True
    s.log.info(f"Gerando o processo da empresa {formatar_cnpj(p.cnpj)} com {a.alvo.rotulo_completo()}...")
    botao.click()


# ============================ cálculo (página antiga) e PDF ============================

def calculo(s: Sessao, a: Andamento, primeiro: bool) -> None:
    page, p, etapa = s.page, a.pedido, "calculo"
    _aviso_etapa(s, a, etapa)
    modais = _esperar_calculo(s, a, etapa)
    lugar = s.lugar = _quadro_do_calculo(s, a, etapa, modais)
    page = s.page
    texto = lugar.locator("body").inner_text()
    numero = ex.ler_numero_processo(texto)
    if not numero:
        raise ErroFluxo("não consegui ler o Número do Processo no cálculo", etapa)
    no_modal = a.processo_visto or next((ex.ler_numero_processo(t) for t in modais if ex.ler_numero_processo(t)), None)
    if no_modal and no_modal != numero:
        raise ErroFluxo(f"o modal diz processo {no_modal} e o cálculo mostra {numero}", etapa)
    chave_calc = chave_calculo(s, a)
    if primeiro:
        a.processo = numero
        s.estado.registrar(chave_processo(s, a.base), Processo(a.base), NOME_PROCESSO, "", "pdf_ok",
                           obs="processo gerado", protocolo=numero)
        s.log.info(f"Processo gerado: {numero} (válido por 40 dias).")
    elif numero != a.processo:
        raise ErroFluxo(f"o cálculo mostra o processo {numero}; o pedido está no processo {a.processo}", etapa)
    nome_destino = nome_pdf_destino(s.cfg, p.cnpj, numero, a.alvo.nome,
                                    a.alvo.acomodacao if _acomodacao_no_nome(a) else "", versao=versao_no_nome(a))
    s.estado.registrar(chave_calc, p, a.alvo.nome, a.alvo.acomodacao, "emitida", protocolo=numero,
                       nome_destino=nome_destino)
    a.aguardando = False
    _mapa(s, f"calculo_{a.indice + 1}")

    r = a.resultado or _resultado(a)
    r.protocolo, r.pdf_nome = numero, nome_destino
    perfil = ex.ler_perfil(texto)
    tabela, totais = ex.ler_tabela_calculo(texto), ex.ler_totais(texto)
    problemas = ex.conferir_calculo(tabela, p.vidas, totais, s.aliquota(), s.tol())
    base_alvo, _ = ex.separar_reembolso(a.alvo.nome)
    if perfil["plano"] and norm(perfil["plano"]) != norm(base_alvo):
        problemas.append(f"o cálculo é do plano '{perfil['plano']}', esperado '{base_alvo}'")
    if perfil["coparticipacao"] and ex.copart_do_texto(perfil["coparticipacao"]) != p.coparticipacao:
        problemas.append(f"o cálculo está com coparticipação '{perfil['coparticipacao']}', esperado {p.coparticipacao}")
    if primeiro and a.card is not None and totais.get("premio") is not None and abs(totais["premio"] - a.card.preco) > s.tol():
        problemas.append(f"o Prêmio Saúde ({totais['premio']}) não é o preço do card ({a.card.preco})")
    r.total_sem_iof, r.iof, r.total_com_iof = totais.get("premio"), totais.get("iof"), totais.get("total1")
    r.preco_mensal = r.preco_mensal or totais.get("premio")
    r.valores_por_vida = r.valores_por_vida or {k: v["valor_vida"] for k, v in tabela.items()}
    a.resultado = r
    layout = ex.layout_do_calculo(texto)
    s.log.info(f"Layout da página do cálculo: {layout} (dental pedido: {p.dental}).")
    if norm(p.dental) == norm(SEM_DENTAL) and layout != "conjugado":
        # Vídeo: com "Sem plano dental" a página tem Saúde Conjugado, "Totais Saúde" e "Totais Conjugado". Sem o
        # "Totais Saúde" o dental provavelmente ficou marcado: não imprime, o PDF sairia no layout errado.
        raise ErroFluxo(f"a página do cálculo do processo {numero} não tem 'Totais Saúde' (layout: {layout}), mas o "
                        f"dental pedido é '{SEM_DENTAL}': o dental pode ter ficado marcado. O robô não imprimiu o PDF; "
                        "confira o processo no portal", etapa)
    if problemas:
        raise ErroFluxo(f"o cálculo do processo {numero} não confere com o pedido: " + "; ".join(problemas)
                        + ". O PDF não foi para a pasta do cliente", etapa)
    s.log.info(f"Cálculo {a.alvo.rotulo_completo()}: prêmio {r.total_sem_iof} + IOF {r.iof} = {r.total_com_iof} "
               f"(código {perfil['codigo'] or '-'}).")

    fechar_modais_ok(page, 2)       # a caixa "válido por 40 dias" (#box-alertbox) cobre o Imprimir (portal real 07/11)
    _identificar_calculo(s, lugar, a, etapa)
    arquivo = imprimir_pdf(s, lugar, p.cnpj, numero, f"{a.alvo.nome} {a.alvo.acomodacao} {versao_no_nome(a)}")
    destino = ""
    if p.pasta_destino:
        try:
            destino = copiar_para_destino(arquivo, p.pasta_destino, nome_destino,
                                          bool(s.cfg["saida"].get("substituir_no_destino", True)), s.log)
        except Exception as e:  # noqa: BLE001
            r.erro = f"PDF salvo em {arquivo}, mas a cópia para a pasta do cliente falhou: {e}"
            s.log.warning(r.erro)
    s.estado.registrar(chave_calc, p, a.alvo.nome, a.alvo.acomodacao, "pdf_ok", pdf=str(arquivo), pdf_destino=destino,
                       nome_destino=nome_destino)
    r.status, r.pdf_arquivo, r.pdf_destino = "OK", str(arquivo), destino
    s.resultados.plano(r)
    a.indice += 1
    a.resultado, a.card = None, None
    if a.alvo is None:
        a.terminou = True


def _responde(pagina) -> str | None:
    """None se a aba responde; senão o nome do erro (ex.: TargetClosedError). Leitura curta (1,5 s), sem tocar em valores."""
    try:
        pagina.locator("body").first.get_attribute("class", timeout=1500)
        return None
    except Exception as e:  # noqa: BLE001
        return type(e).__name__


def _diagnostico_das_abas(s: Sessao) -> str:
    """O que o robô sabe das abas do navegador (para o log quando a tela some do alcance): se fechou, o caminho e se
    responde. Só caminhos e nomes de erro, nunca o texto da página."""
    from urllib.parse import urlparse
    try:
        paginas = list(s.contexto.pages)
    except Exception as e:  # noqa: BLE001
        return f"(não consegui listar as abas: {type(e).__name__})"
    partes = []
    for i, pg in enumerate(paginas):
        try:
            fechada = pg.is_closed()
            caminho = urlparse(pg.url).path[:70] or "/"
        except Exception as e:  # noqa: BLE001
            fechada, caminho = type(e).__name__, "?"
        resposta = "fechada" if fechada is True else (_responde(pg) or "responde")
        partes.append(f"aba {i}{' (a do robô)' if pg is s.page else ''}: {caminho} {resposta}")
    return " | ".join(partes) or "(nenhuma aba)"


def _garantir_pagina(s: Sessao) -> None:
    """Se a aba do robô fechou ou parou de responder (10/11: depois de "Processo N gerado!" os quadros da aba passaram a
    dar TargetClosedError com o cálculo aparecendo na tela e o aviso OK por cima), segue em outra aba que responda e
    grava no log o que viu das abas."""
    try:
        fechada = s.page.is_closed()
        erro = "fechada" if fechada else _responde(s.page)
    except Exception:  # noqa: BLE001
        return
    if erro is None:
        s._abas_mortas = False
        return
    if not getattr(s, "_abas_mortas", False):
        s._abas_mortas = True
        s.log.warning(f"A aba do robô não responde ({erro}). Abas: {_diagnostico_das_abas(s)}")
    try:
        vivas = [p for p in s.contexto.pages if p is not s.page and not p.is_closed() and _responde(p) is None]
    except Exception:  # noqa: BLE001
        return
    if vivas:
        from urllib.parse import urlparse
        s.page, s.lugar = vivas[-1], None
        s._abas_mortas = False
        s.log.info(f"O robô seguiu em outra aba, que responde ({urlparse(s.page.url).path[:80] or '/'}).")


def _parar_na_espera(s: Sessao, a: Andamento, etapa: str, inicio: float) -> None:
    """O corretor clicou em Parar enquanto o robô espera a página do cálculo. É um ponto seguro DEPOIS que o número do
    processo foi guardado no registro (o processo já existe e o robô só está esperando a página; 10/11: esperou mais de
    2 min sem deixar parar). Antes de ter o número, continua sem parar (regra 5). O pedido fica em "Conferir no portal"
    com o número do processo."""
    if a.processo_visto and s.pediu_parar() and time.monotonic() - inicio > 3:
        from nucleo.navegador import Parado
        s.log.warning(f"Parar pedido enquanto esperava a página do cálculo do processo {a.processo_visto}: parando "
                      "(o processo existe no portal; o PDF não foi gerado).")
        raise Parado(etapa)


def _quadro_do_calculo(s: Sessao, a: Andamento, etapa: str, modais: list[str]):
    """O quadro com a página do cálculo. O aviso "válido por 40 dias" (OK) pode aparecer a qualquer momento depois da
    página (10/11: ficou cobrindo a tela com o robô parado): fecha o que aparecer enquanto espera, pelo tempo da
    emissão (o portal levou mais de 100 s para mostrar a página), e grava no log o que a tela mostra a cada 20 s."""
    from .telas import _visivel, descrever, lugares
    inicio = time.monotonic()
    fim = inicio + s.t("timeout_emissao_ms") / 1000
    avisou = 0
    while True:
        _garantir_pagina(s)
        _parar_na_espera(s, a, etapa, inicio)
        modais += fechar_modais_ok(s.page, 1)
        for lugar in lugares(s.page):
            if _visivel(lugar.get_by_text(sel.TEXTO_CALCULO)):
                modais += fechar_modais_ok(s.page, 2)
                return lugar
        if login_na_tela(s.page):
            raise SessaoCaiu("o portal pediu o login de novo (a sessão acabou)", etapa)
        espera = int(time.monotonic() - inicio)
        if espera // 20 > avisou:
            avisou = espera // 20
            s.log.info(f"Esperando a página do cálculo ({espera} s). Tela: {descrever(s.page)} | "
                       f"Abas: {_diagnostico_das_abas(s)}")
        if time.monotonic() >= fim:
            raise ErroFluxo(f"não encontrei 'Cálculo de Seguro SPG' na tela em {s.t('timeout_emissao_ms') // 1000}s. "
                            f"Tela: {descrever(s.page)}", etapa)
        time.sleep(0.3)


def _numero_no_texto(lugar) -> str | None:
    """O Número do Processo da página do cálculo (só aparece com a página carregada de verdade). Só vale com o título
    "Cálculo de Seguro SPG" no mesmo texto: outras páginas do portal também falam em "Processo N" (10/11: a espera
    acabava cedo demais e o robô desistia em 60 s de uma página que o portal levou mais de 100 s para mostrar)."""
    try:
        texto = lugar.locator("body").inner_text(timeout=3000)
        return ex.ler_numero_processo(texto) if sel.TEXTO_CALCULO.search(texto or "") else None
    except Exception:  # noqa: BLE001
        return None


def _guardar_numero(s: Sessao, a: Andamento, numero: str) -> None:
    """Grava o número do processo no registro assim que o portal o mostra (janela "Processo N gerado!"): se a página do
    cálculo não carregar, o processo não fica no registro sem número (item incerto sem como identificar)."""
    if a.processo_visto == numero:
        return
    a.processo_visto = numero
    obs = f"o portal mostrou 'Processo {numero} gerado!'"
    s.estado.registrar(chave_processo(s, a.base), Processo(a.base), NOME_PROCESSO, "", "emitindo", obs=obs,
                       protocolo=numero)
    s.estado.registrar(chave_calculo(s, a), a.pedido, a.alvo.nome, a.alvo.acomodacao, "emitindo", obs=obs,
                       protocolo=numero)
    s.log.info(f"O portal gerou o processo {numero}; número guardado no registro.")


def _esperar_calculo(s: Sessao, a: Andamento, etapa: str) -> list[str]:
    """Espera a página do cálculo. No caminho (portal real), janelas informativas com OK cobrem a tela: o robô fecha
    (só OK/Entendi/Fechar), guarda um mapa da primeira e, na janela "Processo N gerado!", o número do processo.
    A página só conta como pronta com a linha "Número do Processo" (o título pode aparecer antes, 10/11). Passou de
    25 s sem ela: descreve a tela no log e guarda um mapa, para calibrar. Devolve o texto das janelas fechadas."""
    from .telas import descrever, lugares
    textos: list[str] = []
    inicio = time.monotonic()
    fim = inicio + s.t("timeout_emissao_ms") / 1000
    mapeou = descreveu = False
    while time.monotonic() < fim:
        _garantir_pagina(s)
        _parar_na_espera(s, a, etapa, inicio)
        for lugar in lugares(s.page):
            try:
                if _numero_no_texto(lugar) and not visiveis(sel.botoes_ok(lugar)):
                    return textos
            except Exception:  # noqa: BLE001  (quadro carregando)
                pass
        if login_na_tela(s.page):
            raise SessaoCaiu("o portal pediu o login de novo depois do clique", etapa)
        for lugar in lugares(s.page):
            try:
                for ok in visiveis(sel.botoes_ok(lugar))[:1]:
                    texto = " ".join((lugar.locator("body").inner_text(timeout=3000) or "").split())
                    numero = ex.ler_processo_gerado(texto)
                    if numero:
                        _guardar_numero(s, a, numero)
                    if not mapeou:
                        _mapa(s, "janela_ok", forcar=True)
                        mapeou = True
                    caixa = ok.locator("xpath=ancestor::*[@role='dialog' or @id='box-alertbox' or contains(@class,'modal')][1]")
                    resumo = " ".join((caixa.inner_text(timeout=2000) if caixa.count() else texto).split())[:300]
                    s.log.info(f"Janela do portal fechada com '{' '.join(ok.inner_text(timeout=2000).split()) or 'OK'}': "
                               f"{resumo}")
                    textos.append(resumo)
                    ok.click(timeout=5000)
                    time.sleep(0.5)
            except Exception:  # noqa: BLE001
                pass
        if not descreveu and time.monotonic() - inicio > 25:
            descreveu = True
            s.log.warning(f"O cálculo ainda não apareceu depois de 25 s. Tela: {descrever(s.page)}")
            _mapa(s, "espera_calculo", forcar=True)
        time.sleep(0.4)
    s.log.error(f"A página do cálculo não apareceu em {s.t('timeout_emissao_ms') // 1000}s. Tela: {descrever(s.page)}")
    raise ErroFluxo(f"a página do cálculo não apareceu em {s.t('timeout_emissao_ms') // 1000}s depois do clique"
                    + (f" (o portal gerou o processo {a.processo_visto})" if a.processo_visto else ""), etapa)


def _acomodacao_no_nome(a: Andamento) -> bool:
    """O mesmo plano em Quarto e em Enfermaria no pedido: a acomodação entra no nome do PDF."""
    return len({norm(x.acomodacao) for x in a.alvos if norm(x.nome) == norm(a.alvo.nome)}) > 1


def identificador_do_calculo(s: Sessao, a: Andamento) -> str:
    """O que o corretor digita em "Identifique o cálculo a ser armazenado" (vídeo: COM COPAY; sai no cabeçalho do
    PDF): a versão do cálculo, "COM COPAY" ou "SEM COPAY" (mudável na engrenagem). O portal aceita até 60 letras."""
    padroes = s.cfg.get("padroes", {})
    com = a.pedido.coparticipacao == "com"
    padrao = "COM COPAY" if com else "SEM COPAY"
    return (str(padroes.get("identificador_com" if com else "identificador_sem") or "").strip() or padrao)[:60]


def _identificar_calculo(s: Sessao, lugar, a: Andamento, etapa: str) -> None:
    """Portal real 07/11: o Imprimir exige o identificador do cálculo preenchido (no vídeo ficou vazio)."""
    campos = visiveis(sel.campo_identificador_calculo(lugar))
    if not campos:
        s.log.warning("Não achei o campo 'Identifique o cálculo a ser armazenado'; seguindo para o Imprimir.")
        return
    nome = identificador_do_calculo(s, a)
    if (campos[0].input_value() or "").strip() == nome:
        return
    campos[0].click()
    campos[0].fill("")
    campos[0].press_sequentially(nome, delay=15)
    campos[0].press("Tab")
    s.log.info(f"Identificador do cálculo: {nome}")


def _alerta_do_portal(s: Sessao) -> str | None:
    """Se uma caixa de aviso das páginas antigas estiver aberta, fecha (OK) e devolve o texto dela."""
    from .telas import lugares
    for lugar in lugares(s.page):
        try:
            for caixa in visiveis(sel.caixa_alerta(lugar))[:1]:
                texto = " ".join((caixa.inner_text() or "").split()).replace(" OK", "").strip()
                fechar_modais_ok(s.page, 1)
                return texto
        except Exception:  # noqa: BLE001
            pass
    return None


def imprimir_pdf(s: Sessao, lugar, cnpj: str, processo: str, plano: str) -> Path:
    """"Imprimir" abre uma janela (about:blank) com o cálculo; o robô salva essa janela como PDF, como o corretor
    faz com "Salvar como PDF" (vídeo [23])."""
    pasta = Path(s.cfg["saida"]["pasta"]) / "pdfs"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nome_pdf_arquivo(s.cfg, cnpj, processo, plano)
    antes = list(s.contexto.pages)
    esperar_visivel(sel.botao(lugar, sel.TEXTO_IMPRIMIR), 10000, "botão Imprimir", "calculo").click()
    # A janela "Imprimir" abre (about:blank) ou o portal responde numa caixa de aviso (ex.: "O identificador do
    # cálculo deve ser preenchido."): nesse caso para na hora, com o texto do portal.
    janela = None
    fim = time.monotonic() + int(s.cfg["execucao"].get("timeout_download_ms", 120000)) / 1000
    while time.monotonic() < fim and janela is None:
        conferir_parar("calculo")
        novas = [p for p in s.contexto.pages if p not in antes and not p.is_closed()]
        if novas:
            janela = novas[-1]
            break
        aviso = _alerta_do_portal(s)
        if aviso:
            raise ErroFluxo(f"o Imprimir não abriu: o portal respondeu \"{aviso}\"", "calculo")
        time.sleep(0.3)
    if janela is None:
        raise ErroFluxo("o botão Imprimir não abriu a janela do cálculo", "calculo")
    try:
        janela.wait_for_load_state("domcontentloaded")
        _esperar_ate(lambda: processo in so_digitos(janela.locator("body").inner_text())
                     or bool(ex.ler_tabela_calculo(janela.locator("body").inner_text())), 15)
        _descrever_janela(s, janela)
        dados = _pdf_da_janela(s, janela)
        _mapa_da_janela(s, janela)
    finally:
        try:
            janela.close()
        except Exception:  # noqa: BLE001
            pass
    if not dados.startswith(b"%PDF") or len(dados) < 500:
        raise ErroFluxo(f"o PDF da janela Imprimir não parece válido ({len(dados)} bytes)", "calculo")
    destino.write_bytes(dados)
    s.log.info(f"PDF salvo: {destino}")
    return destino


def _descrever_janela(s: Sessao, janela) -> None:
    """No log: o layout e as primeiras linhas da janela "Imprimir" (o que vira PDF). Só leitura, rápido: a janela pode
    fechar sozinha (o portal chama window.print), então nada demorado antes do PDF."""
    try:
        texto = janela.locator("body").inner_text()
        linhas = [" ".join(l.split()) for l in texto.splitlines() if l.strip()][:3]
        s.log.info(f"Janela Imprimir: layout {ex.layout_do_calculo(texto)}; começa com: {' / '.join(linhas)[:120]}")
    except Exception as e:  # noqa: BLE001
        s.log.warning(f"Não consegui descrever a janela Imprimir ({type(e).__name__})")


def _mapa_da_janela(s: Sessao, janela) -> None:
    """Print, HTML e árvore da janela "Imprimir" (sempre), logo depois de o PDF sair dela e antes de fechar: é o que se
    compara com o PDF do vídeo. Depois do PDF, para o print demorado não arriscar a janela."""
    try:
        s.mapa.registrar(janela, "calculo_imprimir", forcar=True)
    except Exception as e:  # noqa: BLE001
        s.log.warning(f"mapear: a janela Imprimir não foi gravada ({type(e).__name__})")


def _pdf_da_janela(s: Sessao, janela) -> bytes:
    try:
        return janela.pdf(format="A4", print_background=True)
    except Exception:  # noqa: BLE001  (com a janela do portal visível o Chromium não gera PDF por aqui)
        pass
    try:
        cdp = s.contexto.new_cdp_session(janela)
        r = cdp.send("Page.printToPDF", {"printBackground": True, "paperWidth": 8.27, "paperHeight": 11.69})
        return base64.b64decode(r["data"])
    except Exception as e:  # noqa: BLE001
        raise ErroFluxo("não consegui salvar a janela Imprimir como PDF (com 'Mostrar a janela do portal' ligado o "
                        f"Chromium pode recusar: desligue e tente de novo) ({type(e).__name__})", "calculo") from None


# ============================ Alterar Cotação (página antiga) ============================

def _opcao_acomodacao(opcoes: list[str], alvo: PlanoAlvo) -> str | None:
    """A acomodação do formulário antigo para o plano: "Múltiplo N" para o card de reembolso Nx; sem multiplicador,
    a opção de quarto (no vídeo, "Quarto Privativo" para o Nacional III) ou a de enfermaria."""
    _, reembolso = ex.separar_reembolso(alvo.nome)
    if reembolso:
        return next((o for o in opcoes if norm(o).replace(" ", "") in (f"multiplo{reembolso}", f"multiplo{reembolso}x")),
                    None)
    palavra = "quarto" if norm(alvo.acomodacao) == "quarto" else "enfermaria"
    return next((o for o in opcoes if norm(o).startswith(palavra)), None)


def alterar(s: Sessao, a: Andamento) -> None:
    """Próximo plano ou versão no MESMO processo: Alterar Cotação -> troca plano, acomodação e coparticipação ->
    Calcular. O "Calcular" cria um cálculo no processo: "emitindo" antes do clique."""
    page, p, etapa = s.page, a.pedido, "alterar"
    _aviso_etapa(s, a, etapa)
    lugar = quadro_com(page, sel.TEXTO_CALCULO, s.t("timeout_tela_ms"), "Cálculo de Seguro SPG", etapa)
    fechar_modais_ok(page, 2)
    sel.botao(lugar, sel.TEXTO_ALTERAR_COTACAO).first.click()
    lugar = s.lugar = quadro_com(page, sel.TEXTO_ALTERAR, s.t("timeout_tela_ms"), "formulário Dados da Cotação",
                                 etapa)
    # Quadro 24: logo depois de abrir, a razão social e a UF aparecem vazias por um instante.
    if a.razao_social and not _esperar_ate(
            lambda: any(norm(v) == norm(a.razao_social) for v in _valores_dos_campos(lugar)), 15):
        s.log.warning("O Alterar Cotação não mostrou a razão social em 15 s; seguindo (confira no mapa).")
    _mapa(s, f"alterar_form_{a.indice + 1}")          # antes de mexer em qualquer campo: calibra os seletores
    texto = lugar.locator("body").inner_text()
    if p.cnpj not in so_digitos(texto) and p.cnpj not in so_digitos(lugar.content()):
        raise ErroFluxo(f"o formulário do Alterar Cotação não mostra o CNPJ {formatar_cnpj(p.cnpj)}", etapa)
    base_alvo, _ = ex.separar_reembolso(a.alvo.nome)
    escolher_select(lugar, sel.ROTULO_PLANO_ANTIGO, base_alvo, etapa)
    time.sleep(0.4)                                  # a lista de acomodação muda com o plano
    campo_acomod = sel.select_antigo(lugar, sel.ROTULO_ACOMODACAO_ANTIGO).first
    opcoes = [" ".join(o.split()) for o in campo_acomod.locator("option").all_inner_texts()]
    acomod = _opcao_acomodacao(opcoes, a.alvo)
    if acomod is None:
        raise ErroDados(f"o plano {a.alvo.rotulo()} não tem acomodação correspondente no Alterar Cotação "
                        f"(opções: {'; '.join(opcoes)})", etapa)
    campo_acomod.select_option(label=acomod)
    campo_copart = sel.select_antigo(lugar, sel.ROTULO_COPART_ANTIGO).first
    copart_opcoes = [" ".join(o.split()) for o in campo_copart.locator("option").all_inner_texts()]
    if p.coparticipacao == "com":
        quer = str(s.cfg["padroes"].get("copart_percentual", "30%"))
        escolha = next((o for o in copart_opcoes if norm(o).replace(" ", "") == norm(quer).replace(" ", "")), None)
    else:
        escolha = next((o for o in copart_opcoes if ex.copart_do_texto(o) == "sem"), None)
    if escolha is None:
        raise ErroFluxo(f"a coparticipação '{p.coparticipacao}' não está na lista do Alterar Cotação "
                        f"(opções: {'; '.join(copart_opcoes)})", etapa)
    campo_copart.select_option(label=escolha)
    for rotulo in ROTULOS:
        antigo = sel.FAIXAS_ANTIGO[rotulo]
        campos = visiveis(lugar.get_by_role("textbox", name=rx(antigo, exato=True)))
        if not campos:
            continue
        valor = int(so_digitos(campos[0].input_value()) or 0)
        if valor != int(p.vidas.get(rotulo, 0)):
            raise ErroFluxo(f"o Alterar Cotação está com {valor} vida(s) em {antigo}; o pedido tem "
                            f"{p.vidas.get(rotulo, 0)}", etapa)
    _mapa(s, f"alterar_{a.indice + 1}")
    if _ja_registrado(s, a):
        a.indice += 1
        raise ErroFluxo("este cálculo já estava no registro", etapa)
    chave = chave_calculo(s, a)
    subst = _substituir(s, chave)
    botao = esperar_visivel(sel.botao(lugar, sel.TEXTO_CALCULAR), 10000, "botão Calcular", etapa)
    s.estado.registrar(chave, p, a.alvo.nome, a.alvo.acomodacao, "emitindo",
                       obs=f"Alterar Cotação -> Calcular (processo {a.processo})"
                           + (f" (de novo; antes: processo {subst})" if subst else ""),
                       pasta_destino=p.pasta_destino, substituir_protocolo=subst)
    a.aguardando = True
    a.resultado = _resultado(a)
    s.log.info(f"Calculando {a.alvo.rotulo_completo()} no processo {a.processo} ({base_alvo}, {acomod}, {escolha})...")
    botao.click()


# ============================ sair ============================

def sair_do_portal(s: Sessao, prazo_s: float = 30) -> bool:
    """Logout pelo menu do usuário (nome da corretora no topo) -> Sair. Só com o robô parado."""
    page = s.page
    if login_na_tela(page):
        return True
    if not logado(page):
        return False
    botoes = visiveis(sel.link_sair(page))
    if not botoes:
        for menu in visiveis(sel.menu_usuario(page))[:1]:
            menu.click()
            _esperar_ate(lambda: bool(visiveis(sel.link_sair(page))), min(prazo_s, 5))
        botoes = visiveis(sel.link_sair(page))
    if not botoes:
        raise ErroFluxo("não achei 'Sair' no menu do portal", "sair")
    botoes[0].click()
    return _esperar_ate(lambda: login_na_tela(s.page), prazo_s)
