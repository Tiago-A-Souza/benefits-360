"""Hotfix 2.9.1 — SulAmérica com ajustes: extração, validação e reconciliação."""

from __future__ import annotations

import pymupdf

from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.cotacao_pdf.extract import PdfDocumento
from newport_app.cotacao_pdf.coords_extract import localizar_paginas_tabela_sulamerica
from newport_app.cotacao_pdf.sulamerica_table import (
    detectar_sequencia_suspeita,
    extrair_tabelas_pagina_sulamerica,
    validar_linha_tarifaria,
)
from newport_app.models.cotacao_pdf import OpcaoCotacaoCandidata


def _fmt_vals(vals: list[int]) -> str:
    parts = []
    for v in vals:
        reais = v // 100
        cents = v % 100
        parts.append(f"R$ {reais:,}".replace(",", ".") + f",{cents:02d}")
    return " | ".join(parts)

_FAIXAS = "0 a 18  19 a 23  24 a 28  29 a 33  34 a 38  39 a 43  44 a 48  49 a 53  54 a 58  59+"
_VALORES = [
    "283,94",
    "354,92",
    "440,09",
    "488,51",
    "522,71",
    "606,34",
    "724,83",
    "849,51",
    "1011,33",
    "1703,59",
]


def _pagina_base_sul(page: pymupdf.Page, titulo_regime: str) -> None:
    page.insert_text((36, 40), "TABELA DE PREÇOS", fontsize=11)
    page.insert_text((36, 58), titulo_regime, fontsize=10)
    page.insert_text((36, 70), _FAIXAS, fontsize=8)


def build_sulamerica_nome_quebrado() -> bytes:
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=10)
    page = doc.new_page(width=595, height=842)
    _pagina_base_sul(page, "SEM COPARTICIP")
    page.insert_text((36, 148), "Direto Apartamento", fontsize=9)
    x = 121
    for v in _VALORES:
        page.insert_text((x, 151), v, fontsize=7)
        x += 38
    page.insert_text((36, 155), "Nacional", fontsize=9)
    out = doc.tobytes()
    doc.close()
    return out


def build_sulamerica_milhar_partido() -> bytes:
    doc = pymupdf.open()
    for _ in range(4):
        doc.new_page(width=595, height=842).insert_text((36, 36), "SUL AMERICA SAUDE", fontsize=10)
    page = doc.new_page(width=595, height=842)
    _pagina_base_sul(page, "SEM COPARTICIP")
    page.insert_text((36, 126), "Especial Vital RC", fontsize=9)
    vals = _VALORES[:7] + ["933,35", "1", "111,15", "1871,73"]
    x = 121
    for v in vals[:8]:
        page.insert_text((x, 125), v, fontsize=7)
        x += 38
    page.insert_text((x, 125), "1", fontsize=7)
    page.insert_text((x + 12, 125), "111,15", fontsize=7)
    page.insert_text((x + 50, 125), "1871,73", fontsize=7)
    out = doc.tobytes()
    doc.close()
    return out


def _extrair_sintetico(pdf_bytes: bytes):
    with PdfDocumento.abrir(pdf_bytes) as doc:
        paginas = localizar_paginas_tabela_sulamerica(doc)
        assert paginas, "tabela não localizada no PDF sintético"
        return extrair_tabelas_pagina_sulamerica(doc, paginas[-1])


def test_nome_quebrado_duas_linhas_recompoe():
    sec = _extrair_sintetico(build_sulamerica_nome_quebrado())
    assert sec is not None
    assert len(sec.linhas) == 1
    nome = sec.linhas[0].plano_nome
    assert "Direto Apartamento" in nome
    assert "Nacional" in nome
    assert nome.lower() not in {"nacional", "apartamento nacional", "direto apartamento"}


def test_milhar_partido_recompoe_tokens():
    sec = _extrair_sintetico(build_sulamerica_milhar_partido())
    assert sec is not None
    assert len(sec.linhas) == 1
    vals = sec.linhas[0].valores
    assert len(vals) == 10
    assert vals[8] == 111115
    assert vals[9] == 187173


def test_sequencia_tarifaria_suspeita_detectada():
    suspeitas = detectar_sequencia_suspeita([93335, 11115, 187173])
    assert 1 in suspeitas


def test_validacao_nome_generico_bloqueia():
    ok, motivos = validar_linha_tarifaria("Nacional", [10000] * 10)
    assert not ok
    assert "nome_generico" in motivos


