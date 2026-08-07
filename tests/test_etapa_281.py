"""Testes ETAPA 2.8.1 — correções consolidadas."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    ComponenteFinanceiroRascunho,
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.models.historico import ConfirmarVinculoRequest, RegistrarPlanoContratadoRequest, VincularEstudoRequest
from newport_app.models.snapshot import AprovarSnapshotRequest, GerarApresentacaoRequest
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.motor_por_proposta import calcular_propostas_do_snapshot
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.snapshot import AprovacaoInvalidaError, SnapshotService
from newport_app.snapshot.hashing import extrair_payload_canonico, hash_snapshot_canonico


def _stack(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    apres = ApresentacaoService(snap_svc, snap_repo, tmp_path / "entregaveis")
    return repo, historico, snap_repo, snap_svc, apres


def _aprovar(repo, snap_svc, rascunho, *, auto=False):
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Ana",
            confirmo_conteudo=True,
            auto_aprovacao=auto,
            justificativa="Justificativa teste" if auto else None,
        ),
    )
    return g.snapshot_id


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


def _rascunho_dois_planos():
    base = rascunho_demo_12_vidas()
    sg2 = SubgrupoAtualRascunho(
        id="sg-2",
        operadora="Operadora Demo 2",
        plano_nome="Plano atual secundário",
        regime_copart_id="regime-sem",
        tipo_fiscal="seguradora",
        reajuste_bps=1198,
        fatura_price_basis=base.subgrupos_atuais[0].fatura_price_basis,
        tabela_atual=base.subgrupos_atuais[0].tabela_atual,
    )
    vidas = []
    for i, v in enumerate(base.vidas):
        sub = "sg-2" if i >= 6 else "sg-1"
        vidas.append(v.model_copy(update={"subgrupo_atual_id": sub}))
    cenario = CenarioRascunho(
        id="c1",
        rotulo="Cenário principal",
        atribuicoes=[
            AtribuicaoRascunho(id="a1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id="op-1"),
            AtribuicaoRascunho(id="a2", alvo_tipo="subgrupo", alvo_id="sg-2", opcao_plano_id="op-1"),
        ],
    )
    return base.model_copy(
        update={"vidas": vidas, "subgrupos_atuais": [base.subgrupos_atuais[0], sg2], "cenarios": [cenario]}
    )


def _rascunho_vigente_diferente_reajustado():
    base = rascunho_demo_12_vidas()
    escolhas = base.escolhas.model_copy(
        update={"baseline_escolhido": base.escolhas.baseline_escolhido.model_copy(update={"valor": "vigente"})}
    )
    sg = base.subgrupos_atuais[0].model_copy(update={"reajuste_bps": 2500})
    return base.model_copy(update={"escolhas": escolhas, "subgrupos_atuais": [sg]})


@pytest.fixture
def stack(tmp_path):
    return _stack(tmp_path)


def test_hash_deterministico_sem_timestamp(stack):
    repo, _, _, snap_svc, _ = stack
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)
    g1 = snap_svc.gerar_snapshot_candidato("demo-12")
    g2 = snap_svc.gerar_snapshot_candidato("demo-12")
    s1 = snap_svc.obter_snapshot(g1.snapshot_id)
    s2 = snap_svc.obter_snapshot(g2.snapshot_id)
    h1 = hash_snapshot_canonico(extrair_payload_canonico(s1.payload))
    h2 = hash_snapshot_canonico(extrair_payload_canonico(s2.payload))
    assert h1 == h2
    assert "gerado_em" in s1.payload
    assert "gerado_em" in s2.payload
    assert s1.payload["gerado_em"] != s2.payload["gerado_em"]


def test_auto_aprovacao_explicita(stack):
    repo, _, snap_repo, snap_svc, _ = stack
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)
    g = snap_svc.gerar_snapshot_candidato("demo-12")
    with pytest.raises(AprovacaoInvalidaError):
        snap_svc.aprovar_snapshot(
            "demo-12",
            g.snapshot_id,
            AprovarSnapshotRequest(
                revisor_nome="Ana",
                confirmo_conteudo=True,
                auto_aprovacao=True,
            ),
        )
    snap_svc.aprovar_snapshot(
        "demo-12",
        g.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Ana",
            confirmo_conteudo=True,
            auto_aprovacao=True,
            justificativa="Revisão solo piloto",
        ),
    )
    aprov = snap_repo.obter_aprovacao(g.snapshot_id)
    assert aprov is not None
    assert aprov.auto_aprovacao is True
    assert aprov.revisor_nome == "Ana"


def test_dez_faixas_sempre_presentes(stack):
    repo, _, _, snap_svc, _ = stack
    r = rascunho_demo_12_vidas()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1"])
    for sec in vm.secoes_regime:
        for plano in sec.planos_atuais:
            assert len(plano.faixas) == 10


def test_soma_duas_vidas_mesmo_valor(stack):
    repo, _, _, snap_svc, _ = stack
    base = rascunho_demo_12_vidas()
    v = base.vidas[0]
    r = base.model_copy(
        update={
            "vidas": [
                v.model_copy(update={"id": "v-a"}),
                v.model_copy(update={"id": "v-b", "nome": "Beneficiário fictício 2"}),
            ]
        }
    )
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1"])
    fx = vm.secoes_regime[0].planos_atuais[0].faixas[v.id if False else 0]
    # encontrar faixa com 2 vidas
    faixa_com_2 = next(f for f in vm.secoes_regime[0].planos_atuais[0].faixas if f.qtd_total == 2)
    assert faixa_com_2.atual_vigente_total_centavos is not None
    if faixa_com_2.atual_vigente_unitario_centavos:
        assert (
            faixa_com_2.atual_vigente_total_centavos
            == faixa_com_2.atual_vigente_unitario_centavos * 2
        )


def test_duas_vidas_valores_diferentes_mesma_faixa(stack):
    from newport_app.agregacao_faixa import agregar_valores_faixa

    unit, total, obs = agregar_valores_faixa([80_000, 95_000])
    assert unit is None
    assert total == 175_000
    assert obs is not None

    repo, _, _, snap_svc, _ = stack
    base = rascunho_demo_12_vidas()
    vidas = base.vidas[:2]
    r = base.model_copy(update={"vidas": vidas})
    snap_id = _aprovar(repo, snap_svc, r)
    vm = construir_view_model(
        snap_svc.obter_snapshot(snap_id), modo="faixas", propostas_selecionadas=["op-1"]
    )
    faixa_com_vidas = next(
        f for f in vm.secoes_regime[0].planos_atuais[0].faixas if f.qtd_total == 2
    )
    assert faixa_com_vidas.atual_vigente_total_centavos is not None


def test_duas_propostas_valores_diferentes(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_duas_propostas()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    calc = calcular_propostas_do_snapshot(snap, ["op-1", "op-2"])
    assert calc["op-1"].total_proposta_centavos != calc["op-2"].total_proposta_centavos
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"])
    sec = vm.secoes_regime[0]
    assert sec.totais.propostas["op-1"] != sec.totais.propostas["op-2"]
    fx = sec.planos_atuais[0].faixas[0]
    cols = {c.opcao_id: c.subtotal_centavos for c in fx.propostas if c.quantidade > 0}
    if "op-1" in cols and "op-2" in cols:
        assert cols["op-1"] != cols["op-2"]


def test_modo_beneficiario_sem_duplicacao(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_duas_propostas()
    snap_id = _aprovar(repo, snap_svc, r)
    vm = construir_view_model(
        snap_svc.obter_snapshot(snap_id),
        modo="beneficiario",
        propostas_selecionadas=["op-1", "op-2"],
    )
    ids = [b.vida_id for b in vm.beneficiarios]
    assert len(ids) == len(set(ids))
    assert len(vm.beneficiarios) == 12


def test_beneficiario_propostas_distintas(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_duas_propostas()
    snap_id = _aprovar(repo, snap_svc, r)
    vm = construir_view_model(
        snap_svc.obter_snapshot(snap_id),
        modo="beneficiario",
        propostas_selecionadas=["op-1", "op-2"],
    )
    b = vm.beneficiarios[0]
    v1 = next(c.valor_centavos for c in b.propostas if c.opcao_id == "op-1")
    v2 = next(c.valor_centavos for c in b.propostas if c.opcao_id == "op-2")
    assert v1 != v2


def test_vigente_diferente_reajustado(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_vigente_diferente_reajustado()
    snap_id = _aprovar(repo, snap_svc, r)
    vm = construir_view_model(
        snap_svc.obter_snapshot(snap_id),
        modo="beneficiario",
        propostas_selecionadas=["op-1"],
    )
    diffs = [
        b
        for b in vm.beneficiarios
        if b.atual_vigente_centavos != b.atual_reajustado_centavos
    ]
    assert len(diffs) >= 1


def test_html_sem_nomes_modo_faixas(stack):
    repo, _, _, snap_svc, apres = stack
    snap_id = _aprovar(repo, snap_svc, rascunho_demo_12_vidas())
    res = apres.gerar_html(
        "demo-12",
        snap_id,
        GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
    )
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "Beneficiário fictício" not in html


def test_html_sem_metadados_tecnicos(stack):
    repo, _, _, snap_svc, apres = stack
    snap_id = _aprovar(repo, snap_svc, rascunho_demo_12_vidas())
    res = apres.gerar_html(
        "demo-12",
        snap_id,
        GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
    )
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "snapshot" not in html.lower()
    assert "hash" not in html.lower()
    assert "renderer" not in html.lower()


def test_totais_reconciliam_com_snapshot(stack):
    repo, _, _, snap_svc, apres = stack
    r = _rascunho_duas_propostas()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"])
    calc = calcular_propostas_do_snapshot(snap, ["op-1", "op-2"])
    assert vm.totais_gerais.atual_centavos == calcular_atual_total(snap)
    for op_id in ("op-1", "op-2"):
        assert vm.totais_gerais.propostas[op_id] == calc[op_id].total_proposta_centavos


def calcular_atual_total(snap):
    from newport_app.presentation.motor_por_proposta import calcular_atual_do_snapshot

    return calcular_atual_do_snapshot(snap).total_atual_centavos


def test_beneficiario_nao_vinculado_silenciosamente(stack):
    repo, historico, _, _, _ = stack
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)
    historico.registrar_posicao_cadastral(r, origem="siscor", documento_hash="h1", importador_versao="t")
    parts = historico.listar_participacoes("demo-12")
    assert all(p.beneficiario_id is None for p in parts)
    assert all(p.vinculo_status == "pendente" for p in parts)


def test_historico_entre_dois_ciclos(stack):
    repo, historico, _, _, _ = stack
    c = historico.criar_cliente("Empresa Ciclo Teste")
    ciclo1 = historico.criar_ciclo(c.id, 1)
    ciclo2 = historico.criar_ciclo(c.id, 2)
    r1 = rascunho_demo_12_vidas().model_copy(update={"id": "estudo-c1"})
    r2 = rascunho_demo_12_vidas().model_copy(update={"id": "estudo-c2", "titulo": "Ciclo 2"})
    repo.salvar_rascunho(r1)
    repo.salvar_rascunho(r2)
    historico.sincronizar_estudo_meta(r1)
    historico.sincronizar_estudo_meta(r2)
    historico.vincular_estudo(
        "estudo-c1",
        VincularEstudoRequest(cliente_id=c.id, ciclo_id=ciclo1.id),
    )
    historico.vincular_estudo(
        "estudo-c2",
        VincularEstudoRequest(cliente_id=c.id, ciclo_id=ciclo2.id),
    )
    historico.registrar_plano_contratado(
        r1,
        RegistrarPlanoContratadoRequest(opcao_proposta_id="op-1", vigencia_inicio=date(2025, 1, 1)),
    )
    ultimo = historico.obter_ultimo_plano_cliente(c.id, excluir_estudo="estudo-c2")
    assert ultimo is not None
    assert ultimo.estudo_id == "estudo-c1"


def test_confirmar_vinculo_novo_beneficiario(stack):
    repo, historico, _, _, _ = stack
    c = historico.criar_cliente("Cliente Vinculo")
    r = rascunho_demo_12_vidas()
    repo.salvar_rascunho(r)
    historico.sincronizar_estudo_meta(r)
    historico.vincular_estudo(
        "demo-12",
        VincularEstudoRequest(cliente_id=c.id, criar_ciclo=True, ciclo_numero=1),
    )
    historico.registrar_posicao_cadastral(r, origem="manual", documento_hash=None, importador_versao=None)
    p = historico.listar_participacoes("demo-12")[0]
    historico.confirmar_vinculo(ConfirmarVinculoRequest(participacao_id=p.id, acao="novo"))
    p2 = historico.listar_participacoes("demo-12")[0]
    assert p2.beneficiario_id is not None
    assert p2.vinculo_status == "novo"


def test_faixa_valor_persistidos_historico(stack):
    repo, historico, _, _, _ = stack
    base = rascunho_demo_12_vidas()
    v0 = base.vidas[0].model_copy(
        update={
            "valor_fatura": ComponenteFinanceiroRascunho(
                centavos=123_456,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
            )
        }
    )
    r = base.model_copy(update={"vidas": [v0, *base.vidas[1:]]})
    repo.salvar_rascunho(r)
    historico.registrar_posicao_cadastral(r, origem="siscor", documento_hash="x", importador_versao="1")
    p = historico.listar_participacoes("demo-12")[0]
    assert p.faixa is not None
    assert p.valor_centavos == 123_456


def test_matriz_reconciliacao_faixa_proposta(stack):
    repo, _, _, snap_svc, _ = stack
    r = _rascunho_duas_propostas()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=["op-1", "op-2"])
    matriz = []
    for sec in vm.secoes_regime:
        for plano in sec.planos_atuais:
            for fx in plano.faixas:
                if fx.qtd_total == 0:
                    continue
                row = {
                    "regime": sec.regime_tipo,
                    "plano": plano.plano_nome,
                    "faixa": fx.faixa,
                    "vidas": fx.qtd_total,
                    "atual_vigente": fx.atual_vigente_total_centavos,
                    "atual_reajustado": fx.atual_reajustado_total_centavos,
                }
                for col in fx.propostas:
                    row[f"prop_{col.opcao_id}"] = col.subtotal_centavos
                matriz.append(row)
    assert len(matriz) >= 1
    assert all("prop_op-1" in r or "prop_op-2" in r for r in matriz)
