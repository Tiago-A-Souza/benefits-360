#!/usr/bin/env python3
"""Análise sanitizada do corpus privado de cotações PDF."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newport_app.config.paths import diretorio_corpus_cotacoes, diretorio_golden_privado
from newport_app.cotacao_pdf.corpus_analyze import analisar_diretorio, matriz_cobertura
from newport_app.cotacao_pdf.template_families import FAMILIAS


def main() -> None:
    corpus = diretorio_corpus_cotacoes()
    if not corpus.is_dir():
        print(f"Corpus não encontrado: {corpus}")
        sys.exit(1)

    resumo = analisar_diretorio(corpus)
    matriz = matriz_cobertura(resumo)

    saida_dir = diretorio_golden_privado()
    saida_dir.mkdir(parents=True, exist_ok=True)

    path_resumo = saida_dir / "corpus_caracterizacao.json"
    path_matriz = saida_dir / "corpus_cobertura.json"

    path_resumo.write_text(
        json.dumps(resumo, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    path_matriz.write_text(
        json.dumps(matriz, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    familias_corpus = len(resumo.get("familias", {}))
    familias_sem_doc = resumo.get("familias_sem_documento", [])

    print(f"Corpus analisado: {corpus}")
    print(f"Documentos: {resumo['total_documentos']}")
    print(f"Famílias definidas: {len(FAMILIAS)}")
    print(f"Famílias no corpus: {familias_corpus}")
    print(f"Famílias sem documento: {len(familias_sem_doc)}")
    if familias_sem_doc:
        for fid in familias_sem_doc:
            print(f"  - {fid}")
    print(f"Não reconhecidos: {len(resumo['nao_reconhecidos_hashes'])}")
    print(f"Resumo: {path_resumo}")
    print(f"Matriz: {path_matriz}")
    print()
    print("Famílias por operadora (frequência no corpus):")
    for op, info in resumo["cobertura_por_operadora"].items():
        print(f"  {op}: {info['reconhecidos']}/{info['total']} reconhecidos")
        for fid, qtd in info.get("familias", {}).items():
            print(f"    - {fid}: {qtd} doc(s)")


if __name__ == "__main__":
    main()