def test_reconciliacao_indisponivel_sem_populacao():
    from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
    from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
    from newport_app.models.draft import PriceBasisRascunho

    tabela = [
        faixa_extraida(
            i,
            valor_centavos=10000 + i * 100,
            quantidade=None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="teste",
            trecho_qtd=None,
            parser_versao="test@1",
            documento_hash="hash",
        )
        for i in range(10)
    ]
    op = OpcaoCotacaoCandidata(
        id="op-1",
        plano_nome=novo_campo("Nome", texto="Plano Teste"),
        tabela=tabela,
    )
    rec = reconciliar_opcao(op)
    assert not rec.ok
    assert "Reconciliação ainda não realizada" in (rec.mensagem or "")


def test_relatorio_aceite_privado_sulamerica_ajustes():
    """Executado com corpus privado — valida 22 planos e amostra de valores."""
    import hashlib
    import json
    from pathlib import Path

    from newport_app.config.paths import diretorio_corpus_cotacoes

    hashes = json.loads(
        (
            Path(__file__).resolve().parent / "fixtures" / "cotacao_pdf" / "corpus_aceite_hashes.json"
        ).read_text(encoding="utf-8")
    )
    esperado = hashes["sulamerica_ajustes_dual"]
    corpus = diretorio_corpus_cotacoes()
    conteudo = None
    for pdf in corpus.rglob("*.pdf"):
        if hashlib.sha256(pdf.read_bytes()).hexdigest() == esperado:
            conteudo = pdf.read_bytes()
            break
    if conteudo is None:
        import pytest

        pytest.skip("Corpus privado indisponível")

    ext = parse_cotacao_pdf(
        conteudo,
        estudo_id="aceite",
        documento_id="doc",
        nome_arquivo="sanitizado.pdf",
    )
    assert ext.documento.template_id == "sulamerica-pme-ajustes-dual"
    assert len(ext.opcoes) == 22

    nomes = [(op.plano_nome.texto or "").strip() for op in ext.opcoes]
    proibidos = {"Nacional", "Apartamento Nacional", "Direto Apartamento"}
    assert not any(n in proibidos for n in nomes)

    sem = [op for op in ext.opcoes if op.regime_copart and op.regime_copart.texto == "sem"]
    percentual = [
        op for op in ext.opcoes if op.regime_copart and op.regime_copart.texto == "percentual"
    ]
    assert len(sem) == 11
    assert len(percentual) == 11

    for op in ext.opcoes:
        assert len(op.tabela) == 10
        assert not op.reconciliacao.ok
        assert "Reconciliação ainda não realizada" in (op.reconciliacao.mensagem or "")

    # Plano com valores > R$ 1.000 — Especial Vital RC (sem copart)
    especial = next(
        op
        for op in sem
        if (op.plano_nome.texto or "").startswith("Especial Vital RC")
        and "Apartamento" not in (op.plano_nome.texto or "")
    )
    vals_especial = [fx.valor.centavos for fx in especial.tabela]
    assert vals_especial[7] == 93335
    assert vals_especial[8] == 111115
    assert vals_especial[9] == 187173
    assert all(v > 100000 for v in vals_especial[8:])

    direto_enf = next(
        op for op in sem if (op.plano_nome.texto or "").startswith("Direto Enfermaria")
    )
    vals_enf_sem = [fx.valor.centavos for fx in direto_enf.tabela]
    assert vals_enf_sem[0] == 26776

    direto_ap = next(
        op
        for op in sem
        if (op.plano_nome.texto or "").startswith("Direto Apartamento")
    )
    vals_direto = [fx.valor.centavos for fx in direto_ap.tabela]
    assert vals_direto[0] == 28569

    direto_enf = next(
        op
        for op in percentual
        if (op.plano_nome.texto or "").startswith("Direto Enfermaria")
    )
    vals_enf = [fx.valor.centavos for fx in direto_enf.tabela]
    assert len(vals_enf) == 10
    assert vals_enf[9] > 100000

    print("\n=== ACEITE PRIVADO SulAmérica ajustes ===")
    print(f"Total opções: {len(ext.opcoes)} (sem={len(sem)}, 30%={len(percentual)})")
    print(f"Especial Vital RC (sem cp): {_fmt_vals(vals_especial)}")
    print(f"Direto Enfermaria Nacional (sem cp): {_fmt_vals(vals_enf_sem)}")
    print(f"{direto_ap.plano_nome.texto} (sem cp): {_fmt_vals(vals_direto)}")
    print(f"{direto_enf.plano_nome.texto} (30%): {_fmt_vals(vals_enf)}")
