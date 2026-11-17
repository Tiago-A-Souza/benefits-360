"""Máquina de estados: olha a URL, descobre a tela e chama a etapa certa.

Assim o robô não depende de uma sequência fixa: telas que nem sempre aparecem
(idades exatas, modal do Cuidado 360°) e o atalho de "Copiar cotação" são
tratados naturalmente.
"""
from __future__ import annotations

import time

from playwright.sync_api import Error as PWError

from . import etapas as et
from . import seletores as sel
from .etapas import Andamento, Sessao
from .login import entrar, tela_modulos_visivel
from .telas import TelaReiniciou
from nucleo.modelo import PlanoAlvo, ResultadoPlano
from nucleo.credenciais import ocultar
from nucleo.navegador import ErroDados, ErroFluxo, ErroLogin, Parado, visiveis

ETAPAS = {
    "modulos": et.tela_modulos,
    "painel": et.tela_painel,
    "dados_empresa": et.dados_empresa,
    "cuidado_360": et.cuidado_360,
    "congenere": et.congenere,
    "vidas": et.vidas,
    "idades": et.idades,
    "planos": et.planos,
    "comparacao": et.comparacao,
    "resumo": et.resumo,
    "emitida": et.emitida,
}


def identificar_etapa(s: Sessao) -> str:
    fim = time.monotonic() + s.t("timeout_tela_ms") / 1000
    while time.monotonic() < fim:
        caminho = sel.caminho(s.page)      # só o caminho: "?volta=.../LoginGeral.aspx" não confunde
        if sel.ROTA_EMITIDA in caminho:
            # 15/11: depois de "Sair da cotação" o portal novo mostra "Selecione um módulo" na MESMA URL da cotação emitida
            # (Simulador.aspx?Token=...&InFlgViaSimulador=True); só o caminho levava o robô a procurar "Voltar para a home".
            if tela_modulos_visivel(s.page):
                return "modulos"
            return "emitida"
        if sel.ROTA_PAINEL in caminho:
            return "painel"
        for nome, pedaco in sel.ROTAS:
            if pedaco in caminho:
                return nome
        if sel.ROTA_LOGIN in caminho:
            if tela_modulos_visivel(s.page):
                return "modulos"
            if visiveis(sel.login_campo_cpf(s.page)):
                return "login"
        time.sleep(0.3)
    raise ErroFluxo(f"não reconheço a tela atual ({s.page.url})", "desconhecida")


def _parse_rotulo(texto: str) -> PlanoAlvo:
    if " | " in texto:
        nome, acomod = texto.split(" | ", 1)
        return PlanoAlvo(nome, acomod)
    return PlanoAlvo(texto, None)


def preparar(s: Sessao, pedido) -> Andamento | None:
    """Decide o que falta fazer no pedido, consultando o registro de andamento.

    Esta é a primeira barreira contra reemissão. A segunda fica na tela de planos,
    já com o nome e a acomodação exatos do portal (etapas._ja_emitida).
    """
    base = list(pedido.planos)
    resolver = False
    if pedido.criterio_quantidade:
        salvos = s.estado.planos_resolvidos(pedido)   # mesmo CNPJ e mesmos parâmetros
        if salvos:
            base = [_parse_rotulo(x) for x in salvos]
        else:
            resolver = True
    pendentes = []
    vistos: set[str] = set()
    for alvo in et.com_versoes(pedido, base):   # "Com e sem": plano 1 com, plano 1 sem, plano 2 com...
        versao = pedido.na_versao(alvo.versao) if alvo.versao else pedido
        achado = None if s.ensaio else s.estado.procurar(versao, alvo)
        if achado is not None and et.reemissao_pedida(s, achado[1]):
            s.log.info(f"[{pedido.id}] {alvo.rotulo_completo()}: emitida antes (protocolo "
                       f"{achado[1].get('protocolo')}); o corretor pediu na tela para emitir de novo.")
            achado = None
        if achado is None:
            pendentes.append(alvo)
            continue
        chave, item = achado
        status = item["status"]
        if chave in vistos:
            continue
        vistos.add(chave)
        situacao = "PULADO" if status == "pdf_ok" else "VERIFICAR"
        msg = et.MENSAGEM_REGISTRO.get(status, status)
        s.resultados.plano(ResultadoPlano(
            pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=item.get("plano") or alvo.nome,
            acomodacao=item.get("acomodacao") or alvo.acomodacao or "", status=situacao,
            protocolo=item.get("protocolo", ""), pdf_arquivo=item.get("pdf", ""),
            pdf_destino=item.get("pdf_destino", ""), pdf_nome=item.get("nome_destino", ""), erro=msg,
            versao=versao.coparticipacao))
        s.log.info(f"[{pedido.id}] {alvo.rotulo_completo()}: {situacao} ({msg}).")
    if s.ensaio:
        pendentes = pendentes[:1]   # ensaio calibra as telas: um plano por pedido basta
    if not pendentes and not resolver:
        return None
    return Andamento(base=pedido, alvos=pendentes, resolver_por_criterio=resolver)


