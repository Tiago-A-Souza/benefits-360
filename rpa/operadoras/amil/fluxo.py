"""O fluxo de um pedido da Amil: reabre (ou cria, uma vez) a oportunidade e faz uma cotação por plano.

Antes de abrir o portal, o registro diz o que falta (preparar): oportunidade já conhecida = reaberta, nunca recriada;
cotação concluída = pulada; cotação em "digitando" = continuada (a mesma COT); cotação que caiu depois de "Concluir
Cotação" = recuperada (reabre a COT e baixa o PDF, SEM criar outra).
"""
from __future__ import annotations

from nucleo.credenciais import ocultar
from nucleo.modelo import ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, ErroLogin, Parado
from nucleo.texto import norm

from . import etapas as et
from .etapas import Andamento, Sessao
from .login import entrar
from .telas import SessaoCaiu


def preparar(s: Sessao, pedido) -> Andamento | None:
    """O que falta no pedido, pelo registro. 1ª barreira contra criar de novo."""
    a = Andamento(base=pedido, alvos=[])
    opp = s.estado.item(et.chave_oportunidade(s, pedido))
    if opp is not None:
        if opp["status"] == "emitindo":
            msg = ("o robô clicou em 'Concluir Oportunidade' para esta empresa e não confirmou o número (OPP). Confira em "
                   "'Andamentos' no portal; o robô não cria outra oportunidade sozinho")
            for alvo in pedido.planos:
                s.resultados.plano(et._resultado(a, alvo, status="VERIFICAR", erro=msg))
            s.log.warning(f"[{pedido.id}] {msg}.")
            return None
        a.opp, a.opp_id = opp.get("protocolo"), str(opp.get("url_id") or "")
    pendentes = []
    for alvo in pedido.planos:
        achado = s.estado.procurar(pedido, alvo)
        if achado is None:
            pendentes.append(alvo)
            continue
        _chave, item = achado
        status = item["status"]
        if status == "pdf_ok":
            if et.reemissao_pedida(s, item):
                s.log.info(f"[{pedido.id}] {alvo.nome}: emitido antes ({item.get('protocolo')}); o corretor pediu para emitir "
                           "de novo: vai numa cotação nova da mesma oportunidade.")
                a.substituir[norm(alvo.nome)] = str(item.get("protocolo") or "")
                pendentes.append(alvo)
                continue
            s.resultados.plano(ResultadoPlano(
                pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=alvo.nome, status="PULADO",
                protocolo=item.get("protocolo", ""), pdf_arquivo=item.get("pdf", ""), pdf_destino=item.get("pdf_destino", ""),
                pdf_nome=item.get("nome_destino", ""), erro=et.MENSAGEM_REGISTRO["pdf_ok"]))
            s.log.info(f"[{pedido.id}] {alvo.nome}: PULADO ({et.MENSAGEM_REGISTRO['pdf_ok']}).")
        elif status == "digitando":
            a.reaproveitar[norm(alvo.nome)] = item
            pendentes.append(alvo)
        elif s.ensaio:
            s.resultados.plano(et._resultado(a, alvo, status="VERIFICAR", protocolo=item.get("protocolo", ""),
                                             erro=f"{et.MENSAGEM_REGISTRO.get(status, status)} (o ensaio não mexe nela)"))
        else:
            a.recuperar.append((alvo, item))
    a.alvos = pendentes
    if not pendentes and not a.recuperar:
        return None
    return a


def processar_pedido(s: Sessao, pedido) -> None:
    a = preparar(s, pedido)
    if a is None:
        s.log.info(f"[{pedido.id}] nada a fazer.")
        return
    nomes = [x.nome for x in a.alvos] + [x.nome + " (recuperar)" for x, _ in a.recuperar]
    s.log.info(f"===== Pedido {pedido.id} (linha {pedido.linha}) | CNPJ {pedido.cnpj} | {pedido.total_vidas} vidas | "
               f"planos: {nomes} =====")
    if s.ensaio:
        s.log.warning(f"[{pedido.id}] ENSAIO na Amil: o portal só mostra os valores depois de criar a oportunidade e uma "
                      "cotação 'Em Digitação' por plano (vencem em 1 dia). O ensaio cria isso e para em Revisar Cotação, "
                      "sem Concluir Cotação.")
    etapa = "inicio"
    try:
        _percorrer(s, a)
    except Parado as e:
        inicio = a.indice
        if a.alvo is not None and a.aguardando:
            _registrar_falha(s, a, e.etapa,
                             ErroFluxo("o corretor pediu para parar enquanto o portal concluía a cotação", e.etapa))
            inicio += 1
        s.log.warning(f"[{pedido.id}] parado a pedido do corretor (tela {e.etapa}).")
        for resto in a.alvos[inicio:]:
            s.resultados.plano(et._resultado(a, resto, status="PARADO", etapa_erro=e.etapa,
                                             erro="parado a pedido do corretor antes de concluir a cotação"))
        raise
    except Exception as e:  # noqa: BLE001
        etapa = getattr(e, "etapa", "") or etapa
        _registrar_falha(s, a, etapa, e)
        resto_msg = (f"não processado: o pedido parou na etapa {etapa}; rode de novo (a oportunidade {a.opp} existe e é "
                     "reaberta, sem criar outra)" if a.opp else f"não processado: o pedido parou na etapa {etapa}; rode de novo")
        for resto in a.alvos[a.indice + 1:]:
            s.resultados.plano(et._resultado(a, resto, status="ERRO", etapa_erro=etapa, erro=resto_msg,
                                             protocolo=a.opp or ""))
        if isinstance(e, ErroLogin):
            raise


