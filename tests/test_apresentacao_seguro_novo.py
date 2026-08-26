"""Apresentação HTML/VM para seguro novo — faixas, totais distintos, sem plano vigente."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

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
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.motor_por_proposta import (
    _atribuir_proposta_unica,
    calcular_propostas_do_snapshot,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService

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
    """12 vidas nas faixas IVTEC com titular/dependente conforme o estudo entregue."""
    specs: list[tuple[date, ParentescoRascunho]] = []
    # 0-18: 4 dependentes (ref. 2026-06-30)
    for y in (2012, 2011, 2010, 2008):
        specs.append((date(y, 6, 15), ParentescoRascunho.FILHO))
    # 19-23: 2 titulares
    for y in (2005, 2003):
        specs.append((date(y, 6, 15), ParentescoRascunho.TITULAR))
    # 24-28: 4 titulares
    for y in (2002, 2001, 2000, 1998):
        specs.append((date(y, 6, 15), ParentescoRascunho.TITULAR))
    # 39-43: 1 titular
    specs.append((date(1986, 6, 15), ParentescoRascunho.TITULAR))
    # 59+: 1 titular
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
            "id": "ivtec-novo",
            "formato": "novo",
            "titulo": "IVTEC — seguro novo",
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


def _aprovar(tmp_path: Path, rascunho):
    db = tmp_path / "apres.db"
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


def test_atribuir_proposta_unica_atualiza_vidas_em_seguro_novo():
    rascunho = _rascunho_ivtec_novo()
    assert rascunho.cenarios[0].atribuicoes[0].opcao_plano_id == "op-bronze"
    reatrib = _atribuir_proposta_unica(rascunho, "op-prata")
    assert len(reatrib.cenarios) == 1
    assert len(reatrib.cenarios[0].atribuicoes) == 12
    assert all(a.alvo_tipo == "vida" for a in reatrib.cenarios[0].atribuicoes)
    assert all(a.opcao_plano_id == "op-prata" for a in reatrib.cenarios[0].atribuicoes)


def test_ivtec_seguro_novo_faixas_totais_e_html(tmp_path: Path):
    snap = _aprovar(tmp_path, _rascunho_ivtec_novo())
    vm = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=["op-bronze", "op-prata"],
    )
    assert vm.formato == "novo"
    assert len(vm.secoes_regime) == 1
    plano = vm.secoes_regime[0].planos_atuais[0]
    faixas_com_vidas = {fx.faixa: fx for fx in plano.faixas if fx.qtd_total > 0}
    assert set(faixas_com_vidas) == {0, 1, 2, 5, 9}
    assert faixas_com_vidas[0].qtd_total == 4 and faixas_com_vidas[0].qtd_dependentes == 4
    assert faixas_com_vidas[1].qtd_total == 2 and faixas_com_vidas[1].qtd_titulares == 2
    assert faixas_com_vidas[2].qtd_total == 4 and faixas_com_vidas[2].qtd_titulares == 4
    assert faixas_com_vidas[5].qtd_total == 1 and faixas_com_vidas[5].qtd_titulares == 1
    assert faixas_com_vidas[9].qtd_total == 1 and faixas_com_vidas[9].qtd_titulares == 1

    totais = vm.totais_gerais.propostas
    assert totais["op-bronze"] == 374_189
    assert totais["op-prata"] == 565_204
    assert totais["op-bronze"] != totais["op-prata"]
    assert vm.totais_gerais.atual_centavos is None
    assert vm.totais_gerais.baseline_rotulo is None
    # Diffs vs menor proposta — preenchidos no builder a partir do numerico.
    assert vm.totais_gerais.diff_mensal["op-bronze"] == 0
    assert vm.totais_gerais.diff_mensal["op-prata"] == 565_204 - 374_189
    assert vm.totais_gerais.diff_anual["op-bronze"] == 0
    assert vm.totais_gerais.diff_anual["op-prata"] == 12 * (565_204 - 374_189)

    html = render_html(vm)
    assert "Plano atual" not in html
    assert "Referência atual" not in html
    assert "Total atual" not in html
    assert "Diferença mensal" not in html
    assert "Atual vigente" not in html
    assert "Atual reajustado" not in html
    assert "3.741,89" in html
    assert "5.652,04" in html
    assert "Comparativo entre propostas" in html


def test_propriedade_propostas_diferentes_totais_distintos(tmp_path: Path):
    snap = _aprovar(tmp_path, _rascunho_ivtec_novo())
    calcs = calcular_propostas_do_snapshot(snap, ["op-bronze", "op-prata"])
    assert calcs["op-bronze"].total_proposta_centavos != calcs["op-prata"].total_proposta_centavos


def test_renovacao_um_subgrupo_sem_regressao(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1"])
    assert vm.formato == "renovacao"
    assert vm.totais_gerais.atual_centavos is not None
    assert vm.totais_gerais.baseline_rotulo
    html = render_html(vm)
    assert "Plano atual" in html
    assert "Referência atual" in html


def test_renovacao_dois_subgrupos_totais_proprios(tmp_path: Path):
    base = rascunho_demo_12_vidas()
    # Estende para 41 vidas e 2 subgrupos (padrão Anistia simplificado)
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
            "id": "anistia-apres",
            "vidas": vidas,
            "subgrupos_atuais": [base.subgrupos_atuais[0], sg2],
            "opcoes_proposta": [base.opcoes_proposta[0], op2],
            "cenarios": [],
        }
    )
    sincronizar_cenarios(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"]
    )
    assert len(vm.secoes_regime[0].planos_atuais) == 2
    t1 = vm.totais_gerais.propostas["op-1"]
    t2 = vm.totais_gerais.propostas["op-2"]
    assert t1 is not None and t2 is not None and t1 != t2
    html = render_html(vm)
    assert "Plano atual" in html
    assert "Diferença mensal" in html
