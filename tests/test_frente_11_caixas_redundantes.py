"""Frente 1.1 — caixas Operadora / Nome do plano saem da etapa 2; campos no modelo."""

from __future__ import annotations

import re
from pathlib import Path

from newport_app.models.draft import SubgrupoAtualRascunho
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.services.snapshot import SnapshotService
from newport_app.snapshot.comparativo import ler_comparativo_congelado
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito

_CONFIG = Path(__file__).resolve().parents[1] / "web" / "src" / "ConfigEstudo.jsx"


def test_01_etapa2_sem_caixas_operadora_e_plano_nome():
    src = _CONFIG.read_text(encoding="utf-8")
    assert "Operadora\n" not in src and re.search(r">\s*Operadora\s*<", src) is None
    assert re.search(r">\s*Nome do plano\s*<", src) is None
    assert 'atualizarSubgrupo(idx, "operadora"' not in src
    assert 'atualizarSubgrupo(idx, "plano_nome"' not in src


def test_02_cabecalho_exibe_operadora_e_plano_nome():
    src = _CONFIG.read_text(encoding="utf-8")
    assert "sg.operadora" in src
    assert "sg.plano_nome" in src
    assert "plan-card-title" in src
    assert ".join(\" · \")" in src or ".join(' · ')" in src


def test_03_campos_permanecem_no_modelo_e_no_rascunho(tmp_path):
    r = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    assert all(isinstance(sg, SubgrupoAtualRascunho) for sg in r.subgrupos_atuais)
    assert r.subgrupos_atuais[0].operadora
    assert r.subgrupos_atuais[0].plano_nome
    db = tmp_path / "frente11.db"
    repo = SQLiteStudyRepository(db)
    repo.salvar_rascunho(r)
    vivo = repo.obter_rascunho(r.id)
    assert vivo is not None
    assert vivo.subgrupos_atuais[0].operadora == r.subgrupos_atuais[0].operadora
    assert vivo.subgrupos_atuais[0].plano_nome == r.subgrupos_atuais[0].plano_nome
    vivo.subgrupos_atuais[0].tipo_fiscal = "operadora"
    repo.salvar_rascunho(vivo)
    de_novo = repo.obter_rascunho(r.id)
    assert de_novo.subgrupos_atuais[0].operadora == r.subgrupos_atuais[0].operadora
    assert de_novo.subgrupos_atuais[0].plano_nome == r.subgrupos_atuais[0].plano_nome


def test_04_tipo_fiscal_continua_na_ui():
    src = _CONFIG.read_text(encoding="utf-8")
    assert "Tipo fiscal" in src
    assert "TIPOS_FISCAIS" in src
    assert 'atualizarSubgrupo(idx, "tipo_fiscal"' in src


def test_05_snapshot_mantem_campos(tmp_path):
    r = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    db = tmp_path / "snap11.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    repo.salvar_rascunho(r)
    g = snap_svc.gerar_snapshot_candidato(r.id)
    snap_svc.aprovar_snapshot(
        r.id,
        g.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(g.snapshot_id)
    sgs = snap.payload["rascunho"]["subgrupos_atuais"]
    assert sgs[0]["operadora"] == r.subgrupos_atuais[0].operadora
    assert sgs[0]["plano_nome"] == r.subgrupos_atuais[0].plano_nome


def test_06_gabarito_anistia_inalterado():
    from newport_app.adapters.motor_out import rascunho_para_resumo
    from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual

    r = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    etapa1 = montar_resumo_plano_atual(r)
    resumo = rascunho_para_resumo(r)
    assert etapa1.total_reajustado_centavos == 4_847_931
    assert resumo.total_reajustado_reais == "R$ 48.479,31"
    por_id = {p.subgrupo_id: p for p in etapa1.planos}
    assert por_id["sg-a"].valor_mensal_reajustado_centavos == 2_938_676
    assert por_id["sg-b"].valor_mensal_reajustado_centavos == 1_909_255
    assert por_id["sg-a"].plano_nome
    assert por_id["sg-b"].plano_nome
    _, nucleo, _ = montar_payload_nucleo_congelamento(r, default_registry)
    assert hash_snapshot_canonico(nucleo) == hash_snapshot_canonico(nucleo)
