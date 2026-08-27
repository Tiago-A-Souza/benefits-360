"""Harness: cada uma das 15 mutações deve ser detectada."""

from __future__ import annotations

from pathlib import Path

from tests.harness_mutacoes_paridade import MUTACOES, rodar_todas


def test_quinze_mutacoes_sao_detectadas(tmp_path: Path):
    resultados = rodar_todas(tmp_path)
    assert len(resultados) == 15
    cegas = [r for r in resultados if r.celulas_acusadas == 0]
    relatorio = "\n".join(
        f"M{r.id:02d} {r.nome}: acusadas={r.celulas_acusadas} "
        f"via={','.join(r.assercoes) or '—'}"
        for r in resultados
    )
    print(relatorio)
    assert not cegas, (
        "Mutações que passaram despercebidas (cegueira):\n"
        + "\n".join(f"M{r.id} {r.nome}" for r in cegas)
        + "\n\n"
        + relatorio
    )


def test_harness_lista_quinze_mutacoes():
    assert len(MUTACOES) == 15
    ids = [m[0] for m in MUTACOES]
    assert ids == list(range(1, 16))
