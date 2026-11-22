"""O fluxo de um pedido da Porto: uma cotação por plano, sempre via Criar nova cotação.

Antes de abrir o portal, o registro diz o que falta. Cotação pdf_ok = pulada. Caiu depois de
Gerar orçamento = recupera pela lista (Visualizar), sem gerar outra. O ensaio para no passo 3.
"""
from __future__ import annotations

from nucleo.credenciais import ocultar
from nucleo.modelo import ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, ErroLogin, Parado
from nucleo.texto import norm

from . import etapas as et
from .etapas import Andamento, Sessao, com_versoes
from .login import entrar
from .telas import SessaoCaiu


def preparar(s: Sessao, pedido) -> Andamento | None:
    alvos = com_versoes(pedido, list(pedido.planos))
    a = Andamento(base=pedido, alvos=[])
    pendentes = []
    for alvo in alvos:
        achado = s.estado.procurar(pedido.na_versao(alvo.versao) if alvo.versao else pedido, alvo)
        if achado is None:
            pendentes.append(alvo)
            continue
        _chave, item = achado
        status = item["status"]
        if status == "pdf_ok":
            if et.reemissao_pedida(s, item):
                a.substituir[norm(alvo.nome)] = str(item.get("protocolo") or "")
                pendentes.append(alvo)
                continue
            s.resultados.plano(ResultadoPlano(
                pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=alvo.nome,
                acomodacao=alvo.acomodacao or pedido.acomodacao, status="PULADO",
                protocolo=item.get("protocolo", ""), pdf_arquivo=item.get("pdf", ""),
                pdf_destino=item.get("pdf_destino", ""), pdf_nome=item.get("nome_destino", ""),
                versao=alvo.versao or pedido.coparticipacao, erro=et.MENSAGEM_REGISTRO["pdf_ok"]))
            s.log.info(f"[{pedido.id}] {alvo.nome}: PULADO ({et.MENSAGEM_REGISTRO['pdf_ok']}).")
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
    nomes = [x.rotulo_completo() for x in a.alvos] + [x.nome + " (recuperar)" for x, _ in a.recuperar]
    s.log.info(f"===== Pedido {pedido.id} | CNPJ {pedido.cnpj} | {pedido.total_vidas} vidas | planos: {nomes} =====")
    if s.ensaio:
        s.log.warning(f"[{pedido.id}] ENSAIO na Porto: preenche até o passo 3 (plano selecionado) e para SEM "
                      "Gerar orçamento. Nada é criado no portal.")
    try:
        _percorrer(s, a)
    except Parado as e:
        s.log.warning(f"[{pedido.id}] parado a pedido do corretor (tela {e.etapa}).")
        for resto in a.alvos[a.indice:]:
            s.resultados.plano(et._resultado(a, resto, status="PARADO", etapa_erro=e.etapa,
                                             erro="parado a pedido do corretor antes de gerar o orçamento"))
        raise
    except Exception as e:  # noqa: BLE001
        etapa = getattr(e, "etapa", "") or "fluxo"
        _registrar_falha(s, a, etapa, e)
        for resto in a.alvos[a.indice + 1:]:
            s.resultados.plano(et._resultado(a, resto, status="ERRO", etapa_erro=etapa,
                                             erro=f"não processado: o pedido parou na etapa {etapa}"))
        if isinstance(e, ErroLogin):
            raise


def _percorrer(s: Sessao, a: Andamento) -> None:
    for alvo, item in a.recuperar:
        r = Andamento(base=a.base, alvos=[alvo], razao_social=a.razao_social)
        try:
            if et.recuperar(s, r, alvo, item):
                continue
        except SessaoCaiu:
            entrar(s)
            if et.recuperar(s, r, alvo, item):
                continue
        s.resultados.plano(et._resultado(r, alvo, status="VERIFICAR", protocolo=item.get("protocolo", ""),
                                         erro="o robô não achou a cotação na lista pelo CNPJ: confira no portal "
                                              "e baixe à mão (não gere outra)"))
    if not a.alvos:
        return
    while a.alvo is not None:
        a.numero = None
        a.resultado = None
        a.aguardando = False
        et.criar_nova_cotacao(s, a)
        et.dados_iniciais(s, a)
        et.produto_vidas(s, a)
        et.comissao(s, a)
        et.selecionar_plano(s, a)
        if s.ensaio:
            et.ensaiar_ok(s, a)
            et.voltar_lista(s)
            a.indice += 1
            continue
        if not s.pode_gerar():
            raise ErroFluxo("Gerar orçamento recusado: a emissão não está liberada", "orcamento")
        et.gerar_orcamento(s, a)
        et.imprimir_pdf(s, a)
        et.voltar_lista(s)
        a.indice += 1


def _registrar_falha(s: Sessao, a: Andamento, etapa: str, erro: Exception) -> None:
    try:
        et._mapa(s, f"ERRO_{etapa}", forcar=True)
    except Exception:  # noqa: BLE001
        pass
    msg = ocultar((str(erro).splitlines() or [type(erro).__name__])[0][:600])
    status = "ERRO"
    if a.alvo is None:
        s.log.error(f"[{a.base.id}] falha na etapa {etapa}: {msg}")
        return
    item = s.estado.item(et.chave_cotacao(s, a.base, a.alvo)) or {}
    if item.get("status") in ("emitindo", "emitida"):
        status = "VERIFICAR"
        msg = (f"{msg} | ATENÇÃO: o robô clicou em Gerar orçamento e a cotação {item.get('protocolo') or a.numero or '?'} "
               "pode existir. Na próxima execução o robô procura na lista pelo CNPJ e baixa o PDF, sem gerar outra.")
    tipo = "dado do pedido" if isinstance(erro, ErroDados) else "tela"
    s.log.error(f"[{a.base.id}] falha na etapa {etapa} ({tipo}): {msg}")
    s.resultados.plano(et._resultado(a, status=status, etapa_erro=etapa, erro=msg, protocolo=item.get("protocolo") or a.numero or ""))
