"""Série P da Porto — não descartar planos alfanuméricos nem omitir em silêncio."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.cotacao_pdf.coords_extract import (
    _eh_nome_plano_valido,
    _parear_linhas_plano,
)
from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf
from newport_app.config.paths import diretorio_corpus_cotacoes


def _corpus_porto(*nomes: str) -> Path | None:
    base = diretorio_corpus_cotacoes()
    if not base.is_dir():
        return None
    for nome in nomes:
        hits = list(base.rglob(nome))
        if hits:
            return hits[0]
    # ATEF / Anistia fora do .private (downloads locais)
    extras = [
        Path(r"C:\Users\tiago\Downloads\ATEF-20260807T152847Z-1-001"),
        Path(r"C:\Users\tiago\Downloads\ANISTIA INTERNACIONAL-20260807T174038Z-1-001"),
    ]
    for root in extras:
        if not root.is_dir():
            continue
        for nome in nomes:
            hits = list(root.rglob(nome))
            if hits:
                return hits[0]
    return None


@pytest.mark.parametrize(
    "nome",
    [
        "P220 Q",
        "P320 Q",
        "P420 Q",
        "P470 Q",
        "P520 Q",
        "P220 E",
        "P320 E",
        "P220 Q COPAR",
        "P320 E COPAR 30",
        "BRONZE BRASIL I Q",
    ],
)
def test_nome_plano_porto_aceita_serie_p(nome: str):
    assert _eh_nome_plano_valido(nome)


def test_completude_alerta_quando_linha_ilegivel(monkeypatch):
    """Linha com 10 valores e nome inválido → candidata contada, não montada → PDF-PORTO-006."""
    header_ws = [(100.0, 50.0, 140.0, 60.0, "0-18"), (150.0, 50.0, 200.0, 60.0, "59")]
    # Nome inválido (só dígitos) + 10 preços
    words_bad = [(10.0, 80.0, 40.0, 90.0, "123")]
    for i in range(10):
        words_bad.append((110.0 + i * 40, 80.0, 140.0 + i * 40, 90.0, f"{100 + i},00"))
    # Plano válido
    words_ok = [(10.0, 100.0, 80.0, 110.0, "P220"), (50.0, 100.0, 70.0, 110.0, "Q")]
    for i in range(10):
        words_ok.append((110.0 + i * 40, 100.0, 140.0 + i * 40, 110.0, f"{200 + i},00"))

    rows = [
        (50.0, header_ws),
        (80.0, words_bad),
        (100.0, words_ok),
    ]
    linhas, candidatas = _parear_linhas_plano(rows, header_y=50.0, header_ws=header_ws, pagina=0)
    assert candidatas == 2
    assert len(linhas) == 1
    assert linhas[0].plano_nome.startswith("P220")

    from newport_app.cotacao_pdf.coords_extract import SecaoTabelaPagina
    from newport_app.cotacao_pdf.extract import PdfDocumento
    from newport_app.cotacao_pdf.parsers import porto as porto_mod

    secao = SecaoTabelaPagina(
        pagina=1,
        regime_tipo="sem",
        copart_percentual=None,
        regime_rotulo="Sem coparticipação",
        linhas=linhas,
        cabecalho="0-18 … 59",
        linhas_tarifarias_detectadas=candidatas,
    )

    class _Doc:
        numero_paginas = 1

        def texto_todo(self):
            return "PORTO SEGURO Tabela Geral de Prêmios"

        def texto(self, _pagina):
            return "PORTO SEGURO"

    monkeypatch.setattr(porto_mod, "localizar_paginas_tabela_geral", lambda _d: [0])
    monkeypatch.setattr(porto_mod, "texto_pagina_enriquecido", lambda _d, _p: ("PORTO", False))
    monkeypatch.setattr(porto_mod, "extrair_tabelas_pagina", lambda _d, _p: secao)
    monkeypatch.setattr(porto_mod, "_plano_resumo", lambda _d: (None, 0, ""))
    monkeypatch.setattr(
        porto_mod, "_extrair_resumo_financeiro", lambda _d: (None, None, None, {})
    )

    opcoes, alertas, meta = porto_mod.parse(_Doc(), documento_hash="h")  # type: ignore[arg-type]
    assert len(opcoes) == 1
    assert meta["linhas_tarifarias_detectadas"] == 2
    assert any(a.codigo == "PDF-PORTO-006" for a in alertas)
    assert "1 plano" in next(a.mensagem for a in alertas if a.codigo == "PDF-PORTO-006")


@pytest.mark.private_corpus
def test_porto3_extrai_serie_p_e_p220_q_copar():
    path = _corpus_porto("PORTO3.pdf")
    if path is None:
        pytest.skip("PORTO3.pdf indisponível")
    ext = parse_cotacao_pdf(
        path.read_bytes(),
        estudo_id="porto3",
        documento_id="doc-porto3",
        nome_arquivo="PORTO3.pdf",
    )
    nomes = [(op.plano_nome.texto or "").strip().upper() for op in ext.opcoes]
    assert len(ext.opcoes) >= 36

    serie_p_sem = [
        "P220 Q",
        "P320 Q",
        "P420 Q",
        "P470 Q",
        "P520 Q",
        "P220 E",
        "P320 E",
    ]
    for nome in serie_p_sem:
        assert any(n == nome or n.startswith(nome + " ") for n in nomes), nome

    # 18 sem copart + 18 com copart
    sem = [
        op
        for op in ext.opcoes
        if op.regime_copart and op.regime_copart.texto == "sem"
    ]
    percentual = [
        op
        for op in ext.opcoes
        if op.regime_copart and op.regime_copart.texto == "percentual"
    ]
    assert len(sem) == 18
    assert len(percentual) == 18

    p220 = next(
        op
        for op in ext.opcoes
        if (op.plano_nome.texto or "").upper().startswith("P220 Q")
        and "COPAR" in (op.plano_nome.texto or "").upper()
    )
    vals = [fx.valor.centavos for fx in p220.tabela]
    # faixas: 0=0-18, 1=19-23, ..., 7=49-53, 8=54-58
    assert vals[1] == 244_98
    assert vals[7] == 486_84
    assert vals[8] == 601_53
    assert "PDF-PORTO-006" not in {a.codigo for a in ext.alertas}


@pytest.mark.private_corpus
def test_porto_anistia_mantem_serie_p():
    path = _corpus_porto("PORTO.pdf")
    if path is None:
        pytest.skip("PORTO.pdf indisponível")
    ext = parse_cotacao_pdf(
        path.read_bytes(),
        estudo_id="porto",
        documento_id="doc-porto",
        nome_arquivo="PORTO.pdf",
    )
    nomes = {(op.plano_nome.texto or "").strip().upper() for op in ext.opcoes}
    for nome in ("P220 E", "P320 E", "P220 Q", "P320 Q", "P420 Q", "P520 Q"):
        assert any(n == nome or n.startswith(nome + " ") for n in nomes), nome
    # Não perder planos em relação ao patamar anterior (22) — agora inclui série P
    assert len(ext.opcoes) >= 22


@pytest.mark.private_corpus
def test_corpus_porto_contagens_relatorio(capsys):
    base = diretorio_corpus_cotacoes()
    if not base.is_dir():
        pytest.skip("Corpus privado indisponível")
    pdfs = sorted({p.resolve() for p in base.rglob("PORTO*.pdf")})
    if not pdfs:
        pytest.skip("Nenhum PORTO*.pdf no corpus")
    for pdf in pdfs:
        ext = parse_cotacao_pdf(
            pdf.read_bytes(),
            estudo_id="rel",
            documento_id="d",
            nome_arquivo=pdf.name,
        )
        serie_p = sum(
            1
            for op in ext.opcoes
            if (op.plano_nome.texto or "").upper().startswith("P")
            and (op.plano_nome.texto or "")[1:4].isdigit()
        )
        print(f"{pdf.name}: {len(ext.opcoes)} opcoes, {serie_p} serie-P")
