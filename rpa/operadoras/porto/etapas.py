"""Uma função por tela do portal da Porto (Saúde PME).

Ordem: login + SUSEP -> Criar nova cotação -> Dados iniciais -> Produto e vidas -> Comissão ->
Selecionar o plano. O ENSAIO PARA AQUI. "Gerar orçamento" (grava emitindo ANTES do clique) só com
emissão liberada e o corretor em Gerar. Nunca Elaborar proposta, Adicionar à Proposta, Remissão,
Editar ou Duplicar orçamento — não há clique para eles aqui.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from nucleo.modelo import ROTULOS, PlanoAlvo, ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, Parado, esperar_visivel, ligar_parar
from nucleo.saidas import copiar_para_destino, nome_pdf_arquivo, nome_pdf_destino
from nucleo.texto import formatar_cnpj, norm

from . import extracao as ex
from . import seletores as sel
from .pedido import Pedido
from .telas import (
    _visivel, cotador, empresa_preenchida, esperar_ate, fechar_overlays,
    login_na_tela, saiu_de_dados_iniciais, texto_do_cotador,
)


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

    def __post_init__(self) -> None:
        ligar_parar(self.pediu_parar)

    def aviso(self, tipo: str, **dados) -> None:
        if self.avisar:
            try:
                self.avisar(tipo, **dados)
            except Exception:  # noqa: BLE001
                pass

    def pediu_parar(self) -> bool:
        try:
            return bool(self.parar and self.parar())
        except Exception:  # noqa: BLE001
            return False

    def tol(self) -> Decimal:
        return Decimal(str(self.cfg["conferencias"]["tolerancia_reais"]))

    def t(self, nome: str) -> int:
        return int(self.cfg["execucao"][nome])

    def pode_gerar(self) -> bool:
        """Gerar orçamento só fora do ensaio e com emissão liberada (nunca o padrão)."""
        return (not self.ensaio) and bool(self.cfg.get("emissao_liberada"))


@dataclass
class Andamento:
    base: Pedido
    alvos: list[PlanoAlvo]
    indice: int = 0
    razao_social: str = ""
    numero: str | None = None
    resultado: ResultadoPlano | None = None
    valores: dict = field(default_factory=dict)
    subtotal: Decimal | None = None
    taxa: Decimal | None = None
    iof: Decimal | None = None
    total: Decimal | None = None
    aguardando: bool = False
    recuperar: list = field(default_factory=list)
    substituir: dict = field(default_factory=dict)

    @property
    def alvo(self) -> PlanoAlvo | None:
        return self.alvos[self.indice] if self.indice < len(self.alvos) else None

    @property
    def pedido(self) -> Pedido:
        return self.base


def com_versoes(pedido: Pedido, planos: list[PlanoAlvo]) -> list[PlanoAlvo]:
    if len(pedido.versoes_copart) == 1:
        return planos
    saida = []
    for alvo in planos:
        for copart in pedido.versoes_copart:
            saida.append(PlanoAlvo(nome=alvo.nome, acomodacao=alvo.acomodacao, versao=copart,
                                   versao_texto=f"{copart} coparticipação"))
    return saida


def chave_cotacao(s: Sessao, pedido: Pedido, alvo: PlanoAlvo) -> str:
    p = pedido.na_versao(alvo.versao) if alvo.versao else pedido
    return s.estado.chave(p, alvo.nome, alvo.acomodacao or p.acomodacao)


MENSAGEM_REGISTRO = {
    "pdf_ok": "já gerada em execução anterior",
    "emitindo": "o robô clicou em Gerar orçamento e não confirmou o número; ele procura a cotação na lista pelo CNPJ",
    "emitida": "cotação calculada no portal, PDF pendente",
    "pdf_manual": "cotação calculada; baixe o PDF à mão pela lista no portal",
}


def _resultado(a: Andamento, alvo: PlanoAlvo | None = None, **campos) -> ResultadoPlano:
    alvo = alvo or a.alvo
    return ResultadoPlano(
        pedido_id=a.base.id, linha=a.base.linha, cnpj=a.base.cnpj,
        plano=alvo.nome if alvo else "", acomodacao=(alvo.acomodacao or a.base.acomodacao) if alvo else "",
        razao_social=a.razao_social, versao=(alvo.versao if alvo and alvo.versao else a.base.coparticipacao),
        **campos)


def _mapa(s: Sessao, etapa: str, forcar: bool = False) -> None:
    try:
        s.mapa.registrar(s.page, etapa, forcar=forcar)
    except Exception:  # noqa: BLE001
        pass


def _aviso_etapa(s: Sessao, a: Andamento, etapa: str) -> None:
    s.aviso("etapa", etapa=etapa, pedido=a.base.id, plano=a.alvo.rotulo_completo() if a.alvo else "",
            indice=a.indice, total=len(a.alvos))
    if s.pediu_parar() and not a.aguardando:
        raise Parado(etapa)


def reemissao_pedida(s: Sessao, item: dict | None) -> bool:
    return (bool(item) and not s.ensaio and item.get("status") == "pdf_ok"
            and str(item.get("protocolo") or "") in s.reemitir)


def _lugar(s: Sessao):
    return cotador(s.page)


def _pausar(s: Sessao) -> None:
    time.sleep(max(int(s.cfg["execucao"].get("lentidao_ms") or 0), 0) / 1000)


def ir_ao_cotador(s: Sessao) -> None:
    page = s.page
    fechar_overlays(page)
    if _visivel(page.locator("iframe#cotador")) or "cotar" in sel.caminho(page):
        return
    url = (s.cfg.get("urls") or {}).get("cotador")
    if url:
        page.goto(url if url.startswith("http") else page.url.rsplit("/", 1)[0] + "/home")
        page.wait_for_load_state("domcontentloaded")
    esperar_ate(lambda: _visivel(page.locator("iframe#cotador")) or _visivel(sel.botao_criar_nova(_lugar(s))),
                s.t("timeout_tela_ms") / 1000)
    fechar_overlays(page)


def criar_nova_cotacao(s: Sessao, a: Andamento) -> None:
    """Sempre Criar nova cotação. Nunca Duplicar."""
    _aviso_etapa(s, a, "inicio")
    ir_ao_cotador(s)
    lugar = _lugar(s)
    botao = esperar_visivel(sel.botao_criar_nova(lugar), s.t("timeout_tela_ms"), "Criar nova cotação", "inicio")
    botao.click()
    _pausar(s)
    esperar_ate(lambda: "dados" in texto_do_cotador(s.page).lower() or _visivel(sel.campo_cnpj(_lugar(s))),
                s.t("timeout_tela_ms") / 1000)
    _mapa(s, "dados")


def _clicar_proximo(lugar) -> None:
    botao = sel.botao_proximo(lugar)
    try:
        botao.first.scroll_into_view_if_needed(timeout=2000)
    except Exception:  # noqa: BLE001
        pass
    botao.first.click(timeout=4000, force=True)


def dados_iniciais(s: Sessao, a: Andamento) -> None:
    _aviso_etapa(s, a, "dados")
    fechar_overlays(s.page)
    lugar, p = _lugar(s), a.base
    campo = esperar_visivel(sel.campo_cnpj(lugar), s.t("timeout_tela_ms"), "CNPJ", "dados")
    campo.fill(formatar_cnpj(p.cnpj), force=True)
    _pausar(s)
    if not esperar_ate(lambda: empresa_preenchida(s.page), s.t("timeout_tela_ms") / 1000):
        raise ErroFluxo("o portal não preencheu os dados da empresa pelo CNPJ", "dados")
    texto = texto_do_cotador(s.page)
    if sel.TEXTO_CEP_INVALIDO.search(texto):
        raise ErroDados("o portal pediu um CEP válido e o cadastro da Receita veio incompleto", "dados")
    try:
        a.razao_social = (_lugar(s).locator("input[name='.companyName']").input_value() or "").strip()
    except Exception:  # noqa: BLE001
        a.razao_social = ""
    if not a.razao_social:
        m = re.search(r"Raz[aã]o social\s*:?\s*([^\n]+)", texto, re.I)
        a.razao_social = " ".join((m.group(1) if m else "").split())
    for _ in range(3):
        fechar_overlays(s.page)
        _clicar_proximo(_lugar(s))
        if esperar_ate(lambda: saiu_de_dados_iniciais(s.page), 8):
            return
    raise ErroFluxo("o portal não saiu de Dados iniciais depois do CNPJ", "dados")


def _preencher_faixa(lugar, rotulo: str, qtd: int, idades: list[int]) -> None:
    chave = rotulo.replace(" ", "").replace("-", "")
    campo = lugar.locator(f"input[data-faixa='{rotulo}'], input[name='faixa_{chave}']").first
    if campo.count():
        campo.fill(str(qtd))
    if rotulo == "0 - 18" and idades:
        for i, idade in enumerate(idades):
            caixa = lugar.locator(f"input[data-idade='{idade}'], input[name='idade_{idade}']").first
            if caixa.count():
                caixa.fill("1")


def produto_vidas(s: Sessao, a: Andamento) -> None:
    _aviso_etapa(s, a, "vidas")
    lugar, p = _lugar(s), a.base
    esperar_visivel(sel.campo_total_vidas(lugar), s.t("timeout_tela_ms"), "quantidade de vidas", "vidas")
    sel.campo_total_vidas(lugar).first.fill(str(p.total_vidas))
    _pausar(s)
    if p.seguro_novo:
        sel.select_plano_anterior(lugar).first.select_option(label="Não Possui Plano Anterior")
    else:
        nomes = p.congeneres_para_tentar()
        escolheu = False
        for nome in nomes:
            try:
                sel.select_plano_anterior(lugar).first.select_option(label=nome)
                escolheu = True
                break
            except Exception:  # noqa: BLE001
                continue
        if not escolheu:
            raise ErroFluxo("a operadora atual não está na lista da Porto. Nomes tentados: "
                            + "; ".join(nomes), "vidas")
    _pausar(s)
    for rotulo in ROTULOS:
        qtd = int(p.vidas.get(rotulo) or 0)
        if qtd:
            _preencher_faixa(lugar, rotulo, qtd, p.idades.get(rotulo) or [])
            _pausar(s)
    texto = texto_do_cotador(s.page)
    if sel.TEXTO_FALTAM_VIDAS.search(texto):
        raise ErroDados(sel.TEXTO_FALTAM_VIDAS.search(texto).group(0), "vidas")
    sel.botao_proximo(lugar).first.click()
    _pausar(s)


def comissao(s: Sessao, a: Andamento) -> None:
    _aviso_etapa(s, a, "comissao")
    lugar, p = _lugar(s), a.base
    esperar_visivel(sel.select_comissao(lugar), s.t("timeout_tela_ms"), "comissão", "comissao")
    sel.select_comissao(lugar).first.select_option(label=p.comissao)
    _pausar(s)
    lido = sel.select_comissao(lugar).first.input_value()
    if lido and norm(lido) != norm(p.comissao):
        # alguns selects devolvem o value; confere pelo texto visível
        visivel = lugar.locator("select#comissao option:checked").inner_text()
        if norm(visivel) != norm(p.comissao):
            raise ErroFluxo(f"a comissão selecionada não é a pedida. Tela: {visivel!r}; pedido: {p.comissao!r}",
                            "comissao")
    caixa = sel.checkbox_agenciamento(lugar)
    if caixa.count() and not caixa.first.is_checked():
        caixa.first.check()
    sel.botao_proximo(lugar).first.click()
    _pausar(s)


def selecionar_plano(s: Sessao, a: Andamento) -> None:
    """Passo 3. O ensaio PARA aqui, com o plano selecionado, sem Gerar orçamento."""
    _aviso_etapa(s, a, "planos")
    lugar, p, alvo = _lugar(s), a.base, a.alvo
    if not esperar_ate(lambda: bool(sel.nomes_dos_planos(_lugar(s))), s.t("timeout_tela_ms") / 1000):
        raise ErroFluxo("a grade de planos não apareceu", "planos")
    lugar = _lugar(s)
    acomodacao = alvo.acomodacao or p.acomodacao
    copart = "30%" if (alvo.versao or p.coparticipacao) == "com" else "0%"
    if sel.radio_acomodacao(lugar, acomodacao).count():
        sel.radio_acomodacao(lugar, acomodacao).first.click()
        _pausar(s)
    if sel.radio_copart(lugar, copart).count():
        sel.radio_copart(lugar, copart).first.click()
        _pausar(s)
    botao = sel.botao_plano(lugar, alvo.nome)
    if not botao.count():
        nomes = sel.nomes_dos_planos(lugar)
        raise ErroFluxo(f"'{alvo.nome}' não está na grade da Porto. Nomes que o robô viu: "
                        f"{'; '.join(nomes[:40])}", "planos")
    botao.first.click()
    _pausar(s)
    texto = texto_do_cotador(s.page)
    resumo = ex.ler_resumo_passo3(texto)
    if resumo["plano"] and norm(alvo.nome) not in norm(resumo["plano"]) and not resumo["selecionado"]:
        raise ErroFluxo(f"o resumo não mostra o plano {alvo.nome} selecionado", "planos")
    a.subtotal = resumo["valor"]
    s.log.info(f"Plano {alvo.nome} selecionado (preço indicativo {a.subtotal}).")
    _mapa(s, "planos")


def gerar_orcamento(s: Sessao, a: Andamento) -> None:
    """PONTO SEM VOLTA. Só com pode_gerar(). Grava emitindo ANTES do clique."""
    if not s.pode_gerar():
        raise ErroFluxo("Gerar orçamento recusado: ensaio ou emissão não liberada", "orcamento")
    _aviso_etapa(s, a, "orcamento")
    lugar, p, alvo = _lugar(s), a.base, a.alvo
    botao = esperar_visivel(sel.botao_gerar_orcamento(lugar), s.t("timeout_tela_ms"),
                            "Gerar orçamento", "orcamento")
    chave = chave_cotacao(s, p, alvo)
    s.estado.registrar(chave, p.na_versao(alvo.versao) if alvo.versao else p, alvo.nome,
                       alvo.acomodacao or p.acomodacao, "emitindo",
                       obs="clicou Gerar orçamento",
                       substituir_protocolo=a.substituir.get(norm(alvo.nome)))
    a.aguardando = True
    s.log.info(f"Gerando orçamento de {alvo.nome} (registro gravado como emitindo)...")
    botao.click()
    esperar_ate(lambda: _visivel(sel.botao_emitir_sem_medicamentos(_lugar(s))), 15)
    if _visivel(sel.botao_emitir_sem_medicamentos(_lugar(s))):
        sel.botao_emitir_sem_medicamentos(_lugar(s)).first.click()
        _pausar(s)
    if not esperar_ate(lambda: ex.ler_numero_cotacao(texto_do_cotador(s.page)), s.t("timeout_emissao_ms") / 1000):
        raise ErroFluxo("o portal não mostrou o número da cotação depois de Gerar orçamento", "orcamento")
    texto = texto_do_cotador(s.page)
    det = ex.ler_detalhes(texto)
    a.numero = det["numero"]
    a.subtotal, a.taxa, a.iof, a.total = det["subtotal"], det["taxa"], det["iof"], det["total"]
    _conferir_valores(s, a)
    s.estado.registrar(chave, p.na_versao(alvo.versao) if alvo.versao else p, alvo.nome,
                       alvo.acomodacao or p.acomodacao, "emitida", obs="cotação calculada",
                       protocolo=a.numero)
    s.log.info(f"Cotação {a.numero} calculada.")
    _mapa(s, "resultado")


def _conferir_valores(s: Sessao, a: Andamento) -> None:
    p = a.base
    conf = s.cfg["conferencias"]
    aliquota = Decimal(str(conf.get("aliquota_iof", "0.0238")))
    por_vida = Decimal(str(conf.get("taxa_inscricao_por_vida", "5.00")))
    if None in (a.subtotal, a.taxa, a.iof, a.total):
        raise ErroFluxo("não li sub-total, taxa, IOF e total depois de preencher as vidas", "orcamento")
    problemas = ex.conferir_detalhes(p.total_vidas, a.valores or {}, p.vidas, a.subtotal, a.taxa, a.iof, a.total,
                                     aliquota, por_vida, s.tol())
    # conferência mínima mesmo sem a tabela por faixa (taxa, IOF, total)
    problemas = [x for x in problemas if "soma por faixa" not in x] if not a.valores else problemas
    if problemas:
        raise ErroFluxo("valores da cotação não conferem: " + "; ".join(problemas), "orcamento")
    s.log.info(f"Valores conferidos: sub-total {a.subtotal}, taxa {a.taxa}, IOF {a.iof}, total {a.total}.")


def imprimir_pdf(s: Sessao, a: Andamento) -> None:
    _aviso_etapa(s, a, "pdf")
    lugar, p, alvo = _lugar(s), a.base, a.alvo
    pasta = Path(s.cfg["saida"]["pasta"]) / "pdfs"
    pasta.mkdir(parents=True, exist_ok=True)
    ultimo_erro = None
    for tentativa in range(1, 4):
        if _visivel(sel.botao_fechar_erro_pdf(lugar)):
            sel.botao_fechar_erro_pdf(lugar).first.click()
            _pausar(s)
        botao = esperar_visivel(sel.botao_imprimir(lugar), s.t("timeout_tela_ms"), "Imprimir cotação", "pdf")
        try:
            with s.page.context.expect_page(timeout=s.t("timeout_download_ms")) as nova:
                botao.click()
            aba = nova.value
            aba.wait_for_load_state("domcontentloaded")
            url = aba.url
            dados = aba.request.get(url).body() if url else aba.content().encode("utf-8")
            aba.close()
            if not dados.startswith(b"%PDF"):
                raise ErroFluxo("o arquivo da aba não é um PDF", "pdf")
            nome = nome_pdf_arquivo(s.cfg, p.cnpj, a.numero or "", alvo.nome)
            caminho = pasta / nome
            caminho.write_bytes(dados)
            nome_dest = nome_pdf_destino(s.cfg, p.cnpj, a.numero or "", alvo.nome,
                                         acomodacao=alvo.acomodacao or p.acomodacao, versao=p.apelido)
            destino = ""
            if p.pasta_destino:
                destino = copiar_para_destino(caminho, p.pasta_destino, nome_dest,
                                              bool(s.cfg["saida"].get("substituir_no_destino", True)), s.log)
            chave = chave_cotacao(s, p, alvo)
            s.estado.registrar(chave, p.na_versao(alvo.versao) if alvo.versao else p, alvo.nome,
                               alvo.acomodacao or p.acomodacao, "pdf_ok", obs="PDF baixado",
                               protocolo=a.numero, pdf=str(caminho), pdf_destino=destino, nome_destino=nome_dest)
            a.resultado = _resultado(a, status="OK", protocolo=a.numero, pdf_arquivo=str(caminho),
                                     pdf_destino=destino, pdf_nome=nome_dest, total_sem_iof=a.subtotal,
                                     iof=a.iof, total_com_iof=a.total, preco_mensal=a.total)
            s.resultados.plano(a.resultado)
            s.log.info(f"PDF da cotação {a.numero} salvo ({tentativa}ª tentativa).")
            return
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            if _visivel(sel.botao_fechar_erro_pdf(_lugar(s))) or "Erro ao gerar PDF" in texto_do_cotador(s.page):
                s.log.warning(f"Erro ao gerar PDF (tentativa {tentativa}/3); fechando e tentando de novo.")
                if _visivel(sel.botao_fechar_erro_pdf(_lugar(s))):
                    sel.botao_fechar_erro_pdf(_lugar(s)).first.click()
                _pausar(s)
                continue
            break
    s.estado.registrar(chave_cotacao(s, p, alvo), p, alvo.nome, alvo.acomodacao or p.acomodacao, "pdf_manual",
                       obs="não baixou o PDF", protocolo=a.numero)
    raise ErroFluxo(f"não consegui baixar o PDF da cotação {a.numero} (confira no portal). "
                    f"Último erro: {ultimo_erro}", "pdf")


def recuperar(s: Sessao, a: Andamento, alvo: PlanoAlvo, item: dict) -> bool:
    """Caiu depois de Gerar orçamento: procura na lista pelo CNPJ e baixa por Visualizar. Não gera outra."""
    _aviso_etapa(s, a, "pdf")
    ir_ao_cotador(s)
    lugar = _lugar(s)
    if sel.busca_lista(lugar).count():
        sel.busca_lista(lugar).first.fill(formatar_cnpj(a.base.cnpj))
        _pausar(s)
    if not _visivel(sel.botao_visualizar(lugar)):
        s.log.warning("Não achei a cotação na lista pelo CNPJ; conferir no portal.")
        return False
    sel.botao_visualizar(lugar).first.click()
    _pausar(s)
    a.numero = item.get("protocolo") or ex.ler_numero_cotacao(texto_do_cotador(s.page))
    det = ex.ler_detalhes(texto_do_cotador(s.page))
    a.subtotal, a.taxa, a.iof, a.total = det["subtotal"], det["taxa"], det["iof"], det["total"]
    imprimir_pdf(s, a)
    return True


def voltar_lista(s: Sessao) -> None:
    lugar = _lugar(s)
    if sel.botao_pagina_principal(lugar).count():
        sel.botao_pagina_principal(lugar).first.click()
        _pausar(s)


def ensaiar_ok(s: Sessao, a: Andamento) -> None:
    a.resultado = _resultado(
        a, status="ENSAIO_OK", preco_mensal=a.subtotal, total_sem_iof=a.subtotal,
        erro="ensaio: parou no passo 3 com o plano selecionado, sem Gerar orçamento")
    s.resultados.plano(a.resultado)
    s.log.info(f"ENSAIO_OK {a.alvo.nome}: plano selecionado, nada gerado no portal.")


def sair_do_portal(sessao, prazo_s: float = 30) -> bool:
    try:
        if sel.botao_sair(sessao.page).count():
            sel.botao_sair(sessao.page).first.click()
            return esperar_ate(lambda: login_na_tela(sessao.page), prazo_s)
    except Exception:  # noqa: BLE001
        return False
    return False
