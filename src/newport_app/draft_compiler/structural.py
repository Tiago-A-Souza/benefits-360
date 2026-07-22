"""Validação estrutural — rejeita ao salvar, não confunde com rascunho incompleto."""

from __future__ import annotations

from collections import Counter

from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import RascunhoEstudo


class RascunhoEstruturalInvalidoError(Exception):
    def __init__(self, erros: list[ErroCompilacao]) -> None:
        self.erros = erros
        super().__init__(f"rascunho estruturalmente inválido ({len(erros)} erro(s))")


def _erro(codigo: str, caminho: str, mensagem: str) -> ErroCompilacao:
    return ErroCompilacao(
        codigo=codigo,
        caminho=caminho,
        mensagem=mensagem,
        severidade="bloqueante",
    )


def _verificar_duplicados(ids: list[str], caminho_base: str, erros: list[ErroCompilacao]) -> None:
    contagem = Counter(ids)
    for id_val, qtd in contagem.items():
        if qtd > 1:
            erros.append(
                _erro(
                    "APP-STR-001",
                    caminho_base,
                    "Há identificadores repetidos no estudo. Cada item deve ter um código único.",
                )
            )
            break


def validar_estrutura(rascunho: RascunhoEstudo) -> list[ErroCompilacao]:
    erros: list[ErroCompilacao] = []

    _verificar_duplicados([v.id for v in rascunho.vidas], "/vidas", erros)
    _verificar_duplicados([sg.id for sg in rascunho.subgrupos_atuais], "/subgrupos_atuais", erros)
    _verificar_duplicados([op.id for op in rascunho.opcoes_proposta], "/opcoes_proposta", erros)
    _verificar_duplicados([r.id for r in rascunho.regimes_copart], "/regimes_copart", erros)
    _verificar_duplicados([c.id for c in rascunho.cenarios], "/cenarios", erros)
    _verificar_duplicados(
        [d.id for d in rascunho.documentos_cotacao],
        "/documentos_cotacao",
        erros,
    )
    _verificar_duplicados(
        [d.id for d in rascunho.documentos_siscor],
        "/documentos_siscor",
        erros,
    )

    for cenario in rascunho.cenarios:
        _verificar_duplicados(
            [a.id for a in cenario.atribuicoes],
            f"/cenarios/{cenario.id}/atribuicoes",
            erros,
        )

    subgrupo_ids = {sg.id for sg in rascunho.subgrupos_atuais}
    opcao_ids = {op.id for op in rascunho.opcoes_proposta}
    regime_ids = {r.id for r in rascunho.regimes_copart}
    documento_ids = {d.id for d in rascunho.documentos_cotacao}

    for idx, vida in enumerate(rascunho.vidas):
        if vida.subgrupo_atual_id is not None and vida.subgrupo_atual_id not in subgrupo_ids:
            erros.append(
                _erro(
                    "APP-STR-002",
                    f"/vidas/{idx}/subgrupo_atual_id",
                    "Referência a um grupo de plano atual que não existe no estudo.",
                )
            )

    for idx, sg in enumerate(rascunho.subgrupos_atuais):
        if sg.regime_copart_id is not None and sg.regime_copart_id not in regime_ids:
            erros.append(
                _erro(
                    "APP-STR-002",
                    f"/subgrupos_atuais/{idx}/regime_copart_id",
                    "Referência a um regime de coparticipação que não existe no estudo.",
                )
            )
        faixas = [t.faixa for t in sg.tabela_atual]
        if len(faixas) != len(set(faixas)):
            erros.append(
                _erro(
                    "APP-STR-003",
                    f"/subgrupos_atuais/{idx}/tabela_atual",
                    "Há faixas etárias repetidas na tabela do plano atual.",
                )
            )

    for idx, op in enumerate(rascunho.opcoes_proposta):
        if op.regime_copart_id not in regime_ids:
            erros.append(
                _erro(
                    "APP-STR-002",
                    f"/opcoes_proposta/{idx}/regime_copart_id",
                    "Referência a um regime de coparticipação que não existe no estudo.",
                )
            )
        if op.documento_cotacao_id is not None and op.documento_cotacao_id not in documento_ids:
            erros.append(
                _erro(
                    "APP-STR-002",
                    f"/opcoes_proposta/{idx}/documento_cotacao_id",
                    "Referência a um documento de cotação que não existe no estudo.",
                )
            )
        faixas = [t.faixa for t in op.tabela]
        if len(faixas) != len(set(faixas)):
            erros.append(
                _erro(
                    "APP-STR-003",
                    f"/opcoes_proposta/{idx}/tabela",
                    "Há faixas etárias repetidas na tabela da proposta.",
                )
            )

    for idx_c, cenario in enumerate(rascunho.cenarios):
        alvos_vistos: set[str] = set()
        for idx_a, atrib in enumerate(cenario.atribuicoes):
            if atrib.opcao_plano_id not in opcao_ids:
                erros.append(
                    _erro(
                        "APP-STR-002",
                        f"/cenarios/{idx_c}/atribuicoes/{idx_a}/opcao_plano_id",
                        "Referência a uma opção de proposta que não existe no estudo.",
                    )
                )
            if atrib.alvo_tipo == "subgrupo":
                if atrib.alvo_id not in subgrupo_ids:
                    erros.append(
                        _erro(
                            "APP-STR-002",
                            f"/cenarios/{idx_c}/atribuicoes/{idx_a}/alvo_id",
                            "Referência a um grupo de plano atual que não existe no estudo.",
                        )
                    )
            elif atrib.alvo_tipo == "vida":
                if atrib.alvo_id not in {v.id for v in rascunho.vidas}:
                    erros.append(
                        _erro(
                            "APP-STR-002",
                            f"/cenarios/{idx_c}/atribuicoes/{idx_a}/alvo_id",
                            "Referência a um beneficiário que não existe no estudo.",
                        )
                    )
            if atrib.alvo_id in alvos_vistos:
                erros.append(
                    _erro(
                        "APP-STR-004",
                        f"/cenarios/{idx_c}/atribuicoes/{idx_a}/alvo_id",
                        "Há atribuições duplicadas para o mesmo alvo no cenário.",
                    )
                )
            alvos_vistos.add(atrib.alvo_id)

    return erros
