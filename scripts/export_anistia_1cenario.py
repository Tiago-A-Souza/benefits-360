import argparse
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import resolver_colunas_selecionadas
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import montar_rede_apresentacao
from newport_app.snapshot.comparativo import ler_comparativo_congelado
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.fixtures.siscor.xlsx_builder import planilha_anistia_41_sintetica
from tests.test_correcao_resumo_regime import _aprovar as aprovar
from tests.test_frente2_grupo_familiar import _anistia_com_vinculos, _ids_seis

ALT_LINHA, ALT_PAG = 38, 720


def _saida(planos: int) -> Path:
    base = ROOT / ".private/runtime/entregaveis/rede-cabecalho-leitura"
    if planos == 1:
        nome = "anistia_1cenario_com_localizacao.html"
    else:
        nome = f"anistia_{planos}planos_com_localizacao.html"
    return base / nome


def main() -> None:
    ap = argparse.ArgumentParser(description="Export HTML Anistia (aba Rede com localização).")
    ap.add_argument(
        "--planos",
        type=int,
        default=1,
        help="Colunas de proposta na aba Rede (1 = um cenário; 5 = largura 1180px).",
    )
    args = ap.parse_args()
    n_planos = max(1, args.planos)
    saida = _saida(n_planos)
    r = _anistia_com_vinculos()
    p = parse_planilha_siscor(
        planilha_anistia_41_sintetica(), estudo_id="t", documento_id="d"
    )
    vidas = [
        v.model_copy(
            update={
                "uf": (l.uf or "").upper() if l.uf else None,
                "cidade": l.cidade,
            }
        )
        for v, l in zip(r.vidas, p.candidata.linhas, strict=True)
    ]
    r = r.model_copy(update={"vidas": vidas})
    tmp = ROOT / ".private/runtime/_tmp_1cen"
    snap = aprovar(tmp, r)
    matriz = ler_comparativo_congelado(snap.payload)
    calculadas = [x for x in matriz.propostas if x.calculo_realizado]
    cen_ids = resolver_colunas_selecionadas([], calculadas)
    cen_rede = list(cen_ids[:n_planos])
    doc = montar_rede_apresentacao(r, cen_rede)
    assert doc
    ids_vm = _ids_seis()
    html = render_html_completo(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids_vm),
        construir_view_model(snap, modo="faixas", propostas_selecionadas=ids_vm),
        construir_view_model(
            snap,
            modo="grupo_familiar",
            propostas_selecionadas=ids_vm,
            beneficiarios_agregados=False,
        ),
        rede=doc,
        estudo_id=r.id,
    )
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(html, encoding="utf-8")
    print(f"EXPORT={saida}")
    print(
        f"cenarios_rede={cen_rede} colunas_por_secao={len(doc.secoes[0].colunas)}"
    )

    chunks = html.split("<div class='secao-rede'>")[1:]
    total_pag = 0
    for i, (sec, chunk) in enumerate(zip(doc.secoes, chunks, strict=True), 1):
        tabs = re.findall(
            r"<table class='tabela-rede[^']*'>(.*?)</table>", chunk, re.S
        )
        print(
            f"SEC{i} prestadores={sec.total_linhas} blocos={len(sec.blocos)} "
            f"tabelas={len(tabs)}"
        )
        for j, tab in enumerate(tabs, 1):
            tbody = re.search(r"<tbody>(.*?)</tbody>", tab, re.S)
            corpo = tbody.group(1) if tbody else ""
            n = len(re.findall(r"<tr", corpo))
            prest = len(re.findall(r"class='p-rede'", corpo))
            pag = max(1, (n * ALT_LINHA + 80) // ALT_PAG)
            total_pag += pag
            print(
                f"  tabela{j} tbody_tr={n} prestadores_tr={prest} paginas_est={pag}"
            )
    print(f"TOTAL_paginas_estimadas_rede={total_pag}")


if __name__ == "__main__":
    main()
