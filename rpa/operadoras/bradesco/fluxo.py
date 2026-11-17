"""O pedido da Bradesco do começo ao fim: um processo por empresa, um cálculo (e um PDF) por plano e versão.

O cotador novo é uma página só (as telas não mudam a URL): o robô segue a ordem do vídeo e confere o título de
cada tela. Se a sessão cair antes do "Gerar processo", ele entra de novo e recomeça o pedido (nada oficial existia);
depois do clique, nunca gera outro processo: fica em "Conferir no portal".
"""
from __future__ import annotations

from nucleo.credenciais import ocultar
from nucleo.modelo import PlanoAlvo, ResultadoPlano
from nucleo.navegador import ErroDados, ErroFluxo, ErroLogin, Parado
from nucleo.texto import norm

from . import etapas as et
from .etapas import Andamento, Sessao
from .login import entrar
from .pedido import DENTAL_ANTIGO
from .telas import SessaoCaiu, login_na_tela


def _parse_rotulo(texto: str) -> PlanoAlvo:
    if " | " in texto:
        nome, acomod = texto.split(" | ", 1)
        return PlanoAlvo(nome, acomod)
    return PlanoAlvo(texto, None)


def preparar(s: Sessao, pedido) -> Andamento | None:
    """O que falta no pedido, pelo registro. 1ª barreira contra gerar de novo (a 2ª fica no Resultado)."""
    base = list(pedido.planos)
    resolver = False
    if pedido.criterio_quantidade:
        salvos = s.estado.planos_resolvidos(pedido)
        if salvos:
            base = [_parse_rotulo(x) for x in salvos]
        else:
            resolver = True
    if not s.ensaio and s.cfg.get("teste_repetir"):
        et.liberar_para_teste(s, pedido, et.com_versoes(pedido, base))
    pendentes, vistos = [], set()
    for alvo in et.com_versoes(pedido, base):
        versao = pedido.na_versao(alvo.versao) if alvo.versao else pedido
        achado = None if s.ensaio else s.estado.procurar(versao, alvo)
        if achado is not None and et.reemissao_pedida(s, achado[1]):
            s.log.info(f"[{pedido.id}] {alvo.rotulo_completo()}: emitido antes (processo {achado[1].get('protocolo')}); "
                       "o corretor pediu na tela para emitir de novo: vai num processo novo.")
            achado = None
        if achado is None:
            pendentes.append(alvo)
            continue
        chave, item = achado
        if chave in vistos:
            continue
        vistos.add(chave)
        situacao = "PULADO" if item["status"] == "pdf_ok" else "VERIFICAR"
        msg = et.MENSAGEM_REGISTRO.get(item["status"], item["status"])
        s.resultados.plano(ResultadoPlano(
            pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=item.get("plano") or alvo.nome,
            acomodacao=item.get("acomodacao") or alvo.acomodacao or "", status=situacao,
            protocolo=item.get("protocolo", ""), pdf_arquivo=item.get("pdf", ""), pdf_destino=item.get("pdf_destino", ""),
            pdf_nome=item.get("nome_destino", ""), erro=msg, versao=versao.coparticipacao))
        s.log.info(f"[{pedido.id}] {alvo.rotulo_completo()}: {situacao} ({msg}).")
    if not pendentes and not resolver:
        return None
    a = Andamento(base=pedido, alvos=pendentes, resolver_por_criterio=resolver)
    if s.ensaio:
        return a
    proc = s.estado.item(et.chave_processo(s, pedido))
    if norm(pedido.dental) != norm(DENTAL_ANTIGO):
        s.log.info(f"[{pedido.id}] Registro: o dental '{pedido.dental}' entra só na chave de registro do processo (outro "
                   "dental, outro preço, outro processo); no portal o robô escolhe o dental no Resultado "
                   "('Sem plano dental' é o padrão do vídeo).")
    if proc is not None and not et.reemissao_pedida(s, proc):
        # O processo desta empresa (mesmos parâmetros) já existe ou ficou incerto: o robô não gera outro.
        if proc["status"] == "emitindo":
            msg = ("o robô clicou em 'Gerar processo' para esta empresa e não confirmou o número. Confira em "
                   "'Acompanhar processos' no portal; o robô não gera outro processo sozinho")
        else:
            msg = (f"o processo {proc.get('protocolo')} desta empresa já existe (válido por 40 dias) e falta(m) "
                   "cálculo(s). O robô ainda não reabre um processo: faça o cálculo no portal ('Acompanhar "
                   "processos' -> Alterar Cotação) ou, para um processo novo, libere o registro do processo")
        for alvo in pendentes or [PlanoAlvo("menor preço", "")]:
            s.resultados.plano(et._resultado(a, alvo, status="VERIFICAR", protocolo=proc.get("protocolo", ""), erro=msg))
        s.log.warning(f"[{pedido.id}] {msg}.")
        return None
    return a