_MAX_REINICIOS = 6      # vezes que um pedido pode ser retomado do começo depois de o portal travar e voltar ao começo


def garantir_inicio(s: Sessao) -> None:
    """Todo pedido começa na tela de módulos (ou num assistente novo, vazio)."""
    try:
        etapa = identificar_etapa(s)
    except ErroFluxo:
        etapa = "desconhecida"
    if etapa in ("modulos", "painel"):   # o painel "Estou em cotações" também é um começo
        return
    if etapa == "login":
        entrar(s, insistir=False)     # já dentro do pedido: "acesso ativo" para na hora
        return
    if etapa == "dados_empresa":
        try:
            et.esperar_tela(s.page, "dados_empresa", s.cfg)
            if et.assistente_novo(s):
                return   # assistente novo ("Comece por aqui" com o CNPJ vazio)
        except Exception:  # noqa: BLE001
            pass
    s.log.info(f"Começo de pedido fora da tela de módulos ({etapa}); voltando ao início.")
    _recompor(s)
    if et.no_cotador(s.page) and not et.assistente_novo(s):
        # Nunca começar um pedido na tela de outro (ex.: o resumo do pedido anterior).
        raise ErroFluxo("não consegui voltar ao começo da cotação para este pedido; nada foi feito nele", "inicio")


def processar_pedido(s: Sessao, pedido) -> None:
    a = preparar(s, pedido)
    if a is None:
        s.log.info(f"[{pedido.id}] nada a fazer.")
        return
    s.log.info(f"===== Pedido {pedido.id} (linha {pedido.linha}) | CNPJ {pedido.cnpj} | "
               f"{pedido.total_vidas} vidas | planos: "
               f"{[x.rotulo_completo() for x in a.alvos] or f'menor_preco:{pedido.criterio_quantidade}'} =====")
    etapa = "inicio"
    visitas: dict[str, int] = {}
    reinicios = 0
    limite = 4 + 2 * max(1, len(a.alvos) or (pedido.criterio_quantidade or 1))
    try:
        garantir_inicio(s)
        while not a.terminou:
            etapa = identificar_etapa(s)
            # Ponto seguro para parar: entre uma tela e outra, nunca com emissão em andamento
            # (na tela "emitida" o protocolo já existe: o robô termina de baixar o PDF antes).
            if s.pediu_parar() and etapa != "emitida" and not a.aguardando_emissao:
                raise Parado(etapa)
            s.aviso("etapa", etapa="modulos" if etapa == "painel" else etapa, pedido=pedido.id,
                    plano=a.alvo.rotulo_completo() if a.alvo else "", indice=a.indice, total=len(a.alvos))
            visitas[etapa] = visitas.get(etapa, 0) + 1
            if visitas[etapa] > limite:
                raise ErroFluxo(f"o fluxo voltou {visitas[etapa]} vezes à tela {etapa}; parei", etapa)
            if etapa == "login":
                # Com emissão em andamento o login não pode ser interrompido: o robô precisa voltar
                # para ler o protocolo da cotação que talvez já tenha saído.
                entrar(s, pode_parar=not a.aguardando_emissao, insistir=False)
                continue
            try:
                ETAPAS[etapa](s, a)
            except TelaReiniciou:
                # a tela travada foi recarregada e o portal voltou ao começo: retoma o pedido de lá (nada foi emitido).
                # 15/11 (3 robôs juntos): chegou a travar 4 vezes no mesmo pedido e todas se recuperaram.
                reinicios += 1
                if reinicios > _MAX_REINICIOS:
                    raise ErroFluxo(f"o portal travou e voltou ao começo {reinicios} vezes neste pedido; parei", etapa) from None
                visitas["dados_empresa"] = max(0, visitas.get("dados_empresa", 0) - 1)    # a retomada não conta como "voltar à tela"
                visitas[etapa] = max(0, visitas.get(etapa, 0) - 1)
                s.log.warning(f"[{pedido.id}] o portal voltou ao começo depois de recarregar a tela {etapa}; "
                              "retomando o pedido desde a tela da empresa.")
                continue
    except Parado as e:
        inicio = a.indice
        if a.alvo is not None and (a.aguardando_emissao or (
                not s.ensaio and _status_registrado(s, a).get("status") in ("emitindo", "emitida"))):
            # Defesa extra: se o plano atual já passou do clique de emitir, ele NÃO é "parado antes
            # de emitir". Fica como "Conferir no portal", e o registro continua bloqueando reemissão.
            _registrar_falha(s, a, e.etapa, ErroFluxo("o corretor pediu para parar durante a emissão", e.etapa))
            inicio = a.indice + 1
        s.log.warning(f"[{pedido.id}] parado a pedido do corretor (tela {e.etapa}); "
                      "os planos que não começaram não foram emitidos.")
        for resto in a.alvos[inicio:]:
            s.resultados.plano(ResultadoPlano(
                pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=resto.nome,
                acomodacao=resto.acomodacao or "", razao_social=a.razao_social, status="PARADO",
                etapa_erro=e.etapa, erro="parado a pedido do corretor antes de emitir",
                versao=resto.versao or pedido.coparticipacao))
        if e.etapa != "login":
            _recompor(s)
        raise
    except Exception as e:  # noqa: BLE001  (qualquer falha: registra pelo estado e segue para o próximo pedido)
        _registrar_falha(s, a, getattr(e, "etapa", "") or etapa, e)
        for resto in a.alvos[a.indice + 1:]:
            s.resultados.plano(ResultadoPlano(
                pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=resto.nome,
                acomodacao=resto.acomodacao or "", razao_social=a.razao_social, status="ERRO",
                etapa_erro=etapa, erro=f"não processado: o pedido parou na etapa {etapa}; rode de novo",
                versao=resto.versao or pedido.coparticipacao))
        if isinstance(e, ErroLogin):
            raise   # sem login, nenhum outro pedido anda: o trabalho para (e o robô não tenta entrar de novo)
        _recompor(s)


