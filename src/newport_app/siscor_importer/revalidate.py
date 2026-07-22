"""Revalidação de alertas por linha após edição manual."""

from __future__ import annotations

from datetime import date

from newport_app.models.siscor_import import AlertaLinhaSiscor, LinhaSiscorCandidata
from newport_app.siscor_importer.normalize import normalizar_parentesco, parse_data_nascimento


def _alerta(codigo: str, caminho: str, mensagem: str) -> AlertaLinhaSiscor:
    return AlertaLinhaSiscor(codigo=codigo, caminho=caminho, mensagem=mensagem)


def revalidar_linha(linha: LinhaSiscorCandidata) -> None:
    caminho = f"/linhas/{linha.id}"
    alertas: list[AlertaLinhaSiscor] = []

    if not linha.segurado:
        alertas.append(
            _alerta("APP-SIS-007", f"{caminho}/segurado", "Nome do beneficiário ausente.")
        )

    if linha.parentesco_texto and linha.parentesco is None:
        _, parentesco = normalizar_parentesco(linha.parentesco_texto)
        linha.parentesco = parentesco
        if parentesco is None:
            alertas.append(
                _alerta(
                    "APP-SIS-008",
                    f"{caminho}/parentesco",
                    "Parentesco não reconhecido — revise.",
                )
            )

    if linha.nascimento:
        _, nasc, invalida = parse_data_nascimento(linha.nascimento)
        if invalida:
            alertas.append(
                _alerta("APP-SIS-001", f"{caminho}/nascimento", "Data de nascimento inválida.")
            )
        elif nasc and nasc > date.today():
            alertas.append(
                _alerta("APP-SIS-002", f"{caminho}/nascimento", "Data de nascimento no futuro.")
            )

    if not linha.plano:
        alertas.append(
            _alerta("APP-SIS-004", f"{caminho}/plano", "Plano ausente na linha importada.")
        )

    if linha.valor_centavos == 0:
        alertas.append(
            _alerta("APP-SIS-003", f"{caminho}/valor", "Valor mensal zerado — revise.")
        )
    elif linha.valor_centavos is None and linha.valor_fatura is not None:
        alertas.append(
            _alerta("APP-SIS-009", f"{caminho}/valor", "Valor mensal ilegível — revise.")
        )

    if linha.status_texto and linha.status_normalizado is None:
        alertas.append(
            _alerta(
                "APP-SIS-005",
                f"{caminho}/status",
                "Status do beneficiário não reconhecido — revise.",
            )
        )

    linha.alertas = alertas
