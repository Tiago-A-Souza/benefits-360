"""Base reajustada na listagem (EstudoResumo via montar_resumo_plano_atual)."""

from __future__ import annotations

import time
from pathlib import Path

from newport_app.adapters.motor_out import rascunho_para_resumo
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.calculo import CalculoService
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito
from tests.test_resumo_plano_atual_agregacao import _rascunho_com_vidas


def test_renovacao_anistia_mesmo_total_da_etapa_1():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    etapa1 = montar_resumo_plano_atual(rascunho)
    resumo = rascunho_para_resumo(rascunho)

    assert etapa1.total_reajustado_centavos == 4_847_931
    assert etapa1.total_reajustado_reais == "R$ 48.479,31"
    assert resumo.total_reajustado_centavos == etapa1.total_reajustado_centavos
    assert resumo.total_reajustado_reais == etapa1.total_reajustado_reais
    assert resumo.total_reajustado_reais == "R$ 48.479,31"


def test_seguro_novo_base_none_nunca_zero():
    rascunho = _rascunho_ivtec_novo()
    resumo = rascunho_para_resumo(rascunho)
    assert rascunho.formato == "novo"
    assert resumo.total_reajustado_centavos is None
    assert resumo.total_reajustado_reais is None
    assert resumo.total_reajustado_centavos != 0


def test_sem_reajuste_base_none_nao_usa_vigente():
    spec = [{"faixa": 0, "centavos": 100_00}] * 3
    rascunho = _rascunho_com_vidas(spec)
    rascunho.subgrupos_atuais[0].reajuste_bps = None

    etapa1 = montar_resumo_plano_atual(rascunho)
    resumo = rascunho_para_resumo(rascunho)

    assert etapa1.total_vigente_centavos == 300_00
    assert etapa1.total_reajustado_centavos is None
    assert resumo.total_reajustado_centavos is None
    assert resumo.total_reajustado_reais is None
    assert resumo.total_reajustado_centavos != etapa1.total_vigente_centavos


def test_listar_resumos_propaga_base(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "estudos.db")
    anistia = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    novo = _rascunho_ivtec_novo()
    repo.salvar_rascunho(anistia)
    repo.salvar_rascunho(novo)

    svc = CalculoService(repo)
    por_id = {r.id: r for r in svc.listar_resumos()}

    assert por_id[anistia.id].total_reajustado_reais == "R$ 48.479,31"
    assert por_id[novo.id].total_reajustado_centavos is None
    assert por_id[novo.id].total_reajustado_reais is None


def test_listagem_47_estudos_abaixo_de_300ms():
    """Mede no banco local de demo quando há ≥47 estudos."""
    import pytest

    demo = Path(".data") / "newport_app.db"
    if not demo.is_file():
        pytest.skip("sem .data/newport_app.db")
    repo = SQLiteStudyRepository(demo)
    metas = repo.listar_metadados()
    if len(metas) < 47:
        pytest.skip(f"demo tem só {len(metas)} estudos")
    svc = CalculoService(repo)
    svc.listar_resumos()  # warm
    tempos: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        resumos = svc.listar_resumos()
        tempos.append((time.perf_counter() - t0) * 1000)
    assert len(resumos) >= 47
    mediana = sorted(tempos)[2]
    assert mediana < 300, f"mediana {mediana:.1f} ms ≥ 300"
def test_listagem_47_estudos_sinteticos_abaixo_de_300ms(tmp_path: Path):
    from newport_app.siscor_mapper.apply import rascunho_vazio

    repo = SQLiteStudyRepository(tmp_path / "perf.db")
    for i in range(47):
        repo.salvar_rascunho(
            rascunho_vazio(f"perf-{i}", f"Estudo perf {i}", formato="renovacao")
        )
    svc = CalculoService(repo)
    svc.listar_resumos()
    tempos: list[float] = []
    for _ in range(5):
        t0 = time.perf_counter()
        assert len(svc.listar_resumos()) == 47
        tempos.append((time.perf_counter() - t0) * 1000)
    mediana = sorted(tempos)[2]
    assert mediana < 300, f"mediana {mediana:.1f} ms ≥ 300"