def _status_registrado(s: Sessao, a: Andamento) -> dict:
    """Item do registro do plano em andamento (pela chave real, se já houver plano na tela)."""
    p = a.pedido
    if a.plano_tela is not None:
        return s.estado.item(s.estado.chave(p, a.plano_tela.nome, a.plano_tela.acomodacao)) or {}
    if a.alvo is not None:
        achado = s.estado.procurar(p, a.alvo)
        return achado[1] if achado else {}
    return {}


def _registrar_falha(s: Sessao, a: Andamento, etapa: str, erro: Exception) -> None:
    p = a.pedido
    try:
        s.mapa.registrar(s.page, f"ERRO_{etapa}", forcar=True)
    except Exception:  # noqa: BLE001
        pass
    alvo = a.alvo
    status = "ERRO"
    msg = ocultar((str(erro).splitlines() or [type(erro).__name__])[0][:400])
    if not s.ensaio:
        item = _status_registrado(s, a)
        if item.get("status") == "emitindo":
            status = "VERIFICAR"
            msg = (f"{msg} | ATENÇÃO: o robô clicou em emitir e não confirmou o protocolo. Confira em "
                   "'Cotações emitidas' no portal; o robô não vai reemitir este plano sozinho.")
        elif item.get("status") == "emitida":
            status = "VERIFICAR"
            msg = (f"{msg} | Cotação emitida (protocolo {item.get('protocolo')}), mas o PDF não foi salvo. "
                   + ("A próxima execução tenta baixar de novo, sem reemitir." if s.cfg.get("recuperar_pdf_automatico")
                      else "Baixe à mão no portal, em Cotações emitidas, e marque como resolvida na tela: "
                           "o robô não tenta de novo sozinho."))
    tipo = "dado da planilha" if isinstance(erro, ErroDados) else "tela"
    s.log.error(f"[{p.id}] falha na etapa {etapa} ({tipo}): {msg}")
    r = a.resultado or ResultadoPlano(pedido_id=p.id, linha=p.linha, cnpj=p.cnpj,
                                      plano=alvo.nome if alvo else "", acomodacao=(alvo.acomodacao or "") if alvo else "",
                                      versao=p.coparticipacao)
    r.razao_social = r.razao_social or a.razao_social
    r.status, r.erro, r.etapa_erro = status, msg, etapa
    s.resultados.plano(r)


