"""Revalidação de alertas por linha após edição manual."""

from __future__ import annotations

from datetime import date

from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
)
from newport_app.models.siscor_import import (
    IMPORTADOR_SISCOR_VERSAO,
    AlertaLinhaSiscor,
    LinhaSiscorCandidata,
)
from newport_app.siscor_importer.money import valor_para_centavos
from newport_app.siscor_importer.normalize import (
    normalizar_parentesco,
    normalizar_status,
    parse_data_nascimento,
)


def _alerta(codigo: str, caminho: str, mensagem: str) -> AlertaLinhaSiscor:
    return AlertaLinhaSiscor(codigo=codigo, caminho=caminho, mensagem=mensagem)


def revalidar_linha(linha: LinhaSiscorCandidata, *, documento_id: str | None = None) -> None:
    caminho = f"/linhas/{linha.id}"
    alertas: list[AlertaLinhaSiscor] = []

    if not linha.segurado:
        alertas.append(
            _alerta("APP-SIS-007", f"{caminho}/segurado", "Nome do beneficiário ausente.")
        )

    if not linha.parentesco_texto:
        alertas.append(
            _alerta(
                "APP-SIS-008",
                f"{caminho}/parentesco",
                "Parentesco ausente — informe antes de confirmar.",
            )
        )
    else:
        texto, parentesco = normalizar_parentesco(linha.parentesco_texto)
        linha.parentesco_texto = texto
        linha.parentesco = parentesco
        if parentesco is None:
            alertas.append(
                _alerta(
                    "APP-SIS-008",
                    f"{caminho}/parentesco",
                    "Parentesco não reconhecido — revise.",
                )
            )

    if not linha.nascimento:
        alertas.append(
            _alerta(
                "APP-SIS-001",
                f"{caminho}/nascimento",
                "Data de nascimento ausente.",
            )
        )
    else:
        nasc_texto, nasc, invalida = parse_data_nascimento(linha.nascimento)
        if invalida:
            alertas.append(
                _alerta("APP-SIS-001", f"{caminho}/nascimento", "Data de nascimento inválida.")
            )
        else:
            linha.nascimento = nasc_texto
            if nasc and nasc > date.today():
                alertas.append(
                    _alerta(
                        "APP-SIS-002",
                        f"{caminho}/nascimento",
                        "Data de nascimento no futuro.",
                    )
                )

    if not linha.plano:
        alertas.append(
            _alerta("APP-SIS-004", f"{caminho}/plano", "Plano ausente na linha importada.")
        )

    if not linha.operadora:
        alertas.append(
            _alerta(
                "APP-SIS-010",
                f"{caminho}/operadora",
                "Operadora ausente na linha importada.",
            )
        )

    if linha.valor_centavos is None:
        alertas.append(
            _alerta("APP-SIS-009", f"{caminho}/valor", "Valor mensal ausente — informe.")
        )
    elif linha.valor_centavos < 0:
        alertas.append(
            _alerta("APP-SIS-012", f"{caminho}/valor", "Valor mensal negativo — revise.")
        )
    elif linha.valor_centavos == 0:
        alertas.append(
            _alerta("APP-SIS-003", f"{caminho}/valor", "Valor mensal zerado — revise.")
        )

    if not linha.status_texto:
        alertas.append(
            _alerta(
                "APP-SIS-005",
                f"{caminho}/status",
                "Status do beneficiário ausente — revise.",
            )
        )
    else:
        status_texto, status_norm = normalizar_status(linha.status_texto)
        linha.status_texto = status_texto
        linha.status_normalizado = status_norm
        if status_norm is None:
            alertas.append(
                _alerta(
                    "APP-SIS-005",
                    f"{caminho}/status",
                    "Status do beneficiário não reconhecido — revise.",
                )
            )
        else:
            linha.incluida_sugerida = status_norm == "ATIVO"

    if linha.valor_centavos is not None and linha.valor_centavos > 0:
        if linha.valor_fatura is None:
            doc = documento_id or (
                linha.valor_fatura.proveniencia.documento_id
                if linha.valor_fatura
                else None
            )
            linha.valor_fatura = ComponenteFinanceiroRascunho(
                centavos=linha.valor_centavos,
                price_basis=PriceBasisRascunho.DESCONHECIDO,
                proveniencia=ProvenienciaRascunho(
                    origem=OrigemValorRascunho.MANUAL,
                    documento_id=doc,
                    extrator_versao=IMPORTADOR_SISCOR_VERSAO,
                    confirmado=False,
                ),
            )
        else:
            linha.valor_fatura = linha.valor_fatura.model_copy(
                update={"centavos": linha.valor_centavos}
            )

    linha.alertas = alertas
