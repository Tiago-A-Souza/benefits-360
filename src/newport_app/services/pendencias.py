"""Tradução de pendências de compilação para a interface."""

from __future__ import annotations

from collections import defaultdict

from newport_app.draft_compiler import compile
from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import PendenciaItem
from newport_app.policy.registry import default_registry
from newport_app.rascunho.cenarios_sync import cenarios_sincronizados

_TRADUCOES: dict[str, tuple[str, str, str]] = {
    "APP-IMP-001": (
        "bloqueio",
        "Tipo fiscal do plano atual",
        "Informe se o plano atual é contrato da seguradora ou da operadora.",
    ),
    "APP-IMP-002": (
        "bloqueio",
        "Regime de coparticipação do plano atual",
        "Selecione o regime de coparticipação de cada plano importado.",
    ),
    "APP-ESC-001": (
        "bloqueio",
        "Data de referência para idades",
        "Informe a data usada para calcular as idades dos beneficiários.",
    ),
    "APP-ESC-002": (
        "bloqueio",
        "Comparação do plano atual",
        "Confirme se a comparação usa o contrato vigente ou o reajustado.",
    ),
    "APP-ESC-003": (
        "bloqueio",
        "Fonte do valor atual",
        "Confirme se prevalece a tabela do plano ou o valor de fatura por vida.",
    ),
    "APP-FIN-001": (
        "bloqueio",
        "Base de IOF pendente",
        "Informe se cada valor inclui IOF, exclui IOF ou não se aplica.",
    ),
    "APP-FIN-002": (
        "bloqueio",
        "Confirmação de valor pendente",
        "Confirme explicitamente os valores informados manualmente.",
    ),
    "APP-FIN-003": (
        "bloqueio",
        "Valor financeiro incompleto",
        "Há campos monetários sem valor informado.",
    ),
    "APP-QTD-001": (
        "bloqueio",
        "Quantidade cotada na proposta",
        "Informe a quantidade cotada de cada faixa ou confirme zero.",
    ),
    "APP-DOC-001": (
        "bloqueio",
        "Documento de cotação pendente",
        "Conclua a extração ou confirme o PDF antes de calcular.",
    ),
    "APP-BAS-001": (
        "bloqueio",
        "Base IOF inválida",
        "A opção «não se aplica» só é permitida para operadoras sem IOF.",
    ),
    "APP-ET3-001": (
        "bloqueio",
        "Nenhuma cotação cadastrada",
        "Cadastre ao menos uma opção de plano na etapa Cotações.",
    ),
    "APP-ET4-001": (
        "bloqueio",
        "Comparação com plano atual pendente",
        "Defina com qual plano atual comparar cada opção selecionada.",
    ),
}


def _etapa_erro(codigo: str, caminho: str) -> int:
    if codigo in ("APP-ET3-001",):
        return 3
    if codigo in ("APP-ET4-001",):
        return 4
    if codigo.startswith("APP-ESC") or codigo.startswith("APP-IMP"):
        return 2
    if "/vidas/" in caminho or "/subgrupos_atuais/" in caminho:
        return 2
    if "/opcoes_proposta/" in caminho or codigo in ("APP-QTD-001", "APP-DOC-001"):
        return 3
    if "/cenarios/" in caminho:
        return 4
    if codigo.startswith("APP-FIN") or codigo == "APP-BAS-001":
        return 2 if "/opcoes_proposta/" not in caminho else 3
    return 2


def _titulo_descricao_agrupados(
    codigo: str,
    titulo: str,
    descricao: str,
    quantidade: int,
) -> tuple[str, str]:
    if quantidade <= 1:
        return titulo, descricao
    rotulos = {
        "APP-FIN-001": f"Base de IOF pendente em {quantidade} valores",
        "APP-FIN-002": f"Confirmação de valor pendente em {quantidade} campos",
        "APP-FIN-003": f"Valor financeiro incompleto em {quantidade} campos",
        "APP-IMP-001": f"Tipo fiscal pendente em {quantidade} planos",
        "APP-IMP-002": f"Regime de coparticipação pendente em {quantidade} planos",
    }
    if codigo in rotulos:
        return rotulos[codigo], descricao
    return titulo, f"{descricao} ({quantidade} ocorrências)."


def _item_de_erro(codigo: str, erros: list[ErroCompilacao]) -> PendenciaItem:
    caminho = erros[0].caminho
    etapa = _etapa_erro(codigo, caminho)
    quantidade = len(erros)
    if codigo in _TRADUCOES:
        tipo, titulo, descricao = _TRADUCOES[codigo]
        titulo, descricao = _titulo_descricao_agrupados(codigo, titulo, descricao, quantidade)
        acao = "Complete a etapa correspondente no fluxo guiado."
        if codigo == "APP-QTD-001":
            acao = (
                "Na etapa Cotações, abra o PDF, confirme a tabela de cada plano "
                "e clique em «Adicionar ao comparativo» novamente."
            )
        return PendenciaItem(
            tipo=tipo,
            titulo=titulo,
            descricao=descricao,
            acao_sugerida=acao,
            codigo=codigo,
            etapa=etapa,
            quantidade=quantidade,
        )
    return PendenciaItem(
        tipo="bloqueio",
        titulo="Informação pendente no estudo",
        descricao=erros[0].mensagem,
        acao_sugerida="Revise os dados nas etapas anteriores.",
        codigo=codigo,
        etapa=etapa,
        quantidade=quantidade,
    )


def pendencias_compilacao(rascunho: RascunhoEstudo) -> list[PendenciaItem]:
    resultado = compile(rascunho, policy_registry=default_registry)
    por_codigo: dict[str, list[ErroCompilacao]] = defaultdict(list)
    for erro in resultado.erros:
        por_codigo[erro.codigo].append(erro)

    itens: list[PendenciaItem] = [
        _item_de_erro(codigo, erros) for codigo, erros in sorted(por_codigo.items())
    ]

    if not rascunho.opcoes_proposta:
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Nenhuma cotação cadastrada",
                descricao="Cadastre ao menos uma opção de plano na etapa Cotações.",
                acao_sugerida="Use a etapa Cotações para incluir a proposta.",
                codigo="APP-ET3-001",
                etapa=3,
                quantidade=1,
            )
        )
    if rascunho.opcoes_proposta and not cenarios_sincronizados(rascunho):
        etapa = 4 if len(rascunho.subgrupos_atuais) > 1 else 3
        acao = (
            "Use a etapa Correspondência com os planos atuais."
            if etapa == 4
            else "Aguarde a sincronização automática ou revise as cotações."
        )
        itens.append(
            PendenciaItem(
                tipo="bloqueio",
                titulo="Comparação com plano atual pendente",
                descricao="Defina com qual plano atual comparar cada opção selecionada.",
                acao_sugerida=acao,
                codigo="APP-ET4-001",
                etapa=etapa,
                quantidade=1,
            )
        )
    return itens