def _recompor(s: Sessao) -> None:
    """Depois de uma falha, volta à tela de módulos (ou a um assistente novo) para o próximo pedido.

    Nunca volta à página de login com a sessão do portal viva (o portal recusaria um segundo acesso): se
    não conseguir sair da cotação, só registra; o próximo pedido tenta de novo de onde a tela está."""
    try:
        et.sair_da_cotacao(s)
    except Parado:
        return
    except ErroLogin:
        raise
    except Exception as e:  # noqa: BLE001
        resumo = ocultar((str(e).splitlines() or [type(e).__name__])[0][:300])
        s.log.warning(f"não consegui voltar ao início ({resumo}). O robô não volta à página de login com a "
                      "sessão do portal aberta; o próximo pedido tenta de novo.")


def recuperar_pdfs(s: Sessao) -> None:
    """Itens com protocolo mas sem PDF: tenta baixar de novo pela página da emissão."""
    from .etapas import baixar_pdf
    from nucleo.saidas import copiar_para_destino, nome_pdf_destino
    from . import extracao as ex

    if not s.cfg.get("recuperar_pdf_automatico"):
        for chave, item in s.estado.pendencias():
            s.log.warning(f"PENDENTE ({item['status']}): {item.get('plano')} | protocolo {item.get('protocolo', '-')} "
                          "— o robô não tenta de novo sozinho; confira e baixe no portal, em Cotações emitidas.")
        return
    for chave, item in s.estado.pendencias():
        if item.get("status") != "emitida":
            s.log.warning(f"PENDENTE ({item['status']}): {chave} — confira no portal.")
            continue
        url = item.get("url_emissao")
        protocolo = item.get("protocolo")
        s.log.info(f"Recuperando PDF do protocolo {protocolo} ({item['plano']})...")

        class _P:  # o registro só precisa de id e cnpj
            id, cnpj = item["pedido_id"], item["cnpj"]
        try:
            if not url:
                raise ErroFluxo("sem URL da emissão", "recuperacao")
            s.page.goto(url)
            texto = s.page.locator("body").inner_text(timeout=s.t("timeout_tela_ms"))
            if ex.ler_protocolo(texto) != protocolo:
                raise ErroFluxo("a página da emissão não mostra mais esse protocolo", "recuperacao")
            arquivo = baixar_pdf(s, item["cnpj"], protocolo, item["plano"])
            destino, nota = "", "PDF recuperado em nova execução"
            nome_destino = item.get("nome_destino") or nome_pdf_destino(s.cfg, item["cnpj"], protocolo, item["plano"])
            if item.get("pasta_destino"):
                try:
                    destino = copiar_para_destino(
                        arquivo, item["pasta_destino"], nome_destino,
                        bool(s.cfg["saida"].get("substituir_no_destino", True)), s.log)
                except Exception as e:  # noqa: BLE001
                    nota += f"; a cópia para a pasta do cliente falhou: {e}"
                    s.log.warning(nota)
            s.estado.registrar(chave, _P, item["plano"], item.get("acomodacao"), "pdf_ok",
                               obs="PDF recuperado", pdf=str(arquivo), pdf_destino=destino)
            s.resultados.plano(ResultadoPlano(
                pedido_id=item["pedido_id"], linha=0, cnpj=item["cnpj"], plano=item["plano"],
                acomodacao=item.get("acomodacao", ""), status="OK", protocolo=protocolo,
                pdf_arquivo=str(arquivo), pdf_destino=destino, pdf_nome=nome_destino, erro=nota))
        except Exception as e:  # noqa: BLE001
            s.estado.registrar(chave, _P, item["plano"], item.get("acomodacao"), "pdf_manual",
                               obs=f"recuperação falhou: {e}")
            s.log.error(f"Não consegui recuperar o PDF do protocolo {protocolo}: baixe à mão. ({e})")
    # A recuperação para na página da emissão (sessão viva): o próximo pedido volta ao início pelos botões dela.
    # Nunca recarregar o login aqui: com a sessão viva o portal recusaria um segundo acesso.
    entrar(s)
