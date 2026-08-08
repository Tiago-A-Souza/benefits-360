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
    "indices_quebra_monotonicidade",
    "alertas_monotonicidade_opcao",
]


def indices_quebra_monotonicidade(valores: list[int | None]) -> list[int]:
    """Índices onde o prêmio é menor que o da faixa etária anterior (ANS: não decresce)."""
    quebras: list[int] = []
    anterior: int | None = None
    for i, v in enumerate(valores):
        if v is None:
            continue
        if anterior is not None and v < anterior:
            quebras.append(i)
        anterior = v
    return quebras


def _fmt_br(centavos: int | None) -> str:
    if centavos is None:
        return "—"
    reais, cents = divmod(abs(centavos), 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"R$ {inteiro},{cents:02d}"


def alertas_monotonicidade_opcao(
    opcao: OpcaoCotacaoCandidata,
    *,
    codigo: str = "PDF-TARIFA-001",
) -> list[AlertaExtracaoCotacao]:
    """Emite alerta se a tabela violar crescimento monotônico por faixa."""
    valores = [fx.valor.centavos for fx in opcao.tabela]
    alertas: list[AlertaExtracaoCotacao] = []
    for idx in indices_quebra_monotonicidade(valores):
        fx = opcao.tabela[idx]
        if fx.valor:
            fx.valor.estado = "revisar"
        prev = valores[idx - 1] if idx > 0 else None
        atual = valores[idx]
        nome = opcao.plano_nome.texto if opcao.plano_nome else "plano"
        alertas.append(
            AlertaExtracaoCotacao(
                codigo=codigo,
                mensagem=(
                    f"«{nome}»: valor da faixa {idx} ({_fmt_br(atual)}) "
                    f"é menor que a faixa {idx - 1} ({_fmt_br(prev)}) — "
                    "tabela ANS não deveria decrescer. Confira se o milhar foi truncado."
                ),
                severidade="alerta",
                pagina=fx.valor.evidencia.pagina if fx.valor and fx.valor.evidencia else None,
            )
        )
    return alertas


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