def _percorrer(s: Sessao, a: Andamento) -> None:
    pedido = a.base
    # 1. cotações que caíram depois de "Concluir Cotação": recupera o PDF, sem criar outra
    pendentes = list(a.alvos)
    for alvo, item in a.recuperar:
        r = Andamento(base=pedido, alvos=[alvo], opp=a.opp, opp_id=a.opp_id, razao_social=a.razao_social)
        try:
            if et.recuperar(s, r, alvo, item):
                continue
        except SessaoCaiu:
            entrar(s)
            if et.recuperar(s, r, alvo, item):
                continue
        novo = s.estado.item(et.chave_cotacao(s, a, alvo)) or {}
        if novo.get("status") == "digitando":           # o clique não valeu: conclui a MESMA cotação
            a.reaproveitar[norm(alvo.nome)] = novo
            pendentes.append(alvo)
        else:
            s.resultados.plano(et._resultado(a, alvo, status="VERIFICAR", protocolo=item.get("protocolo", ""),
                                             erro="o robô não conseguiu reabrir a cotação para baixar o PDF: confira em "
                                                  "'Cotações da Oportunidade' no portal e baixe à mão"))
    a.alvos, a.indice = pendentes, 0
    if not a.alvos:
        return
    # 2. oportunidade (reabre a conhecida ou cria uma) e uma cotação por plano
    recomecos = 0
    et.oportunidade(s, a)
    while a.alvo is not None:
        a.cot, a.cot_id, a.resultado, a.valores, a.valor_total_grade, a.dental_marcado = None, "", None, {}, None, None
        try:
            et.cotacao(s, a)
            et.planos(s, a)
            et.revisar(s, a)
            if not s.ensaio:
                et.concluir(s, a)
        except SessaoCaiu:
            if a.aguardando:
                raise
            recomecos += 1
            if recomecos > 2:
                raise
            s.log.warning("A sessão do portal acabou no meio da cotação; entrando de novo e continuando a mesma cotação.")
            entrar(s, pode_parar=True)
            item = s.estado.item(et.chave_cotacao(s, a)) or {}
            if item.get("status") == "digitando" and item.get("cot_id"):
                a.reaproveitar[norm(a.alvo.nome)] = item
            continue
        if a.alvo is not None:                       # próximo plano: volta à oportunidade (já criada)
            et.reabrir_oportunidade(s, a)


def _registrar_falha(s: Sessao, a: Andamento, etapa: str, erro: Exception) -> None:
    try:                                   # nunca um mapa da tela de login depois de digitar (_mapa confere)
        et._mapa(s, f"ERRO_{etapa}", forcar=True)
    except Exception:  # noqa: BLE001
        pass
    msg = ocultar((str(erro).splitlines() or [type(erro).__name__])[0][:600])
    status = "ERRO"
    if a.alvo is None:
        s.log.error(f"[{a.base.id}] falha na etapa {etapa}: {msg}")
        return
    item = s.estado.item(et.chave_cotacao(s, a)) or {}
    opp_item = s.estado.item(et.chave_oportunidade(s, a.base)) or {}
    if opp_item.get("status") == "emitindo":
        status = "VERIFICAR"
        msg = (f"{msg} | ATENÇÃO: o robô clicou em Concluir Oportunidade e não confirmou o número. Confira em 'Andamentos' "
               "no portal; o robô não cria outra oportunidade sozinho.")
    elif item.get("status") in ("emitindo", "emitida"):
        status = "VERIFICAR"
        msg = (f"{msg} | ATENÇÃO: a cotação {item.get('protocolo') or a.cot or '?'} foi concluída (ou o clique não "
               "confirmou). Na próxima execução o robô a reabre pela oportunidade e baixa o PDF, sem criar outra.")
    elif item.get("status") == "digitando":
        msg = f"{msg} | A cotação {item.get('protocolo')} ficou em Digitação: peça de novo e o robô a continua."
    tipo = "dado do pedido" if isinstance(erro, ErroDados) else "tela"
    s.log.error(f"[{a.base.id}] falha na etapa {etapa} ({tipo}): {msg}")
    r = a.resultado or et._resultado(a)
    r.status, r.erro, r.etapa_erro = status, msg, etapa
    r.protocolo = r.protocolo or a.cot or a.opp or ""
    s.resultados.plano(r)
