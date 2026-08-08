"""Regras de valor de fatura SISCOR conforme o formato do estudo."""

from __future__ import annotations

from typing import Literal

from newport_app.models.siscor_import import AlertaLinhaSiscor

FormatoEstudoSiscor = Literal["renovacao", "novo"] | None


def _alerta(
    codigo: str,
    caminho: str,
    mensagem: str,
    *,
    severidade: str = "alerta",
) -> AlertaLinhaSiscor:
    return AlertaLinhaSiscor(
        codigo=codigo,
        caminho=caminho,
        mensagem=mensagem,
        severidade=severidade,
    )


def alertas_valor_mensal(
    *,
    caminho: str,
    valor_centavos: int | None,
    valor_ausente: bool,
    valor_ilegivel: bool,
    valor_negativo: bool,
    formato: FormatoEstudoSiscor,
) -> list[AlertaLinhaSiscor]:
    """
    Renovação: fatura obrigatória (comportamento histórico).
    Seguro novo: ausência/zero é estado normal — sem exceção.
    Formato ainda não definido: aviso informativo, não bloqueante.
    """
    if valor_negativo:
        return [
            _alerta(
                "APP-SIS-012",
                f"{caminho}/valor",
                "Valor mensal negativo — revise.",
            )
        ]
    if valor_ilegivel:
        return [
            _alerta(
                "APP-SIS-009",
                f"{caminho}/valor",
                "Valor mensal ilegível — revise.",
            )
        ]

    faltando = valor_ausente or valor_centavos is None
    zerado = valor_centavos == 0

    if formato == "novo":
        return []

    if formato == "renovacao":
        if faltando:
            return [
                _alerta(
                    "APP-SIS-009",
                    f"{caminho}/valor",
                    "Valor mensal ausente — informe.",
                )
            ]
        if zerado:
            return [
                _alerta(
                    "APP-SIS-003",
                    f"{caminho}/valor",
                    "Valor mensal zerado — revise.",
                )
            ]
        return []

    # Formato ainda não definido: não bloqueia a confirmação.
    if faltando:
        return [
            _alerta(
                "APP-SIS-009",
                f"{caminho}/valor",
                "Valor mensal ausente — em renovação será obrigatório; em seguro novo é esperado.",
                severidade="info",
            )
        ]
    if zerado:
        return [
            _alerta(
                "APP-SIS-003",
                f"{caminho}/valor",
                "Valor mensal zerado — em renovação será exceção; em seguro novo é esperado.",
                severidade="info",
            )
        ]
    return []
