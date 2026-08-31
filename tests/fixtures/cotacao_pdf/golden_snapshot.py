"""Serialização canônica de extração PDF para goldens sintéticos."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata

RESSALVA_DEDUCAO_ACOMODACAO = (
    "Este golden congela a inferência de acomodação a partir de Q/E/QC/QP no nome do "
    "produto. Não é endosso do comportamento: ele está registrado no §12 como pendente "
    "de decisão, e quebra quando uma operadora mudar a nomenclatura. Se a inferência for "
    "removida, este golden é atualizado deliberadamente."
)

_GOLDEN_ROOT = Path(__file__).resolve().parent / "golden"


def _campo_texto(campo) -> str | None:
    if campo is None:
        return None
    return campo.texto


def _campo_int(campo) -> int | None:
    if campo is None:
        return None
    return campo.inteiro


def _campo_centavos(campo) -> int | None:
    if campo is None:
        return None
    return campo.centavos


def _campo_data(campo) -> str | None:
    if campo is None or campo.data is None:
        return None
    return campo.data.isoformat()


def serializar_opcao(op: OpcaoCotacaoCandidata) -> dict[str, Any]:
    return {
        "plano_nome": _campo_texto(op.plano_nome),
        "acomodacao": _campo_texto(op.acomodacao),
        "regime_copart": _campo_texto(op.regime_copart),
        "copart_percentual": _campo_int(op.copart_percentual),
        "tipo_fiscal": _campo_texto(op.tipo_fiscal),
        "validade": _campo_data(op.validade_oficial),
        "premio_centavos": _campo_centavos(op.premio_saude),
        "iof_centavos": _campo_centavos(op.iof),
        "total_centavos": _campo_centavos(op.total_recorrente),
        "faixas_centavos": [fx.valor.centavos for fx in op.tabela],
        "faixas_price_basis": [fx.valor.price_basis.value for fx in op.tabela],
    }


def serializar_extracao(
    ext: ExtracaoCotacaoCandidata,
    *,
    incluir_ressalva_deducao: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "estado": ext.estado,
        "template_id": ext.documento.template_id,
        "parser_versao": ext.documento.parser_versao,
        "n_opcoes": len(ext.opcoes),
        "opcoes": [serializar_opcao(op) for op in ext.opcoes],
        "alertas_codigos": sorted({a.codigo for a in ext.alertas}),
    }
    if incluir_ressalva_deducao:
        payload["_ressalva_deducacao_acomodacao"] = RESSALVA_DEDUCAO_ACOMODACAO
    return payload


def serializar_parse_direto(
    opcoes: list[OpcaoCotacaoCandidata],
    alertas,
    *,
    parser_versao: str,
    template_id: str | None = None,
    estado: str = "extraido",
    incluir_ressalva_deducao: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "estado": estado,
        "template_id": template_id,
        "parser_versao": parser_versao,
        "n_opcoes": len(opcoes),
        "opcoes": [serializar_opcao(op) for op in opcoes],
        "alertas_codigos": sorted({a.codigo for a in alertas}),
    }
    if incluir_ressalva_deducao:
        payload["_ressalva_deducacao_acomodacao"] = RESSALVA_DEDUCAO_ACOMODACAO
    return payload


def carregar_golden(familia: str, caso: str) -> dict[str, Any]:
    path = _GOLDEN_ROOT / familia / f"{caso}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_extracao_igual_golden(
    atual: dict[str, Any],
    esperado: dict[str, Any],
    *,
    familia: str,
    caso: str,
) -> None:
    if "_ressalva_deducacao_acomodacao" in esperado:
        assert atual.get("_ressalva_deducacao_acomodacao") == esperado[
            "_ressalva_deducacao_acomodacao"
        ]
    for chave in ("estado", "template_id", "parser_versao", "n_opcoes", "alertas_codigos"):
        assert atual.get(chave) == esperado.get(chave), (
            f"{familia}/{caso}: campo {chave!r} divergiu — "
            f"esperado {esperado.get(chave)!r}, obteve {atual.get(chave)!r}"
        )
    assert atual["opcoes"] == esperado["opcoes"], (
        f"{familia}/{caso}: opções divergiram do golden"
    )
