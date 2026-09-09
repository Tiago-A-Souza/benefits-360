"""Matriz de estimativa opção × plano vigente para o dropdown da etapa 4."""

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.cotacao_pdf.estimativa import estimar_opcao_rascunho
from newport_app.policy.registry import default_registry
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.services.matriz_estimativa import montar_matriz_estimativa
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_frente2_grupo_familiar import _GABARITO
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito


def _celula(matriz, opcao_id: str, subgrupo_id: str):
    return next(
        c
        for c in matriz.celulas
        if c.opcao_id == opcao_id and c.subgrupo_id == subgrupo_id
    )


def test_s750_e_one_diferem_na_mesma_cotacao():
    rascunho = _rascunho_anistia_seis()
    matriz = montar_matriz_estimativa(rascunho)
    assert len(rascunho.opcoes_proposta) == 6
    assert {sg.id for sg in rascunho.subgrupos_atuais} == {"sg-a", "sg-b"}
    assert len(matriz.celulas) == 12

    prata_s750 = _celula(matriz, "op-prata", "sg-a")
    prata_one = _celula(matriz, "op-prata", "sg-b")
    assert prata_s750.diff_centavos is not None
    assert prata_one.diff_centavos is not None
    assert prata_s750.diff_centavos != prata_one.diff_centavos
    assert prata_s750.estimado_centavos != prata_one.estimado_centavos


def test_bate_com_etapa_3_mesmo_grupo_mesmo_centavo():
    """Mesma composição da etapa 3: estimar_opcao_rascunho − referência do resumo."""
    rascunho = _rascunho_anistia_seis()
    resumo = montar_resumo_plano_atual(rascunho)
    matriz = montar_matriz_estimativa(rascunho)
    for plano in resumo.planos:
        quantidades = {fx.faixa: fx.quantidade_vidas for fx in plano.faixas}
        for opcao in rascunho.opcoes_proposta:
            estimado = estimar_opcao_rascunho(opcao, quantidades)
            esperado_diff = None
            if estimado is not None and plano.referencia_comparativo_centavos:
                esperado_diff = estimado - plano.referencia_comparativo_centavos
            cel = _celula(matriz, opcao.id, plano.subgrupo_id)
            assert cel.estimado_centavos == estimado
            assert cel.diff_centavos == esperado_diff


def test_opcao_sem_estimativa_nao_inventa_zero():
    rascunho = _rascunho_anistia_seis()
    rascunho.opcoes_proposta[0].tipo_fiscal = None
    matriz = montar_matriz_estimativa(rascunho)
    for cel in matriz.celulas:
        if cel.opcao_id != rascunho.opcoes_proposta[0].id:
            continue
        assert cel.estimado_centavos is None
        assert cel.diff_centavos is None


def test_gabarito_anistia_e_hash_inalterados():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    resumo = montar_resumo_plano_atual(rascunho)
    assert resumo.total_reajustado_centavos == _GABARITO["consolidado_proposta"] == 4_847_931
    assert resumo.total_reajustado_reais == "R$ 48.479,31"

    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    montar_matriz_estimativa(rascunho)
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_endpoint_6x2_e_tempo(tmp_path: Path):
    rascunho = _rascunho_anistia_seis()
    repo = SQLiteStudyRepository(tmp_path / "estudos.db")
    repo.salvar_rascunho(rascunho)
    app = create_app(
        repo=repo,
        import_repo=ImportacaoSiscorRepository(tmp_path / "imp.db"),
        uploads_dir=tmp_path / "uploads",
        seed_demos=False,
    )
    client = TestClient(app)
    t0 = time.perf_counter()
    res = client.get(f"/api/estudos/{rascunho.id}/estimativa-opcao-subgrupo")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert res.status_code == 200
    corpo = res.json()
    assert len(corpo["celulas"]) == 12
    print(f"MATRIZ_ELAPSED_MS={elapsed_ms:.1f}")
    assert elapsed_ms < 2000


def test_jsx_nao_calcula_nem_usa_fallback_sem_iof():
    painel = (
        Path(__file__).resolve().parents[1]
        / "web"
        / "src"
        / "PlanosSelecionadosPanel.jsx"
    ).read_text(encoding="utf-8")
    assert "calcularEstimadoCentavos" not in painel
    assert "formatarDiferencaReferencia" not in painel
    assert "obterMatrizEstimativa" in painel
    assert "diff_centavos" in painel
    assert "rotuloOpcaoComDiff" in painel
    assert "estimado - " not in painel
    assert "estimado-" not in painel
