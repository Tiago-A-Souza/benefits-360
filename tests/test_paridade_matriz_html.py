"""Paridade matriz comparativa × PresentationViewModel e regressão de planos vigentes."""

from __future__ import annotations

import json
from collections import defaultdict
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    ComponenteFinanceiroRascunho,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO, default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService
from newport_motor.engine import calcular
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo

_GABARITO = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "gabarito_dois_planos.json"
)
_ANISTIA_36 = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "resumo_plano_atual"
    / "anistia_sintetica_36.json"
)


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL, extrator_versao="manual", confirmado=True
    )


def _tabela(valores: dict[int, int], *, quantidade: int | None = 0) -> list[TabelaFaixaRascunho]:
    return [
        TabelaFaixaRascunho(
            faixa=fx,
            valor_centavos=valores.get(fx, 80_000),
            quantidade_cotada=quantidade,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            proveniencia=_prov(),
        )
        for fx in range(10)
    ]


def _nascimento_faixa(faixa: int, data_ref: date) -> date:
    idade = {0: 10, 1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45, 7: 50, 8: 55, 9: 60}[faixa]
    return date(data_ref.year - idade, 6, 15)


def _calcular_matriz(rascunho, *, resolver_b04: bool = False):
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel and compilado.compilado is not None, compilado.erros
    estudo = compilado.compilado.estudo_input
    if resolver_b04:
        estudo = estudo.model_copy(
            update={
                "vidas": [
                    v.model_copy(update={"idade_valor_resolvido": True}) for v in estudo.vidas
                ]
            }
        )
    motor = calcular(estudo, compilado.compilado.effective_policy)
    assert not motor.tem_bloqueio
    return montar_comparativo(rascunho, motor_result=motor), motor


def _aprovar(tmp_path: Path, rascunho):
    db = tmp_path / f"paridade-{rascunho.id}.db"
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


def _planos_vm_por_subgrupo(vm) -> dict[str, dict]:
    acc: dict[str, dict] = {}
    for secao in vm.secoes_regime:
        for pl in secao.planos_atuais:
            if pl.subgrupo_id == "vidas-incluidas":
                continue
            slot = acc.setdefault(
                pl.subgrupo_id,
                {
                    "plano_nome": pl.plano_nome,
                    "vigente": None,
                    "reajustado": None,
                    "propostas": defaultdict(int),
                },
            )
            if slot["vigente"] is None:
                slot["vigente"] = pl.subtotal_vigente_centavos or 0
                slot["reajustado"] = pl.subtotal_reajustado_centavos or 0
            for fx in pl.faixas:
                for col in fx.propostas:
                    slot["propostas"][col.opcao_id] += col.subtotal_centavos or 0
    return acc


def _rotulos_vm(vm) -> dict[str, str]:
    rotulos: dict[str, str] = {}
    for secao in vm.secoes_regime:
        for prop in secao.propostas:
            rotulos.setdefault(prop.opcao_id, prop.plano_nome)
    return rotulos


def assert_paridade_rotulos(matriz, vm) -> None:
    rotulos_vm = _rotulos_vm(vm)
    vistos: list[str] = []
    for prop in matriz.propostas:
        assert prop.plano_nome == rotulos_vm[prop.opcao_id]
        vistos.append(prop.plano_nome)
    assert len(vistos) == len(set(vistos))


def _datas_vm(vm) -> dict[str, str | None]:
    vals: dict[str, str | None] = {}
    for secao in vm.secoes_regime:
        for prop in secao.propostas:
            vals.setdefault(prop.opcao_id, prop.validade)
    return vals


def assert_paridade_datas(matriz, vm) -> None:
    datas_vm = _datas_vm(vm)
    for prop in matriz.propostas:
        assert prop.validade_oficial == datas_vm.get(prop.opcao_id)
        if prop.validade_oficial:
            assert "/" in prop.validade_oficial
            assert not (
                len(prop.validade_oficial) >= 10
                and prop.validade_oficial[4] == "-"
                and prop.validade_oficial[7] == "-"
            )
    if matriz.validade_proposta:
        assert "/" in matriz.validade_proposta
        assert not matriz.validade_proposta.startswith("2026-")