def processar_pedido(s: Sessao, pedido) -> None:
    a = preparar(s, pedido)
    if a is None:
        s.log.info(f"[{pedido.id}] nada a fazer.")
        return
    s.log.info(f"===== Pedido {pedido.id} (linha {pedido.linha}) | CNPJ {pedido.cnpj} | {pedido.total_vidas} vidas | "
               f"planos: {[x.rotulo_completo() for x in a.alvos] or f'menor_preco:{pedido.criterio_quantidade}'} =====")
    etapa = "inicio"
    try:
        _percorrer(s, a)
    except Parado as e:
        inicio = a.indice
        if a.alvo is not None and a.aguardando:
            _registrar_falha(s, a, e.etapa, ErroFluxo("o corretor pediu para parar durante o cálculo", e.etapa))
            inicio += 1
        s.log.warning(f"[{pedido.id}] parado a pedido do corretor (tela {e.etapa}).")
        for resto in a.alvos[inicio:]:
            s.resultados.plano(et._resultado(a, resto, status="PARADO", etapa_erro=e.etapa,
                                             erro="parado a pedido do corretor antes de gerar o cálculo"))
        raise
    except Exception as e:  # noqa: BLE001
        etapa = getattr(e, "etapa", "") or etapa
        _registrar_falha(s, a, etapa, e)
        resto_msg = (f"não processado: o pedido parou na etapa {etapa}; o processo {a.processo} já existe, então o "
                     "robô não gera outro (faça no portal ou peça de novo depois de conferir)" if a.processo else
                     f"não processado: o pedido parou na etapa {etapa}; rode de novo")
        for resto in a.alvos[a.indice + 1:]:
            s.resultados.plano(et._resultado(a, resto, status="VERIFICAR" if a.processo else "ERRO",
                                             etapa_erro=etapa, erro=resto_msg, protocolo=a.processo or ""))
        if isinstance(e, ErroLogin):
            raise


def _percorrer(s: Sessao, a: Andamento) -> None:
    recomecos = 0
    while not a.terminou and (a.alvo is not None or (a.resolver_por_criterio and not a.alvos)):
        if a.processo is None:
            try:
                et.ir_ao_cotador(s, a)
                et.produto(s, a)
                et.empresa(s, a)
                et.grupos(s, a)
                et.regiao(s, a)
                et.personalizar(s, a)
                et.configuracao(s, a)
                et.resultado(s, a)
                if a.terminou:
                    return
                if a.card is None:          # o próximo plano é de outra acomodação ou versão: recomeça com ela
                    recomecos += 1
                    if recomecos > len(a.alvos) + 1:
                        raise ErroFluxo("o pedido recomeçou vezes demais pelo cotador; parei", "resultado")
                    continue
                et.complementares(s, a)
            except SessaoCaiu:
                if a.aguardando:
                    raise
                recomecos += 1
                if recomecos > 2:
                    raise
                s.log.warning("A sessão do portal acabou antes de gerar o processo; entrando de novo e recomeçando "
                              "o pedido (nada oficial tinha sido gerado).")
                entrar(s, pode_parar=True)
                continue
            et.calculo(s, a, primeiro=True)
        else:
            et.alterar(s, a)
            et.calculo(s, a, primeiro=False)


def _registrar_falha(s: Sessao, a: Andamento, etapa: str, erro: Exception) -> None:
    try:                                   # nunca um mapa da tela de login depois de digitar (_mapa confere)
        et._mapa(s, f"ERRO_{etapa}", forcar=True)
    except Exception:  # noqa: BLE001
        pass
    msg = ocultar((str(erro).splitlines() or [type(erro).__name__])[0][:400])
    status = "ERRO"
    if a.alvo is None:
        s.log.error(f"[{a.base.id}] falha na etapa {etapa}: {msg}")
        return
    if not s.ensaio:
        item = s.estado.item(et.chave_calculo(s, a)) or {}
        proc = s.estado.item(et.chave_processo(s, a.base)) or {}
        if item.get("status") == "emitindo" or proc.get("status") == "emitindo":
            status = "VERIFICAR"
            numero = proc.get("protocolo") or item.get("protocolo")
            if numero:
                msg = (f"{msg} | ATENÇÃO: o portal gerou o processo {numero}, mas o robô não conseguiu ler o cálculo "
                       "nem salvar o PDF. Imprima à mão no portal ('Acompanhar processos' -> processo "
                       f"{numero}) e marque como resolvido na tela; o robô não gera de novo sozinho.")
            else:
                msg = (f"{msg} | ATENÇÃO: o robô clicou no botão que gera o "
                       + ("processo" if proc.get("status") == "emitindo" else "cálculo")
                       + " e não confirmou. Confira em 'Acompanhar processos' no portal; o robô não gera de novo "
                         "sozinho.")
        elif item.get("status") == "emitida":
            status = "VERIFICAR"
            msg = (f"{msg} | O cálculo saiu no processo {item.get('protocolo')}, mas o PDF não foi salvo: imprima à mão "
                   "pelo processo no portal e marque como resolvido na tela.")
    tipo = "dado do pedido" if isinstance(erro, ErroDados) else "tela"
    s.log.error(f"[{a.base.id}] falha na etapa {etapa} ({tipo}): {msg}")
    r = a.resultado or et._resultado(a)
    r.status, r.erro, r.etapa_erro = status, msg, etapa
    r.protocolo = r.protocolo or a.processo or ""
    s.resultados.plano(r)
