"""Uma função por tela do portal da Amil (vendasmil, Cotação PME).

Ordem (vídeo do corretor): menu "Criar Oportunidade PME" -> CNPJ (o portal preenche o resto pela Receita) -> "Concluir
Oportunidade" (nasce a OPP-...) -> "Criar Cotação" (nasce a COT-... em "Em Digitação") -> Vínculo de Vendas (corretor) ->
Selecionar Planos (plano e vidas por faixa; aditivo e dental) -> Revisar Cotação -> **Concluir Cotação** -> PDF ->
"Baixar PDF". Para o próximo plano: volta à oportunidade -> "Criar Cotação".

Um pedido (empresa) = UMA oportunidade; cada plano = UMA cotação. Registro anti-reemissão (nucleo.estado):
- oportunidade (chave = o CNPJ): "emitindo" antes de "Concluir Oportunidade", "pdf_ok" com o OPP e o id da URL assim que
  o número aparece (é o "feita e conhecida"); uma oportunidade conhecida é REABERTA, nunca criada de novo;
- cotação (chave = a empresa + vidas + corretor + dental + plano): "digitando" (não bloqueia) assim que a COT aparece, com o
  id da URL, para uma cotação que ficou em "Em Digitação" ser continuada e não duplicada; "emitindo" ANTES de "Concluir
  Cotação" (o ponto sem volta); "emitida" quando o portal confirma "Concluída"; "pdf_ok" com o PDF salvo.
  Se cair depois do clique, o robô reabre a COT (pela URL ou pela lista da oportunidade) e baixa o PDF, sem criar outra.

O robô NUNCA clica em "Criar Proposta", "Enviar por E-mail" nem em "+ Incluir Plano Médico"; não há seletor para eles.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin, urlparse

from nucleo.modelo import ROTULOS, PlanoAlvo, PlanoVisto, ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, Parado, conferir_parar, esperar_visivel, ligar_parar, visiveis
from nucleo.saidas import copiar_para_destino, nome_pdf_arquivo, nome_pdf_destino
from nucleo.texto import formatar_cnpj, norm, rx, so_digitos

from . import extracao as ex
from . import seletores as sel
from .login import entrar
from .pedido import NOME_OPORTUNIDADE, Oportunidade, Pedido, familia
from .telas import (SessaoCaiu, _visivel, escolher_na_lista, escolher_no_select, esperar_ate, esperar_sem_carregando,
                    fechar_avisos, login_na_tela, logado, opcoes_do_select, texto_da_pagina)


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
            except Exception:  # noqa: BLE001  (a tela nunca pode derrubar o robô)
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


@dataclass
class Andamento:
    base: Pedido
    alvos: list[PlanoAlvo]
    indice: int = 0
    razao_social: str = ""
    opp: str | None = None                 # OPP-..., depois de "Concluir Oportunidade" (ou do registro)
    opp_id: str = ""                       # o id da oportunidade na URL (/oportunidades/<id>)
    cot: str | None = None                 # COT-... da cotação deste plano
    cot_id: str = ""                       # o id da cotação na URL (/cotacoes/<id>)
    reaproveitar: dict = field(default_factory=dict)  # plano (norm) -> item "digitando" do registro: continua essa COT
    substituir: dict = field(default_factory=dict)    # plano (norm) -> COT concluída que o corretor pediu para emitir de novo
    resultado: ResultadoPlano | None = None
    valores: dict = field(default_factory=dict)       # rótulo -> valor por vida (depois de preencher todas as faixas)
    valor_total_grade: Decimal | None = None
    dental_marcado: bool | None = None     # o dental como ficou na tela dos planos; None = a cotação já veio na revisão
    aguardando: bool = False               # entre o clique em "Concluir Cotação" e o PDF salvo
    terminou: bool = False
    recuperar: list = field(default_factory=list)     # [(alvo, item)] concluídos no portal que faltam o PDF

    @property
    def alvo(self) -> PlanoAlvo | None:
        return self.alvos[self.indice] if self.indice < len(self.alvos) else None

    @property
    def pedido(self) -> Pedido:
        return self.base


def chave_oportunidade(s: Sessao, pedido: Pedido) -> str:
    return s.estado.chave(Oportunidade(pedido), NOME_OPORTUNIDADE, "")


def chave_cotacao(s: Sessao, a: Andamento, alvo: PlanoAlvo | None = None) -> str:
    return s.estado.chave(a.base, (alvo or a.alvo).nome, "")


MENSAGEM_REGISTRO = {
    "pdf_ok": "já concluída em execução anterior",
    "emitindo": "o robô clicou em Concluir Cotação e não confirmou; ele reabre a cotação pela oportunidade para conferir",
    "emitida": "cotação concluída no portal, PDF pendente",
    "pdf_manual": "cotação concluída; baixe o PDF à mão pela oportunidade no portal",
}


def _resultado(a: Andamento, alvo: PlanoAlvo | None = None, **campos) -> ResultadoPlano:
    alvo = alvo or a.alvo
    return ResultadoPlano(pedido_id=a.base.id, linha=a.base.linha, cnpj=a.base.cnpj, plano=alvo.nome if alvo else "",
                          acomodacao="", razao_social=a.razao_social, **campos)


def _mapa(s: Sessao, etapa: str, forcar: bool = False) -> None:
    try:
        s.mapa.registrar(s.page, etapa, forcar=forcar)
    except Exception:  # noqa: BLE001  (o mapa nunca derruba o robô)
        pass


def _aviso_etapa(s: Sessao, a: Andamento, etapa: str) -> None:
    if s.pediu_parar() and not a.aguardando:
        raise Parado(etapa)
    s.aviso("etapa", etapa=etapa, pedido=a.base.id, plano=a.alvo.rotulo_completo() if a.alvo else "",
            indice=a.indice, total=len(a.alvos))


def reemissao_pedida(s: Sessao, item: dict | None) -> bool:
    """O corretor pediu na tela "Emitir de novo mesmo assim" (pelo COT que viu no aviso). Só vale para o que está concluído
    (pdf_ok): cotação incerta continua sendo recuperada, nunca refeita. Na Amil, emitir de novo = uma COT nova na mesma
    oportunidade (a antiga vai para "reemitidos")."""
    return (bool(item) and not s.ensaio and item.get("status") == "pdf_ok"
            and str(item.get("protocolo") or "") in s.reemitir)


# ============================ navegação ============================

def _base(s: Sessao) -> str:
    u = urlparse(s.cfg["urls"].get("home") or s.cfg["urls"]["login"])
    return f"{u.scheme}://{u.netloc}"


def _id_da_url(page, rota: str) -> str:
    """"/oportunidades/6ad25...?origem=cadastro-pme" -> "6ad25..."."""
    caminho = urlparse(page.url).path
    i = caminho.lower().find(rota)
    return caminho[i + len(rota):].strip("/").split("/")[0] if i >= 0 else ""


def garantir_sessao(s: Sessao) -> None:
    if login_na_tela(s.page) or not logado(s.page):
        entrar(s)


def _esperar_tela(s: Sessao, condicao, descricao: str, etapa: str, segundos: float | None = None) -> None:
    fim = time.monotonic() + (segundos if segundos is not None else s.t("timeout_tela_ms") / 1000)
    while time.monotonic() < fim:
        try:
            if condicao():
                return
        except Exception:  # noqa: BLE001  (tela mudando)
            pass
        if login_na_tela(s.page):
            raise SessaoCaiu("o portal pediu o login de novo (a sessão acabou)", etapa)
        conferir_parar(etapa)
        time.sleep(0.25)
    raise ErroFluxo(f"não encontrei '{descricao}' na tela em {int((segundos if segundos is not None else s.t('timeout_tela_ms') / 1000))}s",
                    etapa)


def _numero_no_painel(s: Sessao, prefixo: str) -> str | None:
    return ex.ler_numero_do_painel(texto_da_pagina(s.page), prefixo) or (
        ex.ler_opp(texto_da_pagina(s.page)) if prefixo == "OPP" else None)


# ============================ oportunidade ============================

def oportunidade(s: Sessao, a: Andamento) -> None:
    """Deixa a oportunidade do pedido aberta: reabre a que o registro conhece ou cria uma. Nunca cria duas."""
    if a.opp:
        return reabrir_oportunidade(s, a)
    _criar_oportunidade(s, a)


def reabrir_oportunidade(s: Sessao, a: Andamento) -> None:
    etapa = "oportunidade"
    _aviso_etapa(s, a, etapa)
    garantir_sessao(s)
    if f"{sel.ROTA_OPORTUNIDADE}{a.opp_id}" not in s.page.url.lower() or sel.ROTA_COTACAO in sel.caminho(s.page):
        url = urljoin(_base(s), f"{sel.ROTA_OPORTUNIDADE}{a.opp_id}")
        s.log.info(f"Abrindo a oportunidade {a.opp} (já existe no registro).")
        s.page.goto(url)
        s.page.wait_for_load_state("domcontentloaded")
    _esperar_tela(s, lambda: a.opp in texto_da_pagina(s.page), f"oportunidade {a.opp}", etapa)
    esperar_sem_carregando(s.page, 15)
    if not a.razao_social:
        m = re.search(r"Raz[ãa]o Social\s*:?\s*([^\n]+)", texto_da_pagina(s.page), re.I)
        a.razao_social = " ".join(m.group(1).split()) if m else ""
    _mapa(s, "oportunidade")


def _criar_oportunidade(s: Sessao, a: Andamento) -> None:
    page, p, etapa = s.page, a.base, "oportunidade"
    _aviso_etapa(s, a, etapa)
    garantir_sessao(s)
    if not _visivel(sel.menu_criar_oportunidade_pme(page)):
        page.goto(s.cfg["urls"].get("home") or s.cfg["urls"]["login"])
        page.wait_for_load_state("domcontentloaded")
    esperar_visivel(sel.menu_criar_oportunidade_pme(page), s.t("timeout_tela_ms"), "menu Criar Oportunidade PME", etapa).click()
    _esperar_tela(s, lambda: sel.ROTA_OPORTUNIDADE_NOVA in sel.caminho(page) and _visivel(page.get_by_text(sel.TEXTO_COLIGACAO)),
                  "Oportunidade PME (Haverá Coligação?)", etapa)
    esperar_sem_carregando(page, 10)
    # Haverá Coligação? Já vem em Não (vídeo). O robô confere e só clica se o pedido diz outra coisa.
    quer_sim = norm(p.coligacao) == "sim"
    radio = sel.coligacao_radio(page, quer_sim)
    if not radio.is_checked():
        radio.check()
    if not radio.is_checked():
        raise ErroFluxo(f"não consegui marcar 'Haverá Coligação?' = {p.coligacao}", etapa)
    campo = esperar_visivel(sel.campo_cnpj(page), s.t("timeout_tela_ms"), "campo CNPJ", etapa)
    campo.click()
    campo.fill("")
    campo.press_sequentially(formatar_cnpj(p.cnpj), delay=20)      # digitar: o portal consulta a Receita ao digitar
    campo.press("Tab")
    # "Consultando CNPJ na Receita Federal…" -> "Verificando CNAE…": o portal preenche e trava o resto
    if not esperar_ate(lambda: bool((sel.campo_razao_social(page).first.input_value() or "").strip()),
                       s.t("timeout_tela_ms") / 1000):
        raise ErroFluxo("o portal não preencheu a razão social pela Receita Federal (CNPJ não encontrado?)", etapa)
    esperar_ate(lambda: not _visivel(page.get_by_text(sel.TEXTO_CONSULTANDO_CNPJ)), 30)
    esperar_sem_carregando(page, 30)
    a.razao_social = " ".join((sel.campo_razao_social(page).first.input_value() or "").split())
    for nome, loc in (("Nome Fantasia", sel.campo_nome_fantasia(page)),):
        if not (loc.first.input_value() or "").strip():
            raise ErroFluxo(f"o portal não preencheu '{nome}' pela Receita Federal", etapa)
    s.log.info(f"Empresa: {a.razao_social} | {formatar_cnpj(p.cnpj)}")
    _mapa(s, "oportunidade_form")
    botao = esperar_visivel(sel.botao_concluir_oportunidade(page), s.t("timeout_tela_ms"), "botão Concluir Oportunidade", etapa)
    if not botao.is_enabled():
        raise ErroFluxo("o botão Concluir Oportunidade está desabilitado (falta algum campo obrigatório)", etapa)
    chave = chave_oportunidade(s, p)
    if not s.estado.pode_emitir(chave):
        raise ErroFluxo("o registro diz que a oportunidade desta empresa já foi criada; não crio outra", etapa)
    s.estado.registrar(chave, Oportunidade(p), NOME_OPORTUNIDADE, "", "emitindo", obs="clicou Concluir Oportunidade",
                       pasta_destino=p.pasta_destino)
    s.log.info(f"Concluindo a oportunidade da empresa {formatar_cnpj(p.cnpj)}...")
    botao.click()
    _esperar_tela(s, lambda: sel.ROTA_OPORTUNIDADE in sel.caminho(page) and sel.ROTA_OPORTUNIDADE_NOVA not in sel.caminho(page)
                  and bool(_numero_no_painel(s, "OPP")), "a oportunidade criada (OPP-...)", etapa, s.t("timeout_emissao_ms") / 1000)
    a.opp = _numero_no_painel(s, "OPP")
    a.opp_id = _id_da_url(page, sel.ROTA_OPORTUNIDADE)
    s.estado.registrar(chave, Oportunidade(p), NOME_OPORTUNIDADE, "", "pdf_ok", obs="oportunidade criada", protocolo=a.opp,
                       url_id=a.opp_id)
    s.log.info(f"Oportunidade criada: {a.opp} (id {a.opp_id}); número guardado no registro.")
    esperar_sem_carregando(page, 10)
    _mapa(s, "oportunidade")


# ============================ cotação ============================

def _tela_da_cotacao(s: Sessao) -> str:
    """Em que passo da cotação a página está: vinculo | planos | revisar | outra."""
    page = s.page
    if _visivel(page.get_by_text(rx("Resumo Geral"))):
        return "revisar"
    if _visivel(page.get_by_text(sel.TEXTO_VINCULO)):
        return "vinculo"
    if _visivel(page.get_by_text(rx("Planos Médicos"))):
        return "planos"
    return "outra"


def _voltar_ao_vinculo(s: Sessao, etapa: str) -> None:
    """Cotação continuada: o portal reabre em Selecionar Planos e NÃO guarda o corretor de forma confiável (12/11: a revisão
    mostrou "Corretor: -" numa cotação cujo vínculo tinha sido preenchido antes). Volta com "Anterior" até o Vínculo de Vendas
    para o robô escolher o corretor de novo (escolher é idempotente). Sem botão "Anterior" visível, segue como está: a
    conferência da revisão trava se o corretor não estiver certo."""
    page = s.page
    for _ in range(3):
        if _tela_da_cotacao(s) == "vinculo":
            return
        botoes = visiveis(sel.botao_anterior(page))
        if not botoes:
            return
        botoes[0].click()
        esperar_ate(lambda: _tela_da_cotacao(s) == "vinculo", 6)
        esperar_sem_carregando(page, 10)
    if _tela_da_cotacao(s) != "vinculo":
        s.log.warning("Não consegui voltar ao Vínculo de Vendas com 'Anterior'; sigo e confiro o corretor na revisão.")


def cotacao(s: Sessao, a: Andamento) -> None:
    """Cria a cotação do plano (ou continua a que ficou em "Em Digitação") e preenche o Vínculo de Vendas."""
    page, p, etapa = s.page, a.base, "vinculo"
    _aviso_etapa(s, a, etapa)
    chave = chave_cotacao(s, a)
    continuar = a.reaproveitar.get(norm(a.alvo.nome))
    if continuar and continuar.get("cot_id"):
        a.cot, a.cot_id = continuar.get("protocolo"), continuar["cot_id"]
        s.log.info(f"Continuando a cotação {a.cot} (ficou em Digitação em execução anterior).")
        page.goto(urljoin(_base(s), f"{sel.ROTA_COTACAO}{a.cot_id}"))
        page.wait_for_load_state("domcontentloaded")
        _esperar_tela(s, lambda: _tela_da_cotacao(s) != "outra", "a cotação em digitação", etapa)
        esperar_sem_carregando(page, 15)
        if a.cot not in texto_da_pagina(page):
            raise ErroFluxo(f"a página aberta não é a cotação {a.cot}", etapa)
        if re.search(r"Conclu[ií]da", texto_da_pagina(page)[:3000]) and _tela_da_cotacao(s) == "revisar":
            raise ErroFluxo(f"a cotação {a.cot} já está Concluída no portal; confira em 'Cotações da Oportunidade'", etapa)
        _voltar_ao_vinculo(s, etapa)
    else:
        botoes = visiveis(sel.botao_criar_cotacao(page))
        if not botoes:
            raise ErroFluxo("não achei o botão Criar Cotação na oportunidade", etapa)
        substituir = a.substituir.get(norm(a.alvo.nome))
        if not s.estado.pode_emitir(chave) and not substituir and (s.estado.item(chave) or {}).get("status") != "digitando":
            raise ErroFluxo("o registro diz que esta cotação já foi feita; não crio outra", etapa)
        botoes[0].click()
        _esperar_tela(s, lambda: sel.ROTA_COTACAO in sel.caminho(page) and _tela_da_cotacao(s) == "vinculo",
                      "Criar Cotação (Vínculo de Vendas)", etapa)
        esperar_sem_carregando(page, 15)
        _esperar_tela(s, lambda: bool(_numero_no_painel(s, "COT")), "o número da cotação (COT-...)", etapa)
        a.cot = ex.ler_numero_do_painel(texto_da_pagina(page), "COT")
        a.cot_id = _id_da_url(page, sel.ROTA_COTACAO)
        # Grava a COT assim que aparece: "digitando" não bloqueia, mas deixa continuar a mesma cotação depois.
        s.estado.registrar(chave, p, a.alvo.nome, "", "digitando",
                           obs="cotação criada (Em Digitação)" + (f" (de novo; antes: {substituir})" if substituir else ""),
                           protocolo=a.cot, cot_id=a.cot_id, opp=a.opp, pasta_destino=p.pasta_destino,
                           substituir_protocolo=substituir)
        s.log.info(f"Cotação criada: {a.cot} (id {a.cot_id}) para {a.alvo.nome}.")
    if _tela_da_cotacao(s) == "vinculo":
        _mapa(s, f"vinculo_{a.indice + 1}")
        if visiveis(sel.corretor_ja_escolhido(page, p.corretor)):
            # cotação continuada: o portal já mostra o corretor no campo ("EDLAINE ABREU SOARES ×"); não abre a lista de novo
            s.log.info(f"Corretor do Vínculo de Vendas já escolhido: {p.corretor}.")
        else:
            escolhido = escolher_na_lista(page, sel.combo_corretor(page), p.corretor, "Nome do Corretor", etapa,
                                          busca=sel.busca_corretor(page))
            s.log.info(f"Corretor do Vínculo de Vendas: {escolhido}.")
        if p.supervisor:
            esperar_ate(lambda: sel.combo_supervisor(page).count() > 0, 5)
            escolhido = escolher_na_lista(page, sel.combo_supervisor(page), p.supervisor, "Nome do Supervisor", etapa)
            s.log.info(f"Supervisor: {escolhido}.")
        continuar = esperar_visivel(sel.botao_continuar(page), s.t("timeout_tela_ms"), "botão Continuar", etapa)
        _esperar_tela(s, continuar.is_enabled, "o botão Continuar habilitado (Vínculo de Vendas)", etapa)
        continuar.click()
        _esperar_tela(s, lambda: _tela_da_cotacao(s) in ("planos", "revisar"), "Selecionar Planos", etapa)
        esperar_sem_carregando(page, 15)


def _ler_grade(s: Sessao) -> dict:
    page = s.page
    qtds = [int(so_digitos(c.input_value()) or 0) for c in sel.campos_de_vidas(page).all()]

    def linha(rotulo: str) -> list[Decimal]:
        celulas = sel.celulas_da_linha(page, rotulo).all_inner_texts()
        return [ex.dinheiro(t) for t in celulas[-len(ROTULOS):]]

    totais = ex.ler_totais_da_grade(texto_da_pagina(page))
    return {"qtds": qtds, "valores": linha("Valor por Vida"), "subtotais": linha("Subtotal"), "vidas": totais[0],
            "valor_total": totais[1]}


def planos(s: Sessao, a: Andamento) -> None:
    """Escolhe o plano, preenche as 10 faixas e só DEPOIS lê o valor por vida (ele muda com o total de vidas)."""
    page, p, etapa = s.page, a.base, "planos"
    _aviso_etapa(s, a, etapa)
    if _tela_da_cotacao(s) == "revisar":
        return
    _esperar_tela(s, lambda: _tela_da_cotacao(s) == "planos", "Selecionar Planos", etapa)
    campo = esperar_visivel(sel.select_plano(page), s.t("timeout_tela_ms"), "lista de planos", etapa)
    atual = [o for o in opcoes_do_select(campo)]
    escolhido = escolher_no_select(campo, a.alvo.nome, "Plano", etapa)
    s.log.info(f"Plano escolhido: {escolhido} (a lista tem {max(0, len(atual) - 1)} planos).")
    esperar_sem_carregando(page, 10)
    esperar_ate(lambda: sel.campos_de_vidas(page).count() == len(ROTULOS), 15)
    esperar_visivel(sel.campos_de_vidas(page).first, s.t("timeout_tela_ms"), "campos de vidas por faixa", etapa)
    _mapa(s, f"planos_{a.indice + 1}")
    # Preenche todas as faixas e relê: o portal recalcula o valor por vida a cada vida que entra.
    for _ in range(3):
        campos = sel.campos_de_vidas(page).all()
        for rotulo, c in zip(ROTULOS, campos):
            quer = int(p.vidas.get(rotulo, 0))
            if int(so_digitos(c.input_value()) or 0) != quer:
                c.click()
                c.fill(str(quer))
                c.press("Tab")
                time.sleep(0.2)
        esperar_sem_carregando(page, 10)
        if [int(so_digitos(c.input_value()) or 0) for c in sel.campos_de_vidas(page).all()] == [int(p.vidas.get(r, 0)) for r in ROTULOS]:
            break
    grade, anterior, problemas = None, None, []
    fim = time.monotonic() + 20
    while time.monotonic() < fim:
        grade = _ler_grade(s)
        problemas = ex.conferir_grade(p.vidas, grade["qtds"], grade["valores"], grade["subtotais"], grade["vidas"],
                                      grade["valor_total"], s.tol())
        if not problemas and grade == anterior:          # os valores assentaram (duas leituras iguais e conferindo)
            break
        anterior = grade
        time.sleep(0.5)
    if problemas:
        raise ErroFluxo("a grade de vidas não confere: " + "; ".join(problemas), etapa)
    a.valores = ex.valores_por_vida(grade["valores"])
    a.valor_total_grade = grade["valor_total"]
    s.log.info(f"Grade conferida: {grade['vidas']} vida(s), Valor Total {grade['valor_total']} "
               "(soma dos subtotais = Valor Total).")
    _aditivo_e_dental(s, a)
    _mapa(s, f"aditivo_dental_{a.indice + 1}")
    continuar = esperar_visivel(sel.botao_continuar(page), s.t("timeout_tela_ms"), "botão Continuar", etapa)
    _esperar_tela(s, continuar.is_enabled, "o botão Continuar habilitado (Selecionar Planos)", etapa)
    continuar.click()
    _esperar_tela(s, lambda: _tela_da_cotacao(s) == "revisar", "Revisar Cotação", etapa)
    esperar_sem_carregando(page, 15)


def _aditivo_e_dental(s: Sessao, a: Andamento) -> None:
    """Estado final igual ao do vídeo: aditivo presente (AMIL RESGATE SAÚDE I) e o dental marcado em "Aderir". O vídeo não
    mostra se o portal já traz marcados ou se foram clicados: o robô confere e só clica no dental se faltar."""
    page, p = s.page, a.base
    texto = texto_da_pagina(page)
    s.log.info("Aditivo AMIL RESGATE SAÚDE I: " + ("presente." if sel.TEXTO_ADITIVO.search(texto) else
                                                  "não aparece para este plano (segue como o portal oferece)."))
    caixa = sel.checkbox_dental(page)
    try:
        existe = caixa.count() > 0
    except Exception:  # noqa: BLE001
        existe = False
    if not existe:
        a.dental_marcado = False
        if p.dental:
            s.log.warning("O portal não oferece dental para este plano; segue sem dental.")
        return
    marcado = caixa.is_checked()
    s.log.info(f"Dental: {'marcado' if marcado else 'desmarcado'} no portal; pedido: {'aderir' if p.dental else 'não aderir'}.")
    if marcado != p.dental:
        caixa.set_checked(p.dental)
        esperar_sem_carregando(page, 10)
    a.dental_marcado = caixa.is_checked()
    if a.dental_marcado != p.dental:
        raise ErroFluxo(f"o dental ficou {'marcado' if a.dental_marcado else 'desmarcado'}, o pedido quer "
                        f"{'aderir' if p.dental else 'não aderir'}", "planos")


def revisar(s: Sessao, a: Andamento) -> None:
    """Revisar Cotação: lê e confere (falha fechada). O ensaio para aqui, sem "Concluir Cotação"."""
    page, p, etapa = s.page, a.base, "revisar"
    _aviso_etapa(s, a, etapa)
    _esperar_tela(s, lambda: _tela_da_cotacao(s) == "revisar", "Revisar Cotação", etapa)
    esperar_sem_carregando(page, 15)
    texto = texto_da_pagina(page)
    rev = ex.ler_revisao(texto)
    _mapa(s, f"revisar_{a.indice + 1}")
    # Cotação continuada direto na revisão: o dental da tela dos planos não foi visto agora; vale o pedido.
    dental = p.dental if a.dental_marcado is None else a.dental_marcado
    problemas = ex.conferir_revisao(rev, a.alvo.nome, p.total_vidas, p.corretor, a.valor_total_grade, s.tol(), dental)
    if rev.get("cot") and a.cot and rev["cot"] != a.cot:
        problemas.append(f"a revisão é da cotação {rev['cot']}, esperava {a.cot}")
    if rev.get("opp") and a.opp and rev["opp"] != a.opp:
        problemas.append(f"a revisão é da oportunidade {rev['opp']}, esperava {a.opp}")
    r = a.resultado = _resultado(a, protocolo=a.cot or rev.get("cot") or "")
    # A tela mostra um valor por cotação (total_com_iof): na Amil é o valor/mês a partir da 3ª parcela (o preço do plano, o que o
    # corretor compara). O Total Geral da 1ª e 2ª parcelas (50% com o selo) e o total após 12 meses vão para o log e o PDF; a
    # Amil não tem IOF, então total_sem_iof e iof ficam vazios (a tela só os mostra quando existem).
    r.preco_mensal = rev.get("mensal")
    r.total_com_iof = rev.get("mensal")
    r.valores_por_vida = dict(a.valores)
    if problemas:
        raise ErroFluxo("a revisão não confere: " + "; ".join(problemas), etapa)
    s.log.info(f"Revisão {rev['cot']} | {a.alvo.nome}: mensal {rev['mensal']}"
               + (f", 1ª e 2ª parcelas {rev['total_geral']} (50%)" if rev["selo_50"] else f", Total Geral {rev['total_geral']}")
               + f", após 12 meses {rev['total_12_meses']}; validade {rev['validade'] or '?'} (criada {rev['criacao'] or '?'}); "
                 f"tabela {rev['tabela'] or '?'}.")
    if s.ensaio:
        r.status = "ENSAIO_OK"
        r.erro = (f"Ensaio: a oportunidade {a.opp} e a cotação {rev['cot']} (Em Digitação) já foram criadas no portal e "
                  "vencem em 1 dia; nada foi concluído.")
        s.resultados.plano(r)
        a.indice += 1


def _nome_destino(s: Sessao, a: Andamento) -> str:
    """AMIL <apelido do plano> <nome curto da empresa>.pdf. O apelido do plano vem de arquivos.nomes_arquivo e o nome curto
    da empresa é o "nome para achar depois" da Nova cotação (vai no lugar de {versao}; vazio = sem nome)."""
    return nome_pdf_destino(s.cfg, a.base.cnpj, a.cot or "", a.alvo.nome, "", versao=(a.base.apelido or "").upper())


def concluir(s: Sessao, a: Andamento) -> None:
    """PONTO SEM VOLTA: "Concluir Cotação" (a COT vira "Concluída" e o portal gera o PDF). "emitindo" antes do clique."""
    page, p, etapa = s.page, a.base, "concluir"
    _aviso_etapa(s, a, etapa)
    chave = chave_cotacao(s, a)
    botao = esperar_visivel(sel.botao_concluir_cotacao(page), s.t("timeout_tela_ms"), "botão Concluir Cotação", etapa)
    if not botao.is_enabled():
        raise ErroFluxo("o botão Concluir Cotação está desabilitado", etapa)
    item = s.estado.item(chave) or {}
    if item.get("status") not in (None, "digitando"):
        raise ErroFluxo("o registro diz que esta cotação já foi concluída; não concluo de novo", etapa)
    nome_destino = _nome_destino(s, a)
    s.estado.registrar(chave, p, a.alvo.nome, "", "emitindo", obs=f"clicou Concluir Cotação ({a.cot})", protocolo=a.cot,
                       cot_id=a.cot_id, opp=a.opp, nome_destino=nome_destino, pasta_destino=p.pasta_destino)
    a.aguardando = True
    s.log.info(f"Concluindo a cotação {a.cot} ({a.alvo.nome})...")
    botao.click()
    # O portal gera o PDF: "Concluída" + "Gerando PDF…" -> "PDF Gerado". Parar vale aqui só depois de 3 s: a COT é conhecida e
    # fica "emitindo" no registro (a próxima execução a reabre e baixa o PDF, sem criar outra).
    inicio = time.monotonic()
    fim = inicio + s.t("timeout_emissao_ms") / 1000
    while time.monotonic() < fim:
        if _visivel(page.get_by_text(sel.TEXTO_CONCLUIDA)) or _pdf_pronto(s):
            break
        if s.pediu_parar() and time.monotonic() - inicio > 3:
            s.log.warning(f"Parar pedido enquanto o portal concluía a cotação {a.cot}: parando (a cotação fica 'emitindo' e "
                          "a próxima execução reabre e baixa o PDF).")
            raise Parado(etapa)
        if login_na_tela(page):
            raise SessaoCaiu("o portal pediu o login de novo depois do clique", etapa)
        time.sleep(0.4)
    else:
        raise ErroFluxo(f"o portal não confirmou 'Cotação concluída' em {s.t('timeout_emissao_ms') // 1000}s", etapa)
    s.estado.registrar(chave, p, a.alvo.nome, "", "emitida", obs="portal confirmou Concluída", protocolo=a.cot,
                       nome_destino=nome_destino)
    s.log.info(f"Cotação {a.cot} concluída no portal.")
    _baixar_e_registrar(s, a, nome_destino)


def _pdf_pronto(s: Sessao) -> bool:
    """O botão Baixar PDF aparece habilitado (some o "Gerando PDF…")."""
    try:
        botoes = visiveis(sel.botao_baixar_pdf(s.page))
        return bool(botoes) and botoes[0].is_enabled() and not _visivel(s.page.get_by_text(sel.TEXTO_GERANDO_PDF))
    except Exception:  # noqa: BLE001
        return False


def _pdf_valido(caminho: Path, cot: str, nome_sugerido: str, log) -> None:
    dados = caminho.read_bytes()
    if not dados.startswith(b"%PDF") or len(dados) < 5000:
        raise ErroFluxo(f"o arquivo baixado não parece um PDF da cotação ({len(dados)} bytes)", "pdf")
    if cot and cot not in (nome_sugerido or ""):
        raise ErroFluxo(f"o PDF baixado ('{nome_sugerido}') não é da cotação {cot}", "pdf")
    try:                                      # com leitor de PDF disponível, confere também o texto (COT e plano)
        from pypdf import PdfReader
        texto = " ".join((pg.extract_text() or "") for pg in PdfReader(str(caminho)).pages[:3])
        # o texto do PDF traz só os dígitos da cotação (12/11: "5291608", sem "COT-")
        if cot and re.sub(r"\D", "", cot) not in texto:
            log.warning(f"O texto do PDF não cita {cot}; confira o arquivo.")
    except Exception:  # noqa: BLE001  (sem leitor de PDF: vale o nome do arquivo e o cabeçalho %PDF)
        pass


def baixar_pdf(s: Sessao, a: Andamento) -> Path:
    page, etapa = s.page, "pdf"
    inicio = time.monotonic()
    fim = inicio + s.t("timeout_emissao_ms") / 1000
    while not _pdf_pronto(s):
        # Parar vale aqui (depois de 3 s): a COT já está concluída e "emitida" no registro; a próxima execução reabre e baixa.
        if s.pediu_parar() and time.monotonic() - inicio > 3:
            s.log.warning(f"Parar pedido enquanto o portal gerava o PDF da cotação {a.cot}: parando (a próxima execução "
                          "reabre a cotação e baixa o PDF).")
            raise Parado(etapa)
        if login_na_tela(page):
            raise SessaoCaiu("o portal pediu o login de novo antes do PDF", etapa)
        if time.monotonic() >= fim:
            raise ErroFluxo(f"o botão Baixar PDF não ficou pronto em {s.t('timeout_emissao_ms') // 1000}s", etapa)
        time.sleep(0.4)
    botao = visiveis(sel.botao_baixar_pdf(page))[0]
    pasta = Path(s.cfg["saida"]["pasta"]) / "pdfs"
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / nome_pdf_arquivo(s.cfg, a.base.cnpj, a.cot or "", a.alvo.nome)
    with page.expect_download(timeout=s.t("timeout_download_ms")) as baixando:
        botao.click()
    download = baixando.value
    download.save_as(str(destino))
    _pdf_valido(destino, a.cot or "", download.suggested_filename, s.log)
    s.log.info(f"PDF salvo: {destino}")
    return destino


def _baixar_e_registrar(s: Sessao, a: Andamento, nome_destino: str) -> None:
    p, chave = a.base, chave_cotacao(s, a)
    arquivo = baixar_pdf(s, a)
    destino = ""
    if p.pasta_destino:
        try:
            destino = copiar_para_destino(arquivo, p.pasta_destino, nome_destino,
                                          bool(s.cfg["saida"].get("substituir_no_destino", True)), s.log)
        except Exception as e:  # noqa: BLE001
            msg = f"PDF salvo em {arquivo}, mas a cópia para a pasta do cliente falhou: {e}"
            s.log.warning(msg)
            if a.resultado:
                a.resultado.erro = msg
    s.estado.registrar(chave, p, a.alvo.nome, "", "pdf_ok", obs="PDF salvo", protocolo=a.cot, pdf=str(arquivo),
                       pdf_destino=destino, nome_destino=nome_destino)
    r = a.resultado or _resultado(a, protocolo=a.cot or "")
    r.status, r.protocolo, r.pdf_arquivo, r.pdf_destino, r.pdf_nome = "OK", a.cot or "", str(arquivo), destino, nome_destino
    a.aguardando = False
    s.resultados.plano(r)
    a.indice += 1


# ============================ recuperar uma cotação concluída (sem criar outra) ============================

def recuperar(s: Sessao, a: Andamento, alvo: PlanoAlvo, item: dict) -> bool:
    """A COT ficou "emitindo"/"emitida" (caiu depois de Concluir Cotação): reabre a COT pelo id (ou pela lista da
    oportunidade) e baixa o PDF, SEM criar outra. True se baixou. Se o portal ainda a mostra em "Em Digitação", o clique não
    valeu: volta a "digitando" e o robô conclui a MESMA cotação."""
    page, etapa = s.page, "recuperar"
    cot, cot_id = str(item.get("protocolo") or ""), str(item.get("cot_id") or "")
    if not cot:
        return False
    s.log.info(f"Recuperando a cotação {cot} ({alvo.nome}): estava '{item.get('status')}' no registro.")
    garantir_sessao(s)
    abriu = False
    if cot_id:
        page.goto(urljoin(_base(s), f"{sel.ROTA_COTACAO}{cot_id}"))
        page.wait_for_load_state("domcontentloaded")
        abriu = esperar_ate(lambda: cot in texto_da_pagina(page), s.t("timeout_tela_ms") / 1000)
    if not abriu and a.opp_id:                                  # pela lista "Cotações da Oportunidade"
        page.goto(urljoin(_base(s), f"{sel.ROTA_OPORTUNIDADE}{a.opp_id}"))
        page.wait_for_load_state("domcontentloaded")
        esperar_ate(lambda: bool(visiveis(sel.linha_da_cotacao(page, cot))), s.t("timeout_tela_ms") / 1000)
        linhas = visiveis(sel.linha_da_cotacao(page, cot))
        if linhas:
            sel.botao_ver_cotacao(linhas[0]).click()
            abriu = esperar_ate(lambda: cot in texto_da_pagina(page) and sel.ROTA_COTACAO in sel.caminho(page),
                                s.t("timeout_tela_ms") / 1000)
    if not abriu:
        return False
    esperar_sem_carregando(page, 15)
    a.cot, a.cot_id = cot, _id_da_url(page, sel.ROTA_COTACAO) or cot_id
    a.alvos = [alvo]
    a.indice = 0
    texto = texto_da_pagina(page)
    concluida = bool(sel.TEXTO_CONCLUIDA.search(texto)) or _pdf_pronto(s)
    chave = chave_cotacao(s, a, alvo)
    if not concluida:
        s.log.warning(f"A cotação {cot} ainda está em Digitação no portal: o clique em Concluir não valeu. Volta a 'digitando'.")
        s.estado.registrar(chave, a.base, alvo.nome, "", "digitando", obs="recuperação: continua em Digitação", protocolo=cot,
                           cot_id=a.cot_id)
        return False
    a.resultado = _resultado(a, alvo, protocolo=cot)
    _mapa(s, "recuperar")
    _baixar_e_registrar(s, a, str(item.get("nome_destino") or _nome_destino(s, a)))
    return True


# ============================ sair ============================

def sair_do_portal(s: Sessao, prazo_s: float = 30) -> bool:
    """Logout pelo botão "Sair" do menu lateral. Só com o robô parado. Depois de sair, o próximo login pede um código novo."""
    page = s.page
    if login_na_tela(page):
        return True
    if not logado(page):
        return False
    botoes = visiveis(sel.botao_sair(page))
    if not botoes:
        return False
    botoes[0].click()
    return esperar_ate(lambda: login_na_tela(page), prazo_s)
