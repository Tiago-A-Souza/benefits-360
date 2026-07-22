"""Textos de apresentação para a camada de aplicação (sem alterar o motor)."""

from __future__ import annotations

_FORMATOS: dict[str, str] = {
    "renovacao": "renovação",
    "novo": "novo",
}


def formatar_tipo_estudo(formato: str) -> str:
    return _FORMATOS.get(formato, formato)


def plural_beneficiarios(quantidade: int) -> str:
    if quantidade == 1:
        return "1 beneficiário"
    return f"{quantidade} beneficiários"


def descricao_estudo(formato: str, quantidade_incluidos: int) -> str:
    tipo = formatar_tipo_estudo(formato)
    return f"Estudo de {tipo} com {plural_beneficiarios(quantidade_incluidos)} — dados fictícios."


def mensagem_faixa_homologada(n_vidas: int, max_homologadas: int) -> str:
    return (
        f"Este estudo possui {n_vidas} vidas. "
        f"A faixa operacional homologada atualmente é de até {max_homologadas} vidas. "
        "O comparativo pode ser calculado, mas exige revisão adicional antes de qualquer aprovação."
    )


def rotulos_diferenca(
    diff_mensal_centavos: int,
    diff_anual_centavos: int,
) -> tuple[str, str, str]:
    """Retorna (semantica, rotulo_mensal, rotulo_anual)."""
    if diff_mensal_centavos == 0:
        return ("empate", "Sem diferença mensal", "Sem diferença anual")
    if diff_mensal_centavos > 0:
        return ("aumento", "Aumento mensal", "Aumento anual")
    return ("economia", "Economia mensal", "Economia anual")