def assert_paridade_planos(matriz, vm) -> None:
    vm_planos = _planos_vm_por_subgrupo(vm)
    ids_matriz = {p.subgrupo_id for p in matriz.planos_atuais}
    assert ids_matriz == set(vm_planos)
    for pl in matriz.planos_atuais:
        slot = vm_planos[pl.subgrupo_id]
        assert pl.plano_nome == slot["plano_nome"]
        assert (pl.vigente_centavos or 0) == slot["vigente"]
        assert (pl.reajustado_centavos or 0) == slot["reajustado"]
        for prop in matriz.propostas:
            rec = next((s for s in prop.subgrupos if s.subgrupo_id == pl.subgrupo_id), None)
            assert rec is not None
            assert (rec.proposta_centavos or 0) == slot["propostas"][prop.opcao_id]


def assert_coerencia_interna(matriz) -> None:
    if not matriz.planos_atuais:
        return
    vigentes = [p.vigente_centavos or 0 for p in matriz.planos_atuais]
    reajustados = [p.reajustado_centavos or 0 for p in matriz.planos_atuais]
    assert sum(p.vigente_centavos or 0 for p in matriz.planos_atuais) == sum(vigentes)
    assert sum(p.reajustado_centavos or 0 for p in matriz.planos_atuais) == sum(reajustados)
    propostas_ok = [p for p in matriz.propostas if p.calculo_realizado and p.numerico]
    if propostas_ok and propostas_ok[0].numerico.atual_mensal_centavos is not None:
        soma_mensal = sum(p.mensal_centavos or 0 for p in matriz.planos_atuais)
        assert soma_mensal == propostas_ok[0].numerico.atual_mensal_centavos
    for prop in propostas_ok:
        soma_sg = sum(s.proposta_centavos or 0 for s in prop.subgrupos)
        assert soma_sg == (prop.numerico.proposta_mensal_centavos or 0)
    assert sum(p.vidas for p in matriz.planos_atuais) == matriz.beneficiarios_calculados


def _vidas_matriz_faixa(matriz, subgrupo_id: str, faixa: int):
    for prop in matriz.propostas:
        if not prop.calculo_realizado:
            continue
        return [
            v
            for sec in prop.secoes
            for v in sec.vidas
            if v.subgrupo_id == subgrupo_id and v.faixa == faixa
        ]
    return []


def _faixa_vm(vm, subgrupo_id: str, faixa: int):
    for secao in vm.secoes_regime:
        for pl in secao.planos_atuais:
            if pl.subgrupo_id != subgrupo_id:
                continue
            found = next((fx for fx in pl.faixas if fx.faixa == faixa), None)
            if found is not None:
                return found
    return None


def assert_gabarito_propostas(matriz, vm, gab) -> None:
    vm_planos = _planos_vm_por_subgrupo(vm)
    mapa_sg = {p["chave"]: p["subgrupo_id"] for p in gab["planos"]}
    for spec in gab["propostas"]:
        prop = next(p for p in matriz.propostas if p.opcao_id == spec["opcao_id"])
        rec_a = next(s for s in prop.subgrupos if s.subgrupo_id == mapa_sg["plano_a"])
        rec_b = next(s for s in prop.subgrupos if s.subgrupo_id == mapa_sg["plano_b"])
        assert rec_a.proposta_centavos == spec["plano_a_centavos"], spec["chave"]
        assert rec_b.proposta_centavos == spec["plano_b_centavos"], spec["chave"]
        soma = (rec_a.proposta_centavos or 0) + (rec_b.proposta_centavos or 0)
        assert soma == spec["consolidado_centavos"]
        assert prop.numerico is not None
        assert prop.numerico.proposta_mensal_centavos == spec["consolidado_centavos"]
        assert vm_planos[mapa_sg["plano_a"]]["propostas"][spec["opcao_id"]] == spec[
            "plano_a_centavos"
        ]
        assert vm_planos[mapa_sg["plano_b"]]["propostas"][spec["opcao_id"]] == spec[
            "plano_b_centavos"
        ]
        assert vm.totais_gerais.propostas[spec["opcao_id"]] == spec["consolidado_centavos"]


