"""Validação operacional antes de aplicar extrações ao rascunho (ETAPA 2.5.6)."""

from __future__ import annotations

from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata, ValorExtraido


_CAMPOS_OBRIGATORIOS = (
    "operadora",
    "plano_nome",
    "tipo_fiscal",
    "regime_copart",
)

_MENSAGENS_AUSENCIA = {
    "tipo_fiscal": (
        "Tipo fiscal: declare se é Operadora (Amil, Hapvida, Unimed, NotreDame) "
        "ou Seguradora (Porto, SulAmérica, Bradesco) — o IOF depende dessa escolha."
    ),
    "regime_copart": (
        "Regime de coparticipação: declare o regime — não é preenchido automaticamente."
    ),
}


def _tem_valor(campo: ValorExtraido | None) -> bool:
    if campo is None:
        return False
    return any(v is not None for v in (campo.texto, campo.centavos, campo.data, campo.inteiro))


def pendencias_opcao(op: OpcaoCotacaoCandidata) -> list[str]:
    """Pendências reais — seleção do plano aceita valores extraídos sem confirmação campo a campo."""
    if op.excluida:
        return []

    msgs: list[str] = []
    for nome in _CAMPOS_OBRIGATORIOS:
        campo = getattr(op, nome, None)
        rotulo = campo.rotulo if campo else nome.replace("_", " ")
        if not _tem_valor(campo):
            msgs.append(_MENSAGENS_AUSENCIA.get(nome, f"{rotulo}: valor ausente."))

    faixas_com_valor = sum(1 for fx in op.tabela if fx.valor.centavos is not None)
    if faixas_com_valor == 0:
        msgs.append("Nenhuma faixa etária com valor — corrija a tabela ou escolha outro plano.")

    if op.reconciliacao is not None and op.reconciliacao.status == "divergente":
        msgs.append("Divergência financeira — ajuste valores na revisão.")

    return msgs
