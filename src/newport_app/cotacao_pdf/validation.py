"""Validação operacional antes de aplicar extrações ao rascunho (ETAPA 2.5.6)."""

from __future__ import annotations

from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata, ValorExtraido

_CAMPOS_OBRIGATORIOS = (
    "operadora",
    "plano_nome",
    "tipo_fiscal",
    "regime_copart",
)

_CAMPOS_FINANCEIROS = (
    "premio_saude",
    "iof",
    "total_recorrente",
    "total_primeira_parcela",
    "subtotal_impresso",
)


def _campo_pendente(campo: ValorExtraido | None, *, obrigatorio: bool) -> str | None:
    if campo is None:
        return "informe e confirme" if obrigatorio else None
    if campo.confirmado:
        if obrigatorio and not any(
            v is not None for v in (campo.texto, campo.centavos, campo.data, campo.inteiro)
        ):
            return "informe e confirme"
        return None
    if campo.estado == "ausente":
        return "informe e confirme" if obrigatorio else None
    return "confirme após revisar"


def pendencias_opcao(op: OpcaoCotacaoCandidata) -> list[str]:
    if op.excluida:
        return []

    msgs: list[str] = []
    for nome in _CAMPOS_OBRIGATORIOS:
        campo = getattr(op, nome, None)
        pend = _campo_pendente(campo, obrigatorio=True)
        if pend:
            rotulo = campo.rotulo if campo else nome.replace("_", " ")
            msgs.append(f"{rotulo}: {pend}.")

    for nome in ("acomodacao", "modalidade", "copart_percentual", "validade_oficial", "observacoes"):
        campo = getattr(op, nome, None)
        pend = _campo_pendente(campo, obrigatorio=False)
        if pend:
            msgs.append(f"{campo.rotulo}: {pend}.")

    for nome in _CAMPOS_FINANCEIROS:
        campo = getattr(op, nome, None)
        pend = _campo_pendente(campo, obrigatorio=False)
        if pend:
            msgs.append(f"{campo.rotulo}: {pend}.")

    for custo in op.custos_unicos:
        pend = _campo_pendente(custo, obrigatorio=False)
        if pend:
            msgs.append(f"{custo.rotulo}: {pend}.")

    faixas_confirmadas = 0
    for fx in op.tabela:
        if fx.valor.estado != "ausente" and not fx.valor.confirmado:
            msgs.append(f"{fx.valor.rotulo}: confirme após revisar.")
        if fx.quantidade.estado != "ausente" and not fx.quantidade.confirmado:
            msgs.append(f"{fx.quantidade.rotulo}: confirme após revisar.")
        if fx.valor.confirmado and fx.valor.centavos is not None:
            faixas_confirmadas += 1

    if faixas_confirmadas == 0:
        msgs.append("Confirme ao menos uma faixa etária com valor.")

    if op.reconciliacao is not None and op.reconciliacao.status == "divergente":
        msgs.append("Divergência financeira não resolvida — ajuste valores ou quantidades.")

    return msgs
