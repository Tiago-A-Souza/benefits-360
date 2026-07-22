"""Tradução de pendências de compilação para a interface."""

from __future__ import annotations

from newport_app.draft_compiler import compile
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import PendenciaItem
from newport_app.policy.registry import default_registry

_TRADUCOES: dict[str, tuple[str, str, str]] = {
    "APP-IMP-001": (
        "bloqueio",
        "Tipo fiscal do plano atual",
        "Informe se o plano atual é contrato da seguradora ou da operadora.",
    ),
    "APP-IMP-002": (
        "bloqueio",
        "Regime de coparticipação do plano atual",
        "Selecione o regime de coparticipação de cada plano importado.",
    ),
    "APP-ESC-001": (
        "bloqueio",
        "Data de referência para idades",
        "Informe a data usada para calcular as idades dos beneficiários.",
    ),
    "APP-ESC-002": (
        "bloqueio",
        "Comparação do plano atual",
        "Confirme se a comparação usa o contrato vigente ou o reajustado.",
    ),
    "APP-ESC-003": (
        "bloqueio",
        "Fonte do valor atual",
        "Confirme se prevalece a tabela do plano ou o valor de fatura por vida.",
    ),
    "APP-FIN-001": (
        "bloqueio",
        "Base de IOF pendente",
        "Informe se cada valor inclui IOF, exclui IOF ou não se aplica.",
    ),
    "APP-FIN-002": (
        "bloqueio",
        "Confirmação de valor pendente",
        "Confirme explicitamente os valores informados manualmente.",
    ),
    "APP-FIN-003": (
        "bloqueio",
        "Valor financeiro incompleto",
        "Há campos monetários sem valor informado.",
    ),
    "APP-QTD-001": (
        "bloqueio",
        "Quantidade cotada na proposta",
        "Informe a quantidade cotada de cada faixa ou confirme zero.",
    ),
}


def pendencias_compilacao(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    resultado = compile(rascunho, policy_registry=default_registry)
    itens: list[PendenciaItem] = []
    vistos: set[str] = set()
    for erro in resultado.erros:
        chave = f"{erro.codigo}:{erro.caminho}"
        if chave in vistos:
            continue
        vistos.add(chave)
        if erro.codigo in _TRADUCOES:
            tipo, titulo, descricao = _TRADUCOES[erro.codigo]
            itens.append(
                PendenciaItem(
                    tipo=tipo,
                    titulo=titulo,
                    descricao=descricao,
                    acao_sugerida="Complete a etapa correspondente no fluxo guiado.",
                )
            )
        else:
            itens.append(
                PendenciaItem(
                    tipo="bloqueio",
                    titulo="Informação pendente no estudo",
                    descricao=erro.mensagem,
                    acao_sugerida="Revise os dados nas etapas anteriores.",
                )
            )
    if not rascunho.opcoes_proposta:
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Nenhuma proposta cadastrada",
                descricao="Cadastre ao menos uma opção de plano na proposta.",
                acao_sugerida="Use a etapa Propostas para incluir a cotação.",
            )
        )
    if rascunho.opcoes_proposta and not rascunho.cenarios:
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Associação de planos pendente",
                descricao="Associe cada plano atual à proposta correspondente.",
                acao_sugerida="Use a etapa Associação dos planos.",
            )
        )
    return itens
