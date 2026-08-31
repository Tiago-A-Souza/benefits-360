"""Gera JSONs golden dos parsers — rodar após alteração intencional do parser."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newport_app.cotacao_pdf.parsers import bradesco  # noqa: E402
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf  # noqa: E402
from tests.fixtures.cotacao_pdf.build_pdfs import (  # noqa: E402
    build_amil_bronze_sem_acomodacao,
    build_amil_prata_qc_milhar,
    build_amil_sem_tabela,
    build_bradesco_doc_caso_feliz,
    build_bradesco_doc_sem_tabelas,
    build_porto_27_paginas,
    build_porto_27_serie_p220,
    build_porto_sem_tabela_geral,
    build_porto_sem_validade,
    build_sulamerica_com_copart,
    build_sulamerica_faixa_unica_com_vidas,
    build_sulamerica_sem_copart,
    build_sulamerica_sem_tabela,
)
from tests.fixtures.cotacao_pdf.golden_snapshot import (  # noqa: E402
    serializar_extracao,
    serializar_parse_direto,
)

OUT = ROOT / "tests" / "fixtures" / "cotacao_pdf" / "golden"


def _gravar(familia: str, caso: str, payload: dict) -> None:
    dest = OUT / familia / f"{caso}.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("wrote", dest.relative_to(ROOT))


def _pipeline(pdf: bytes, nome: str, *, ressalva: bool = False) -> dict:
    ext = parse_cotacao_pdf(pdf, estudo_id="golden", documento_id="d", nome_arquivo=nome)
    return serializar_extracao(ext, incluir_ressalva_deducao=ressalva)


def main() -> None:
    _gravar("amil", "caso_feliz_prata_qc", _pipeline(build_amil_prata_qc_milhar(), "amil-qc.pdf", ressalva=True))
    _gravar(
        "amil",
        "bronze_sem_acomodacao",
        _pipeline(build_amil_bronze_sem_acomodacao(), "amil-bronze.pdf"),
    )
    _gravar("amil", "layout_sem_tabela", _pipeline(build_amil_sem_tabela(), "amil-vazio.pdf"))

    _gravar("porto", "caso_feliz_p320", _pipeline(build_porto_27_paginas(), "porto27.pdf", ressalva=True))
    _gravar("porto", "serie_p220", _pipeline(build_porto_27_serie_p220(), "porto-p220.pdf", ressalva=True))
    _gravar("porto", "sem_validade", _pipeline(build_porto_sem_validade(), "porto-sem-val.pdf", ressalva=True))
    _gravar(
        "porto",
        "layout_sem_tabela_geral",
        _pipeline(build_porto_sem_tabela_geral(), "porto-sem-tab.pdf", ressalva=True),
    )

    _gravar("sulamerica", "caso_feliz_sem_copart", _pipeline(build_sulamerica_sem_copart(), "sul-sem.pdf"))
    _gravar(
        "sulamerica",
        "com_acomodacao_faixa_unica",
        _pipeline(build_sulamerica_faixa_unica_com_vidas(), "sul-faixa.pdf"),
    )
    _gravar(
        "sulamerica",
        "dois_regimes_copart",
        _pipeline(build_sulamerica_com_copart(), "sul-dual.pdf"),
    )
    _gravar("sulamerica", "layout_sem_tabela", _pipeline(build_sulamerica_sem_tabela(), "sul-vazio.pdf"))

    doc_ok = build_bradesco_doc_caso_feliz()
    ops, als, _ = bradesco.parse(doc_ok, documento_hash="golden-bra")
    _gravar(
        "bradesco",
        "caso_feliz_tabela",
        serializar_parse_direto(
            ops,
            als,
            parser_versao=bradesco.PARSER_VERSAO,
            template_id=bradesco.TEMPLATE_ID,
        ),
    )
    doc_vazio = build_bradesco_doc_sem_tabelas()
    ops2, als2, _ = bradesco.parse(doc_vazio, documento_hash="golden-bra-vazio")
    _gravar(
        "bradesco",
        "layout_sem_tabelas",
        serializar_parse_direto(
            ops2,
            als2,
            parser_versao=bradesco.PARSER_VERSAO,
            template_id=bradesco.TEMPLATE_ID,
        ),
    )


if __name__ == "__main__":
    main()
