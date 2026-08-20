"""Comparativo exibe valores em seguro novo e mantém paridade com a apresentação."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    EscolhasEstudo,
    OrigemValorRascunho,
    ParentescoRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_app.services.snapshot import SnapshotService
from newport_motor.engine import calcular

_BRONZE = [17938, 24360, 28595, 28595, 28595, 31941, 44111, 52669, 75737, 107396]
_PRATA = [28290, 33100, 40382, 48458, 50881, 55969, 69962, 76958, 96198, 168347]


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL, extrator_versao="manual", confirmado=True
    )


def _tabela(valores: list[int]) -> list[TabelaFaixaRascunho]:
    return [
        TabelaFaixaRascunho(
            faixa=i,
            valor_centavos=v,
            quantidade_cotada=0,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            proveniencia=_prov(),
        )
        for i, v in enumerate(valores)
    ]


def _vidas_ivtec() -> list[VidaRascunho]:
    specs: list[tuple[date, ParentescoRascunho]] = []
    for y in (2012, 2011, 2010, 2008):
        specs.append((date(y, 6, 15), ParentescoRascunho.FILHO))
    for y in (2005, 2003):
        specs.append((date(y, 6, 15), ParentescoRascunho.TITULAR))
    for y in (2002, 2001, 2000, 1998):
        specs.append((date(y, 6, 15), ParentescoRascunho.TITULAR))
    specs.append((date(1986, 6, 15), ParentescoRascunho.TITULAR))
    specs.append((date(1960, 6, 15), ParentescoRascunho.TITULAR))
    return [
        VidaRascunho(
            id=f"v{i}",
            nome=f"Beneficiário {i + 1}",
            nascimento=nasc,
            incluida=True,
            parentesco=parentesco,
            subgrupo_atual_id=None,
        )
        for i, (nasc, parentesco) in enumerate(specs)
    ]


def _rascunho_ivtec_novo():
    base = rascunho_demo_12_vidas()
    op_bronze = base.opcoes_proposta[0].model_copy(
        update={
            "id": "op-bronze",
            "operadora": "Amil",
            "plano_nome": "BRONZE SP MAIS COPART TP",
            "tipo_fiscal": "operadora",
            "tabela": _tabela(_BRONZE),
        }
    )
    op_prata = base.opcoes_proposta[0].model_copy(
        update={
            "id": "op-prata",
            "operadora": "Amil",
            "plano_nome": "PRATA QC COPART TP",
            "tipo_fiscal": "operadora",
            "tabela": _tabela(_PRATA),
        }
    )
    rascunho = base.model_copy(
        update={
            "id": "ivtec-cmp-novo",
            "formato": "novo",
            "titulo": "IVTEC — comparativo seguro novo",
            "vidas": _vidas_ivtec(),
            "subgrupos_atuais": [],
            "opcoes_proposta": [op_bronze, op_prata],
            "cenarios": [],
            "escolhas": EscolhasEstudo(
                data_referencia_idade=date(2026, 6, 30),
                baseline_escolhido=CampoConfirmavelBaseline(),
                precedencia_atual_vida=CampoConfirmavelPrecedencia(),
            ),
        }
    )
    sincronizar_cenarios(rascunho)
    return rascunho


def _calcular_comparativo(rascunho):
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel and compilado.compilado is not None
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    assert not motor.tem_bloqueio
    return montar_comparativo(rascunho, motor_result=motor)


def _aprovar(tmp_path: Path, rascunho):
    db = tmp_path / "cmp.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Ana",
            confirmo_conteudo=True,
            auto_aprovacao=False,
        ),
    )
    return snap_svc.obter_snapshot(g.snapshot_id)


def test_ivtec_seguro_novo_comparativo_exibe_totais_e_faixas():
    cmp = _calcular_comparativo(_rascunho_ivtec_novo())
    assert cmp.formato == "novo"
    assert cmp.planos_atuais == []
    assert cmp.calculo_realizado
    assert cmp.beneficiarios_calculados == 12

    por_id = {p.opcao_id: p for p in cmp.propostas}
    bronze = por_id["op-bronze"]
    prata = por_id["op-prata"]
    assert bronze.numerico is not None
    assert prata.numerico is not None
    assert bronze.numerico.proposta_mensal_centavos == 374_189
    assert prata.numerico.proposta_mensal_centavos == 565_204
    assert bronze.totais is not None
    assert bronze.totais.proposta_mensal_reais == "R$ 3.741,89"
    assert prata.totais is not None
    assert prata.totais.proposta_mensal_reais == "R$ 5.652,04"
    assert bronze.totais.atual_mensal_reais is None
    assert bronze.numerico.atual_mensal_centavos is None

    faixas = {f.faixa: f for f in cmp.faixas_estudo}
    assert set(faixas) == {0, 1, 2, 5, 9}
    assert faixas[0].quantidade == 4
    assert faixas[1].quantidade == 2
    assert faixas[2].quantidade == 4
    assert faixas[5].quantidade == 1
    assert faixas[9].quantidade == 1
    col_bronze = next(c for c in faixas[0].propostas if c.opcao_id == "op-bronze")
    assert col_bronze.subtotal_centavos == 4 * 17_938
    assert faixas[0].vigente_total_centavos is None


def test_paridade_totais_comparativo_e_apresentacao(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    cmp = _calcular_comparativo(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=["op-bronze", "op-prata"],
    )
    for p in cmp.propostas:
        assert p.numerico is not None
        assert (
            p.numerico.proposta_mensal_centavos
            == vm.totais_gerais.propostas[p.opcao_id]
        )


def test_paridade_renovacao_um_subgrupo(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    cmp = _calcular_comparativo(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in cmp.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    for p in cmp.propostas:
        if not p.calculo_realizado or p.numerico is None:
            continue
        assert (
            p.numerico.proposta_mensal_centavos
            == vm.totais_gerais.propostas[p.opcao_id]
        )


def test_renovacao_um_subgrupo_inalterado():
    rascunho = rascunho_demo_12_vidas()
    cmp = _calcular_comparativo(rascunho)
    assert cmp.formato == "renovacao"
    assert cmp.planos_atuais
    p0 = cmp.propostas[0]
    assert p0.numerico is not None
    assert p0.numerico.proposta_mensal_centavos is not None
    assert p0.numerico.atual_mensal_centavos is not None
    assert p0.totais is not None
    assert p0.totais.atual_mensal_reais is not None


def test_renovacao_dois_subgrupos_totais_proprios(tmp_path: Path):
    base = rascunho_demo_12_vidas()
    vidas = []
    for i in range(41):
        v = deepcopy(base.vidas[i % len(base.vidas)])
        v.id = f"v{i}"
        v.nome = f"Beneficiário {i + 1}"
        v.subgrupo_atual_id = "sg-1" if i < 20 else "sg-2"
        vidas.append(v)
    sg2 = deepcopy(base.subgrupos_atuais[0])
    sg2.id = "sg-2"
    sg2.plano_nome = "Plano atual B"
    op2 = deepcopy(base.opcoes_proposta[0])
    op2.id = "op-2"
    op2.plano_nome = "Proposta B"
    op2.tabela = [
        f.model_copy(update={"valor_centavos": f.valor_centavos + 20_000})
        for f in op2.tabela
    ]
    rascunho = base.model_copy(
        update={
            "id": "anistia-cmp",
            "vidas": vidas,
            "subgrupos_atuais": [base.subgrupos_atuais[0], sg2],
            "opcoes_proposta": [base.opcoes_proposta[0], op2],
            "cenarios": [],
        }
    )
    sincronizar_cenarios(rascunho)
    cmp = _calcular_comparativo(rascunho)
    assert cmp.formato == "renovacao"
    assert len(cmp.planos_atuais) == 2
    ids = {p.subgrupo_id for p in cmp.planos_atuais}
    assert ids == {base.subgrupos_atuais[0].id, "sg-2"}
    mensais = [p.mensal_centavos for p in cmp.planos_atuais]
    assert all(v is not None for v in mensais)
    consolidado = sum(mensais)
    if mensais[0] != mensais[1]:
        assert all(p.mensal_centavos != consolidado for p in cmp.planos_atuais)
    por_id = {p.opcao_id: p for p in cmp.propostas}
    t1 = por_id["op-1"].numerico.proposta_mensal_centavos
    t2 = por_id["op-2"].numerico.proposta_mensal_centavos
    assert t1 is not None and t2 is not None and t1 != t2

    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"]
    )
    assert t1 == vm.totais_gerais.propostas["op-1"]
    assert t2 == vm.totais_gerais.propostas["op-2"]


def test_calculo_service_seguro_novo_retorna_valores(tmp_path: Path):
    db = tmp_path / "svc.db"
    repo = SQLiteStudyRepository(db)
    svc = CalculoService(repo)
    rascunho = _rascunho_ivtec_novo()
    repo.salvar_rascunho(rascunho)
    resp = svc.calcular(rascunho.id)
    assert resp.calculo_realizado
    assert {p.opcao_id: p.numerico.proposta_mensal_centavos for p in resp.propostas} == {
        "op-bronze": 374_189,
        "op-prata": 565_204,
    }
