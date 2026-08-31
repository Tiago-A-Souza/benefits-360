"""Normalização e alertas de acomodação (enfermaria × apartamento)."""

from __future__ import annotations

import re

from newport_app.models.draft import OpcaoPropostaRascunho, RascunhoEstudo, SubgrupoAtualRascunho
from newport_app.models.responses import PendenciaItem


def normalizar_acomodacao(texto: str | None) -> str | None:
    if not texto or not str(texto).strip():
        return None
    t = str(texto).strip().lower()
    if t in {"enfermaria", "qc", "e", "coletivo", "quarto coletivo"}:
        return "enfermaria"
    if t in {"apartamento", "qp", "q", "privativo", "quarto privativo"}:
        return "apartamento"
    if "enfermaria" in t or re.search(r"\bqc\b", t):
        return "enfermaria"
    if "apartamento" in t or re.search(r"\bqp\b", t):
        return "apartamento"
    return None


def rotulo_acomodacao(canonico: str | None) -> str:
    if canonico == "enfermaria":
        return "Enfermaria"
    if canonico == "apartamento":
        return "Apartamento"
    return "—"


def acomodacao_de_texto(*textos: str | None) -> str | None:
    for texto in textos:
        n = normalizar_acomodacao(texto)
        if n:
            return n
    return None


def acomodacao_subgrupo(sg: SubgrupoAtualRascunho) -> str | None:
    return acomodacao_de_texto(sg.acomodacao, sg.plano_nome)


def acomodacao_opcao(op: OpcaoPropostaRascunho) -> str | None:
    return acomodacao_de_texto(op.acomodacao, op.plano_nome)


def acomodacao_informada_subgrupo(sg: SubgrupoAtualRascunho) -> str | None:
    """Acomodação declarada explicitamente — sem dedução do nome do plano."""

    return normalizar_acomodacao(sg.acomodacao)


def acomodacao_informada_opcao(op: OpcaoPropostaRascunho) -> str | None:
    """Acomodação declarada explicitamente — sem dedução do nome do plano."""

    return normalizar_acomodacao(op.acomodacao)


def mensagem_divergencia_acomodacao(
    *,
    plano_atual: str,
    acomod_atual: str,
    plano_proposta: str,
    acomod_proposta: str,
) -> str:
    return (
        f"«{plano_atual}» é {rotulo_acomodacao(acomod_atual)}; "
        f"a proposta atribuída «{plano_proposta}» é {rotulo_acomodacao(acomod_proposta)}. "
        f"A comparação de preço não é equivalente."
    )


def mensagem_incompleto_acomodacao(
    *,
    plano_atual: str,
    plano_proposta: str,
    falta_atual: bool,
    falta_proposta: bool,
) -> str:
    if falta_atual and falta_proposta:
        return (
            f"Comparação de acomodação não realizada entre «{plano_atual}» e "
            f"«{plano_proposta}»: nenhum dos lados informado. "
            f"Preencha na etapa «Plano atual» e na conferência do PDF."
        )
    if falta_atual:
        return (
            f"Comparação de acomodação não realizada para «{plano_atual}»: "
            f"acomodação do plano vigente não informada. "
            f"Preencha na etapa «Plano atual»."
        )
    return (
        f"Comparação de acomodação não realizada para «{plano_proposta}»: "
        f"acomodação da proposta não informada. "
        f"Preencha na conferência do PDF."
    )


def _iterar_pares_atribuidos(rascunho: RascunhoEstudo):
    if rascunho.formato == "novo":
        return
    subgrupos = {sg.id: sg for sg in rascunho.subgrupos_atuais}
    opcoes = {op.id: op for op in rascunho.opcoes_proposta}
    for cenario in rascunho.cenarios:
        for atr in cenario.atribuicoes:
            if atr.alvo_tipo != "subgrupo":
                continue
            sg = subgrupos.get(atr.alvo_id)
            op = opcoes.get(atr.opcao_plano_id)
            if sg is None or op is None:
                continue
            yield sg, op


def coletar_divergencias_acomodacao(rascunho: RascunhoEstudo) -> list[str]:
    """Mensagens únicas de divergência nas atribuições atuais."""
    mensagens: list[str] = []
    vistos: set[str] = set()
    for sg, op in _iterar_pares_atribuidos(rascunho):
        ac_sg = acomodacao_informada_subgrupo(sg)
        ac_op = acomodacao_informada_opcao(op)
        if not ac_sg or not ac_op or ac_sg == ac_op:
            continue
        msg = mensagem_divergencia_acomodacao(
            plano_atual=sg.plano_nome,
            acomod_atual=ac_sg,
            plano_proposta=op.plano_nome,
            acomod_proposta=ac_op,
        )
        if msg not in vistos:
            vistos.add(msg)
            mensagens.append(msg)
    return mensagens


def coletar_incompletos_acomodacao(rascunho: RascunhoEstudo) -> list[str]:
    """Mensagens informativas quando a comparação não pôde ser feita."""
    mensagens: list[str] = []
    vistos: set[str] = set()
    for sg, op in _iterar_pares_atribuidos(rascunho):
        ac_sg = acomodacao_informada_subgrupo(sg)
        ac_op = acomodacao_informada_opcao(op)
        if ac_sg and ac_op:
            continue
        msg = mensagem_incompleto_acomodacao(
            plano_atual=sg.plano_nome,
            plano_proposta=op.plano_nome,
            falta_atual=not ac_sg,
            falta_proposta=not ac_op,
        )
        if msg not in vistos:
            vistos.add(msg)
            mensagens.append(msg)
    return mensagens


def pendencias_divergencia_acomodacao(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    msgs = coletar_divergencias_acomodacao(rascunho)
    if not msgs:
        return []
    return [
        PendenciaItem(
            tipo="alerta",
            titulo="Acomodação divergente entre plano atual e proposta",
            descricao=msg,
            acao_sugerida=(
                "Revise a matriz de atribuição: upgrade/rebaixamento pode ser "
                "intencional, mas a comparação de preço não é equivalente."
            ),
            codigo="APP-ACO-001",
            etapa=4 if len(rascunho.subgrupos_atuais) > 1 else 3,
            quantidade=1,
        )
        for msg in msgs
    ]


def pendencias_incompleto_acomodacao(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    msgs = coletar_incompletos_acomodacao(rascunho)
    if not msgs:
        return []
    return [
        PendenciaItem(
            tipo="info",
            titulo="Acomodação incompleta — comparação não realizada",
            descricao=msg,
            acao_sugerida=(
                "Informe a acomodação na etapa «Plano atual» (vigente) e na "
                "conferência do PDF (proposta), quando o documento não trouxer o dado."
            ),
            codigo="APP-ACO-002",
            etapa=4 if len(rascunho.subgrupos_atuais) > 1 else 3,
            quantidade=1,
        )
        for msg in msgs
    ]


def chave_plano_equivalente(op: OpcaoPropostaRascunho) -> tuple[str, str]:
    return (
        (op.operadora or "").strip().upper(),
        (op.plano_nome or "").strip().upper(),
    )


def tabela_por_faixa(op: OpcaoPropostaRascunho) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((fx.faixa, fx.valor_centavos) for fx in op.tabela))
