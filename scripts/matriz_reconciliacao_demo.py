#!/usr/bin/env python3
"""Matriz de reconciliação demo — ferramenta de diagnóstico ETAPA 2.8."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from newport_app.models.draft import TabelaFaixaRascunho
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.presentation.builder import construir_view_model
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService


def _rascunho_duas_propostas():
    base = rascunho_demo_12_vidas()
    tabela_b = [
        TabelaFaixaRascunho(
            faixa=f.faixa,
            valor_centavos=f.valor_centavos + 50_000,
            quantidade_cotada=f.quantidade_cotada,
            price_basis=f.price_basis,
            proveniencia=f.proveniencia,
        )
        for f in base.opcoes_proposta[0].tabela
    ]
    op2 = base.opcoes_proposta[0].model_copy(
        update={"id": "op-2", "plano_nome": "Proposta B — valores maiores", "tabela": tabela_b}
    )
    return base.model_copy(update={"opcoes_proposta": [base.opcoes_proposta[0], op2]})


def main() -> None:
    parser = argparse.ArgumentParser(description="Matriz de reconciliação por faixa e proposta.")
    parser.add_argument(
        "--propostas",
        nargs="+",
        default=["op-1", "op-2"],
        help="IDs das propostas selecionadas",
    )
    args = parser.parse_args()

    td = Path(tempfile.mkdtemp())
    repo = SQLiteStudyRepository(td / "t.db")
    hist = HistoricoRepository(td / "t.db")
    snap_repo = SnapshotRepository(td / "t.db")
    svc = SnapshotService(repo, snap_repo, hist)
    r = _rascunho_duas_propostas()
    repo.salvar_rascunho(r)
    g = svc.gerar_snapshot_candidato("demo-12")
    svc.aprovar_snapshot(
        "demo-12",
        g.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Demo", confirmo_conteudo=True),
    )
    snap = svc.obter_snapshot(g.snapshot_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=args.propostas)

    print(f"MATRIZ RECONCILIACAO (centavos) — demo-12, propostas {args.propostas}")
    print("-" * 95)
    for sec in vm.secoes_regime:
        print(f"[{sec.regime_rotulo}]")
        for plano in sec.planos_atuais:
            print(f"  Plano: {plano.plano_nome}")
            for fx in plano.faixas:
                cols = {c.opcao_id: c.subtotal_centavos for c in fx.propostas}
                props = " | ".join(f"{op} {cols.get(op)}" for op in args.propostas)
                print(
                    f"    Faixa {fx.faixa:02d} | vidas {fx.qtd_total:2d} | "
                    f"vigente {fx.atual_vigente_total_centavos} | "
                    f"reajustado {fx.atual_reajustado_total_centavos} | {props}"
                )
    print("-" * 95)
    props_totais = " | ".join(
        f"{op} {vm.totais_gerais.propostas.get(op)}" for op in args.propostas
    )
    print(f"Totais | atual {vm.totais_gerais.atual_centavos} | {props_totais}")


if __name__ == "__main__":
    main()