def _rascunho_n_subgrupos(n: int, *, extra_opcoes: int = 0):
    base = rascunho_demo_12_vidas()
    sgs = []
    for i in range(n):
        sg = deepcopy(base.subgrupos_atuais[0])
        sg.id = f"sg-{i + 1}"
        sg.plano_nome = f"Plano vigente {i + 1}"
        sg.operadora = f"Operadora {i + 1}"
        sgs.append(sg)
    vidas = deepcopy(base.vidas)
    for i, v in enumerate(vidas):
        v.subgrupo_atual_id = sgs[i % n].id
    opcoes = [deepcopy(base.opcoes_proposta[0])]
    for i in range(extra_opcoes):
        op = deepcopy(base.opcoes_proposta[0])
        op.id = f"op-extra-{i + 1}"
        op.plano_nome = f"Proposta extra {i + 1}"
        op.tabela = [
            f.model_copy(update={"valor_centavos": f.valor_centavos + (i + 1) * 15_000})
            for f in op.tabela
        ]
        opcoes.append(op)
    rascunho = base.model_copy(
        update={
            "id": f"paridade-{n}sg-x{extra_opcoes}",
            "vidas": vidas,
            "subgrupos_atuais": sgs,
            "opcoes_proposta": opcoes,
            "cenarios": [],
        }
    )
    sincronizar_cenarios(rascunho)
    return rascunho


def _rascunho_dois_planos_gabarito(*, reajuste_bps: int) -> RascunhoEstudo:
    payload_36 = json.loads(_ANISTIA_36.read_text(encoding="utf-8"))
    data_ref = date.fromisoformat(payload_36["data_referencia"])
    vidas: list[VidaRascunho] = []
    for i, spec in enumerate(payload_36["vidas"]):
        vidas.append(
            VidaRascunho(
                id=f"va{i}",
                nome=f"Beneficiário A {i + 1}",
                nascimento=date.fromisoformat(spec["nascimento"]),
                incluida=True,
                subgrupo_atual_id="sg-a",
                valor_fatura=ComponenteFinanceiroRascunho(
                    centavos=spec["centavos"],
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    proveniencia=_prov(),
                ),
            )
        )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    faixas_b = [
        fx
        for fx, qtd in enumerate(gab["vidas_por_faixa"]["sg-b"])
        for _ in range(qtd)
    ]
    for i, (fx, cent) in enumerate(
        zip(faixas_b, [200_000, 200_000, 200_000, 200_000, 904_692], strict=True)
    ):
        vidas.append(
            VidaRascunho(
                id=f"vb{i}",
                nome=f"Beneficiário B {i + 1}",
                nascimento=_nascimento_faixa(fx, data_ref),
                incluida=True,
                subgrupo_atual_id="sg-b",
                valor_fatura=ComponenteFinanceiroRascunho(
                    centavos=cent,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    proveniencia=_prov(),
                ),
            )
        )
    prata_fx = {i: v for i, v in enumerate(gab["unitarias_proposta_centavos"]["prata"])}
    ouro_fx = {i: v for i, v in enumerate(gab["unitarias_proposta_centavos"]["ouro"])}
    sg_a = SubgrupoAtualRascunho(
        id="sg-a",
        operadora="Operadora A",
        plano_nome="Plano vigente A",
        regime_copart_id="regime-sem",
        tipo_fiscal="operadora",
        acomodacao="Apartamento",
        reajuste_bps=reajuste_bps,
        fatura_price_basis=PriceBasisRascunho.EXCLUI_IOF,
        tabela_atual=[],
    )
    sg_b = sg_a.model_copy(
        update={
            "id": "sg-b",
            "operadora": "Operadora B",
            "plano_nome": "Plano vigente B",
        }
    )
    op_prata = OpcaoPropostaRascunho(
        id="op-prata",
        operadora="Operadora P",
        plano_nome="Proposta prata",
        regime_copart_id="regime-sem",
        tipo_fiscal="operadora",
        tabela=_tabela(prata_fx),
        validade_oficial=date(2026, 7, 2),
    )
    op_ouro = OpcaoPropostaRascunho(
        id="op-ouro",
        operadora="Operadora P",
        plano_nome="Proposta ouro",
        regime_copart_id="regime-percentual",
        tipo_fiscal="operadora",
        tabela=_tabela(ouro_fx),
        validade_oficial=date(2026, 4, 10),
    )
    rascunho = RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id=f"gabarito-dois-planos-{reajuste_bps}",
        titulo="Gabarito dois planos vigentes",
        formato="renovacao",
        vidas=vidas,
        subgrupos_atuais=[sg_a, sg_b],
        opcoes_proposta=[op_prata, op_ouro],
        regimes_copart=[
            RegimeCopartRascunho(id="regime-sem", tipo="sem"),
            RegimeCopartRascunho(id="regime-percentual", tipo="percentual", percentual=30),
        ],
        cenarios=[],
        escolhas=EscolhasEstudo(
            data_referencia_idade=data_ref,
            baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
            precedencia_atual_vida=CampoConfirmavelPrecedencia(
                valor="valor_fatura", confirmado=True
            ),
        ),
    )
    sincronizar_cenarios(rascunho)
    return rascunho


