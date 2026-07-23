"""Validação estrutural de linhas tarifárias extraídas de PDF."""

from __future__ import annotations

from newport_app.cotacao_pdf.sulamerica_table import (
    detectar_sequencia_suspeita,
    validar_linha_tarifaria,
)
from newport_app.models.cotacao_pdf import AlertaExtracaoCotacao, OpcaoCotacaoCandidata

__all__ = [
    "detectar_sequencia_suspeita",
    "validar_linha_tarifaria",
    "aplicar_validacao_estrutural_opcao",
]


def aplicar_validacao_estrutural_opcao(
    opcao: OpcaoCotacaoCandidata,
    *,
    motivos_extra: list[str] | None = None,
) -> list[AlertaExtracaoCotacao]:
    """Marca campos suspeitos e retorna alertas operacionais."""
    alertas: list[AlertaExtracaoCotacao] = []
    valores = [fx.valor.centavos for fx in opcao.tabela if fx.valor.centavos is not None]
    nome = opcao.plano_nome.texto if opcao.plano_nome else ""
    ok, motivos = validar_linha_tarifaria(nome, valores, flags_extra=motivos_extra or [])

    if opcao.plano_nome:
        if "nome_generico" in motivos or "nome_possivelmente_fragmentado" in motivos:
            opcao.plano_nome.estado = "revisar"
        elif ok:
            opcao.plano_nome.estado = "confirmar"

    suspeitas = detectar_sequencia_suspeita(valores)
    for idx in suspeitas:
        if idx < len(opcao.tabela):
            fx = opcao.tabela[idx]
            fx.valor.estado = "revisar"
            alertas.append(
                AlertaExtracaoCotacao(
                    codigo="PDF-SUL-004",
                    mensagem=(
                        f"Valor da faixa {idx} possivelmente fragmentado ou inconsistente — "
                        "confira a célula no PDF antes de confirmar."
                    ),
                    severidade="alerta",
                    pagina=fx.valor.evidencia.pagina,
                )
            )

    if len(valores) != 10:
        alertas.append(
            AlertaExtracaoCotacao(
                codigo="PDF-SUL-005",
                mensagem="A opção não possui exatamente 10 faixas tarifárias.",
                severidade="alerta",
            )
        )

    if not ok:
        for m in motivos:
            if m.startswith("faixa_"):
                continue
            if m == "nome_generico":
                alertas.append(
                    AlertaExtracaoCotacao(
                        codigo="PDF-SUL-006",
                        mensagem="Nome do plano possivelmente fragmentado ou genérico.",
                        severidade="alerta",
                    )
                )

    return alertas
