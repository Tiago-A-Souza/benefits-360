#!/usr/bin/env python3
"""Gera exemplos HTML fictícios — ETAPA 2.8."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newport_app.models.snapshot import (  # noqa: E402
    AprovarSnapshotRequest,
    GerarApresentacaoRequest,
)
from newport_app.repository.historico import HistoricoRepository  # noqa: E402
from newport_app.repository.snapshot import SnapshotRepository  # noqa: E402
from newport_app.repository.sqlite import SQLiteStudyRepository  # noqa: E402
from newport_app.seed.ficticio import rascunho_demo_12_vidas  # noqa: E402
from newport_app.services.apresentacao import ApresentacaoService  # noqa: E402
from newport_app.services.snapshot import SnapshotService  # noqa: E402


def main() -> None:
    destino = ROOT / ".private" / "runtime" / "entregaveis" / "exemplos-2.8"
    destino.mkdir(parents=True, exist_ok=True)
    db = destino / "_geracao.db"
    if db.is_file():
        db.unlink()

    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    apres = ApresentacaoService(snap_svc, snap_repo, destino)

    rascunho = rascunho_demo_12_vidas()
    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato("demo-12")
    snap_svc.aprovar_snapshot(
        "demo-12",
        gerado.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Gerador Exemplos", confirmo_conteudo=True),
    )

    req_faixas = GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"])
    req_benef = GerarApresentacaoRequest(modo="beneficiario", propostas_selecionadas=["op-1"])

    res_faixas = apres.gerar_html("demo-12", gerado.snapshot_id, req_faixas)
    res_benef = apres.gerar_html("demo-12", gerado.snapshot_id, req_benef)

    print("Exemplos gerados em:", destino)
    print("  Faixas:", destino / res_faixas.caminho_relativo)
    print("  Beneficiário:", destino / res_benef.caminho_relativo)


if __name__ == "__main__":
    main()