def test_paridade_renovacao_um_subgrupo(tmp_path: Path):
    rascunho = _rascunho_n_subgrupos(1)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_paridade_planos(matriz, vm)
    assert_paridade_rotulos(matriz, vm)
    assert_paridade_datas(matriz, vm)
    assert_coerencia_interna(matriz)


def test_paridade_renovacao_dois_subgrupos(tmp_path: Path):
    rascunho = _rascunho_n_subgrupos(2)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_paridade_planos(matriz, vm)
    assert_paridade_rotulos(matriz, vm)
    assert_paridade_datas(matriz, vm)
    assert_coerencia_interna(matriz)
    assert len(matriz.planos_atuais) == 2


def test_paridade_renovacao_tres_subgrupos(tmp_path: Path):
    rascunho = _rascunho_n_subgrupos(3)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_paridade_planos(matriz, vm)
    assert_paridade_rotulos(matriz, vm)
    assert_paridade_datas(matriz, vm)
    assert_coerencia_interna(matriz)
    assert len(matriz.planos_atuais) == 3


def test_paridade_seguro_novo(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert matriz.planos_atuais == []
    assert _planos_vm_por_subgrupo(vm) == {}
    for p in matriz.propostas:
        assert p.numerico is not None
        assert p.numerico.proposta_mensal_centavos == vm.totais_gerais.propostas[p.opcao_id]
        assert p.subgrupos == []
    assert_paridade_rotulos(matriz, vm)
    assert_paridade_datas(matriz, vm)


def test_regressao_planos_atuais_nao_carregam_consolidado():
    rascunho = _rascunho_n_subgrupos(2, extra_opcoes=1)
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.planos_atuais) == 2
    mensais = [p.mensal_centavos for p in matriz.planos_atuais]
    assert all(v is not None for v in mensais)
    consolidado = sum(mensais)
    assert mensais[0] != mensais[1]
    assert all(p.mensal_centavos != consolidado for p in matriz.planos_atuais)
    for p in matriz.planos_atuais:
        assert p.mensal_centavos == p.reajustado_centavos
    assert_coerencia_interna(matriz)


def test_planos_atuais_independente_da_ordem_das_propostas():
    r1 = _rascunho_n_subgrupos(2, extra_opcoes=1)
    m1, _ = _calcular_matriz(r1)
    r2 = r1.model_copy(deep=True)
    r2.opcoes_proposta = list(reversed(r2.opcoes_proposta))
    m2, _ = _calcular_matriz(r2)
    v1 = {
        p.subgrupo_id: (p.vigente_centavos, p.reajustado_centavos, p.mensal_centavos)
        for p in m1.planos_atuais
    }
    v2 = {
        p.subgrupo_id: (p.vigente_centavos, p.reajustado_centavos, p.mensal_centavos)
        for p in m2.planos_atuais
    }
    assert v1 == v2


def test_planos_atuais_completos_se_primeira_proposta_nao_calcula():
    rascunho = _rascunho_n_subgrupos(2, extra_opcoes=1)
    matriz_ok, motor = _calcular_matriz(rascunho)
    primeiro = rascunho.cenarios[0].id
    motor_parcial = motor.model_copy(
        update={"cenarios": [c for c in motor.cenarios if c.cenario_id != primeiro]}
    )
    matriz = montar_comparativo(rascunho, motor_result=motor_parcial)
    assert len(matriz.planos_atuais) == 2
    ref = {p.subgrupo_id: p.mensal_centavos for p in matriz_ok.planos_atuais}
    got = {p.subgrupo_id: p.mensal_centavos for p in matriz.planos_atuais}
    assert got == ref
    assert any(not p.calculo_realizado for p in matriz.propostas)


