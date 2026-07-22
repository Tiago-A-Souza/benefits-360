"""Validação de valores financeiros utilizados na compilação."""

from __future__ import annotations

from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    TabelaFaixaRascunho,
)


def _erro(codigo: str, caminho: str, mensagem: str) -> ErroCompilacao:
    return ErroCompilacao(
        codigo=codigo,
        caminho=caminho,
        mensagem=mensagem,
        severidade="bloqueante",
    )


def validar_price_basis_usavel(
    basis: PriceBasisRascunho,
    tipo_fiscal: str,
    caminho: str,
    erros: list[ErroCompilacao],
) -> bool:
    if basis == PriceBasisRascunho.DESCONHECIDO:
        erros.append(
            _erro(
                "APP-FIN-001",
                caminho,
                "Informe se o valor inclui IOF, exclui IOF ou não se aplica.",
            )
        )
        return False
    if basis == PriceBasisRascunho.NAO_APLICA and tipo_fiscal != "operadora":
        erros.append(
            _erro(
                "APP-BAS-001",
                caminho,
                "A opção 'não se aplica' só é permitida para operadoras sem IOF.",
            )
        )
        return False
    return True


def validar_proveniencia_confirmada(
    prov: ProvenienciaRascunho,
    caminho: str,
    erros: list[ErroCompilacao],
) -> bool:
    if not prov.confirmado:
        erros.append(
            _erro(
                "APP-FIN-002",
                caminho,
                "Confirme a origem deste valor financeiro antes de calcular.",
            )
        )
        return False
    return True


def validar_componente_financeiro(
    comp: ComponenteFinanceiroRascunho,
    tipo_fiscal: str,
    caminho_base: str,
    erros: list[ErroCompilacao],
) -> bool:
    ok = True
    if comp.centavos is None:
        erros.append(
            _erro(
                "APP-FIN-003",
                f"{caminho_base}/centavos",
                "Informe o valor em centavos antes de calcular.",
            )
        )
        ok = False
    if not validar_price_basis_usavel(
        comp.price_basis, tipo_fiscal, f"{caminho_base}/price_basis", erros
    ):
        ok = False
    if not validar_proveniencia_confirmada(
        comp.proveniencia, f"{caminho_base}/proveniencia/confirmado", erros
    ):
        ok = False
    return ok


def validar_faixa_tabela(
    faixa: TabelaFaixaRascunho,
    tipo_fiscal: str,
    caminho_base: str,
    erros: list[ErroCompilacao],
    *,
    exigir_quantidade: bool,
) -> bool:
    ok = True
    if not validar_price_basis_usavel(
        faixa.price_basis, tipo_fiscal, f"{caminho_base}/price_basis", erros
    ):
        ok = False
    if not validar_proveniencia_confirmada(
        faixa.proveniencia, f"{caminho_base}/proveniencia/confirmado", erros
    ):
        ok = False
    if exigir_quantidade and faixa.quantidade_cotada is None:
        erros.append(
            _erro(
                "APP-QTD-001",
                f"{caminho_base}/quantidade_cotada",
                "Informe a quantidade cotada da faixa ou confirme zero explicitamente. "
                "A regra de correspondência com a população será definida nas etapas 2.4/2.5.",
            )
        )
        ok = False
    return ok
