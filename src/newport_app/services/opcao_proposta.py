"""Exclusão de cotação manual do rascunho — governança no backend."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.services.comparativo_ui import sanitizar_selecao_apresentacao


class OpcaoPropostaNaoEncontradaError(Exception):
    pass


class OpcaoPropostaDeExtracaoError(Exception):
    """Cotação vinda de PDF não se exclui por este caminho."""


def excluir_opcao_proposta_manual(rascunho: RascunhoEstudo, opcao_id: str) -> None:
    """Remove uma cotação manual e as referências que a atestariam.

    Invalida `confirmacao_comparativo` e limpa `selecao_apresentacao` e
    atribuições de cenário. A confirmação da etapa 5 não pode sobreviver a
    uma opção que deixou de existir — na fase 2 o snapshot nasce dela.
    """
    opcao = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    if opcao is None:
        raise OpcaoPropostaNaoEncontradaError(opcao_id)
    if opcao.extracao_id:
        raise OpcaoPropostaDeExtracaoError(opcao_id)

    rascunho.opcoes_proposta = [o for o in rascunho.opcoes_proposta if o.id != opcao_id]
    for cenario in rascunho.cenarios:
        cenario.atribuicoes = [
            a for a in cenario.atribuicoes if a.opcao_plano_id != opcao_id
        ]
    rascunho.cenarios = [c for c in rascunho.cenarios if c.atribuicoes]
    sanitizar_selecao_apresentacao(rascunho)
    rascunho.confirmacao_comparativo = None
