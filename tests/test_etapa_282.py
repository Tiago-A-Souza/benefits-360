"""Testes ETAPA 2.8.2 — hotfix regimes de coparticipação e dois planos atuais."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
)
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.motor_por_proposta import calcular_propostas_do_snapshot
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from tests.test_etapa_281 import _aprovar, _rascunho_dois_planos, _stack


def _rascunho_regimes_diferentes():
    base = rascunho_demo_12_vidas()
    op_b = base.opcoes_proposta[0].model_copy(
        update={
            "id": "op-2",
            "plano_nome": "Proposta B — copart parcial",
            "regime_copart_id": "regime-parcial",
        }
    )
    return base.model_copy(
        update={
            "opcoes_proposta": [base.opcoes_proposta[0], op_b],
            "regimes_copart": [
                RegimeCopartRascunho(id="regime-sem", tipo="sem"),
                RegimeCopartRascunho(id="regime-parcial", tipo="parcial"),
            ],
        }
    )


@pytest.fixture
def stack(tmp_path: Path):
    return _stack(tmp_path)


def test_regimes_diferentes_secoes_isoladas(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_regimes_diferentes()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"])

    assert len(vm.secoes_regime) == 2
    sec_sem = next(s for s in vm.secoes_regime if s.regime_tipo == "sem")
    sec_parcial = next(s for s in vm.secoes_regime if s.regime_tipo == "parcial")

    assert [p.opcao_id for p in sec_sem.propostas] == ["op-1"]
    assert [p.opcao_id for p in sec_parcial.propostas] == ["op-2"]

    for sec in (sec_sem, sec_parcial):
        plano = sec.planos_atuais[0]
        assert sum(f.qtd_total for f in plano.faixas) == 12
        assert plano.subtotal_reajustado_centavos == sec.totais.atual_centavos

    calc = calcular_propostas_do_snapshot(snap, ["op-1", "op-2"])
    assert sec_sem.totais.propostas["op-1"] == calc["op-1"].total_proposta_centavos
    assert sec_parcial.totais.propostas["op-2"] == calc["op-2"].total_proposta_centavos
    assert "op-2" not in sec_sem.totais.propostas
    assert "op-1" not in sec_parcial.totais.propostas


def test_dois_planos_atuais(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_dois_planos()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1"])

    sec = vm.secoes_regime[0]
    assert len(sec.planos_atuais) == 2
    nomes = {p.plano_nome for p in sec.planos_atuais}
    assert "Plano atual fictício" in nomes
    assert "Plano atual secundário" in nomes

    sg1 = next(p for p in sec.planos_atuais if p.subgrupo_id == "sg-1")
    sg2 = next(p for p in sec.planos_atuais if p.subgrupo_id == "sg-2")
    vidas_sg1 = sum(f.qtd_total for f in sg1.faixas)
    vidas_sg2 = sum(f.qtd_total for f in sg2.faixas)
    assert vidas_sg1 == 6
    assert vidas_sg2 == 6
    assert vidas_sg1 + vidas_sg2 == 12

    soma_subtotais = (sg1.subtotal_reajustado_centavos or 0) + (
        sg2.subtotal_reajustado_centavos or 0
    )
    assert soma_subtotais == vm.totais_gerais.atual_centavos
    assert sec.totais.atual_centavos == vm.totais_gerais.atual_centavos

    calc = calcular_propostas_do_snapshot(snap, ["op-1"])
    assert sec.totais.propostas["op-1"] == calc["op-1"].total_proposta_centavos

    vm_benef = construir_view_model(
        snap, modo="beneficiario", propostas_selecionadas=["op-1"]
    )
    ids = [b.vida_id for b in vm_benef.beneficiarios]
    assert len(ids) == len(set(ids))
    assert len(ids) == 12
    subgrupos = {b.subgrupo_id for b in vm_benef.beneficiarios}
    assert subgrupos == {"sg-1", "sg-2"}
