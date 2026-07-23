"""Testes ETAPAS 2.6–2.8: snapshot, aprovação e apresentação HTML."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.historico import RegistrarPlanoContratadoRequest
from newport_app.models.snapshot import (
    AprovarSnapshotRequest,
    GerarApresentacaoRequest,
)
from newport_app.presentation.html_renderer import render_html
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.apresentacao import ApresentacaoService
from newport_app.services.calculo import CalculoService
from newport_app.services.snapshot import (
    AprovacaoInvalidaError,
    SnapshotBloqueadoError,
    SnapshotService,
)


def _stack(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)

    def _invalidar(estudo_id: str, motivo: str) -> None:
        snap_svc.invalidar_por_alteracao(estudo_id, motivo)

    snap_svc = SnapshotService(repo, snap_repo, historico)
    calc = CalculoService(repo, on_rascunho_alterado=_invalidar)
    apres = ApresentacaoService(snap_svc, snap_repo, tmp_path / "entregaveis")
    return repo, historico, snap_repo, snap_svc, calc, apres


def _aprovar_demo(repo, snap_svc, apres, rascunho: RascunhoEstudo):
    repo.salvar_rascunho(rascunho)
    gerado = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        gerado.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Revisor Teste",
            confirmo_conteudo=True,
        ),
    )
    return gerado.snapshot_id


@pytest.fixture
def stack(tmp_path):
    return _stack(tmp_path)


def test_snapshot_demo_41_com_alerta(stack):
    repo, _, _, snap_svc, _, _ = stack
    repo.salvar_rascunho(rascunho_demo_41_vidas())
    gerado = snap_svc.gerar_snapshot_candidato("demo-41")
    assert gerado.tem_bloqueio is False
    snap = snap_svc.obter_snapshot(gerado.snapshot_id)
    pendencias = snap.payload["comparativo"].get("pendencias", [])
    assert any(p.get("tipo") == "alerta" for p in pendencias)


def test_fluxo_aprovacao_e_html(stack):
    repo, _, snap_repo, snap_svc, calc, apres = stack
    rascunho = rascunho_demo_12_vidas()
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho)

    comparativo = snap_svc.comparativo_do_snapshot(snap_id)
    calc_res = calc.calcular("demo-12")
    assert comparativo.totais is not None
    assert calc_res.totais is not None
    assert comparativo.totais.atual_mensal_reais == calc_res.totais.atual_mensal_reais

    snap_repo.invalidar_aprovacoes_estudo("demo-12", "teste")
    with pytest.raises(AprovacaoInvalidaError):
        apres.gerar_html(
            "demo-12",
            snap_id,
            GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
        )


def test_html_faixas_sem_nomes(stack):
    repo, _, _, snap_svc, _, apres = stack
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho_demo_12_vidas())
    res = apres.gerar_html(
        "demo-12",
        snap_id,
        GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
    )
    caminho = apres._entregaveis_dir / res.caminho_relativo  # noqa: SLF001
    conteudo = caminho.read_text(encoding="utf-8")
    assert "Beneficiário fictício" not in conteudo
    assert "1970" not in conteudo
    assert "http://" not in conteudo and "https://" not in conteudo
    assert "<style>" in conteudo
    assert res.modo == "faixas"


def test_html_beneficiario_todos(stack):
    repo, _, _, snap_svc, _, apres = stack
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho_demo_12_vidas())
    res = apres.gerar_html(
        "demo-12",
        snap_id,
        GerarApresentacaoRequest(modo="beneficiario", propostas_selecionadas=["op-1"]),
    )
    caminho = apres._entregaveis_dir / res.caminho_relativo  # noqa: SLF001
    conteudo = caminho.read_text(encoding="utf-8")
    assert conteudo.count("Beneficiário fictício") >= 12
    assert "nascimento" not in conteudo.lower()
    assert "1970-01-01" not in conteudo
    assert res.aviso_dados_pessoais is not None


@pytest.mark.parametrize("n_vidas", [1, 12, 29])
def test_modo_beneficiario_quantidade_vidas(stack, n_vidas):
    repo, _, _, snap_svc, _, apres = stack
    base = rascunho_demo_41_vidas() if n_vidas > 12 else rascunho_demo_12_vidas()
    vidas = base.vidas[:n_vidas]
    rascunho = base.model_copy(
        update={
            "id": f"demo-{n_vidas}",
            "titulo": f"Teste {n_vidas} vidas",
            "vidas": vidas,
        }
    )
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho)
    res = apres.gerar_html(
        rascunho.id,
        snap_id,
        GerarApresentacaoRequest(modo="beneficiario", propostas_selecionadas=["op-1"]),
    )
    caminho = apres._entregaveis_dir / res.caminho_relativo  # noqa: SLF001
    conteudo = caminho.read_text(encoding="utf-8")
    assert conteudo.count("<tr><td>") >= n_vidas


def test_demo_41_html_beneficiario_sem_truncar(stack):
    repo, _, _, snap_svc, _, apres = stack
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho_demo_41_vidas())
    res = apres.gerar_html(
        "demo-41",
        snap_id,
        GerarApresentacaoRequest(modo="beneficiario", propostas_selecionadas=["op-1"]),
    )
    caminho = apres._entregaveis_dir / res.caminho_relativo  # noqa: SLF001
    conteudo = caminho.read_text(encoding="utf-8")
    assert conteudo.count("Beneficiário fictício") >= 41


def test_invalidacao_apos_alteracao(stack):
    repo, _, snap_repo, snap_svc, calc, apres = stack
    rascunho = rascunho_demo_12_vidas()
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho)

    r2 = repo.obter_rascunho("demo-12")
    assert r2 is not None
    r2.titulo = "Título alterado"
    calc.salvar_rascunho(r2)

    assert snap_repo.snapshot_aprovado_atual("demo-12") is None
    with pytest.raises(AprovacaoInvalidaError):
        apres.gerar_html(
            "demo-12",
            snap_id,
            GerarApresentacaoRequest(modo="faixas", propostas_selecionadas=["op-1"]),
        )


def test_historico_posicao_versionada(stack):
    repo, historico, _, _, _, _ = stack
    rascunho = rascunho_demo_12_vidas()
    repo.salvar_rascunho(rascunho)
    historico.registrar_posicao_cadastral(
        rascunho,
        origem="siscor",
        documento_hash="abc123",
        importador_versao="test@1",
    )
    r2 = rascunho.model_copy(update={"titulo": "Outro título"})
    historico.registrar_posicao_cadastral(
        r2,
        origem="siscor",
        documento_hash="def456",
        importador_versao="test@1",
    )
    posicoes = historico.listar_posicoes("demo-12")
    assert len(posicoes) == 2
    assert posicoes[0].versao > posicoes[1].versao


def test_plano_contratado_imutavel(stack):
    repo, historico, _, _, _, _ = stack
    from datetime import date

    rascunho = rascunho_demo_12_vidas()
    repo.salvar_rascunho(rascunho)
    reg = historico.registrar_plano_contratado(
        rascunho,
        RegistrarPlanoContratadoRequest(
            opcao_proposta_id="op-1",
            vigencia_inicio=date(2026, 1, 1),
        ),
    )
    lista = historico.listar_planos_contratados("demo-12")
    assert len(lista) == 1
    assert lista[0].id == reg.id
    assert lista[0].plano_nome == "Proposta fictícia"


def test_html_autocontido_render(stack):
    repo, _, _, snap_svc, _, apres = stack
    snap_id = _aprovar_demo(repo, snap_svc, apres, rascunho_demo_12_vidas())
    snap = snap_svc.obter_snapshot(snap_id)
    from newport_app.presentation.builder import construir_view_model

    vm = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=["op-1"],
    )
    html = render_html(vm)
    assert "cdn." not in html.lower()