def test_gabarito_proposta_por_plano_vigente(tmp_path: Path):
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_gabarito_propostas(matriz, vm, gab)
    assert_paridade_planos(matriz, vm)
    assert_coerencia_interna(matriz)
    for spec in gab["faixas_heterogeneas_reajuste_1200"]:
        vidas = _vidas_matriz_faixa(matriz, spec["subgrupo_id"], spec["faixa"])
        soma_vidas = sum(v.reajustado_centavos or 0 for v in vidas)
        assert soma_vidas == spec["total_reajustado_centavos"]
        fx_vm = _faixa_vm(vm, spec["subgrupo_id"], spec["faixa"])
        assert fx_vm is not None
        assert fx_vm.atual_reajustado_total_centavos == spec["total_reajustado_centavos"]
        assert soma_vidas == fx_vm.atual_reajustado_total_centavos


@pytest.mark.parametrize("reajuste_bps", [1000, 1200])
def test_gabarito_dois_planos_vigente_e_reajuste(reajuste_bps: int):
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=reajuste_bps)
    matriz, _ = _calcular_matriz(rascunho)
    por_id = {p.subgrupo_id: p for p in matriz.planos_atuais}
    assert por_id["sg-a"].vidas == gab["planos"][0]["vidas"]
    assert por_id["sg-b"].vidas == gab["planos"][1]["vidas"]
    assert por_id["sg-a"].vigente_centavos == gab["planos"][0]["vigente_centavos"]
    assert por_id["sg-b"].vigente_centavos == gab["planos"][1]["vigente_centavos"]
    assert sum(p.vigente_centavos or 0 for p in matriz.planos_atuais) == gab[
        "consolidado_vigente_centavos"
    ]
    reaj = gab["reajuste"][str(reajuste_bps)]
    assert por_id["sg-a"].reajustado_centavos == reaj["plano_a_centavos"]
    assert por_id["sg-b"].reajustado_centavos == reaj["plano_b_centavos"]
    assert sum(p.reajustado_centavos or 0 for p in matriz.planos_atuais) == reaj[
        "consolidado_centavos"
    ]
    assert_coerencia_interna(matriz)
    por_op = {p.opcao_id: p.validade_oficial for p in matriz.propostas}
    assert por_op["op-prata"] == "02/07/2026"
    assert por_op["op-ouro"] == "10/04/2026"
    assert matriz.validade_proposta == "02/07/2026"
    gab_prop = {p["opcao_id"]: p for p in gab["propostas"]}
    for prop in matriz.propostas:
        spec = gab_prop[prop.opcao_id]
        rec = {s.subgrupo_id: s.proposta_centavos for s in prop.subgrupos}
        assert rec["sg-a"] == spec["plano_a_centavos"]
        assert rec["sg-b"] == spec["plano_b_centavos"]
        assert (rec["sg-a"] or 0) + (rec["sg-b"] or 0) == spec["consolidado_centavos"]
        assert prop.numerico is not None
        assert prop.numerico.proposta_mensal_centavos == spec["consolidado_centavos"]


def test_rotulos_desambiguados_quando_nome_base_coincide(tmp_path: Path):
    base = rascunho_demo_12_vidas()
    nome = "Executivo R1 Apartamento (Nacional)"
    op_sem = deepcopy(base.opcoes_proposta[0])
    op_sem.id = "op-r1-sem"
    op_sem.plano_nome = nome
    op_sem.regime_copart_id = "regime-sem"
    op_com = deepcopy(base.opcoes_proposta[0])
    op_com.id = "op-r1-copart"
    op_com.plano_nome = nome
    op_com.regime_copart_id = "regime-percentual"
    op_com.tabela = [
        f.model_copy(update={"valor_centavos": f.valor_centavos + 12_000})
        for f in op_com.tabela
    ]
    rascunho = base.model_copy(
        update={
            "id": "rotulos-ambiguos",
            "opcoes_proposta": [op_sem, op_com],
            "regimes_copart": [
                RegimeCopartRascunho(id="regime-sem", tipo="sem"),
                RegimeCopartRascunho(id="regime-percentual", tipo="percentual", percentual=30),
            ],
            "cenarios": [],
        }
    )
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    nomes = [p.plano_nome for p in matriz.propostas]
    assert len(nomes) == len(set(nomes))
    assert any("sem copart" in n for n in nomes)
    assert any("copart 30%" in n for n in nomes)
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_paridade_rotulos(matriz, vm)
    assert_paridade_datas(matriz, vm)


def test_rotulo_unico_nao_ganha_sufixo():
    rascunho = rascunho_demo_12_vidas()
    matriz, _ = _calcular_matriz(rascunho)
    nome = matriz.propostas[0].plano_nome
    assert "(sem copart)" not in nome
    assert not nome.endswith("(1)")

