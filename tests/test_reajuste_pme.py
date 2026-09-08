"""Sugestão de reajuste PME abaixo de 30 vidas — tabela versionada, tipo=premio."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import VidaRascunho
from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.regras_comerciais import reconhecer_operadora
from newport_app.reajuste_pme import (
    CAMINHO_BASE,
    LIMIAR_VIDAS_PME,
    BaseReajustesPmeInvalida,
    aplicar_sugestao_se_vazio,
    carregar_base,
    formatar_pct_de_bps,
    periodo_da_data,
    reconhecer_operadora_reajuste,
    sugerir_reajuste_plano,
    sugestoes_do_rascunho,
    vidas_incluidas_estudo,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_frente2_grupo_familiar import _anistia_com_vinculos, _ids_seis
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar as _aprovar_gabarito,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

_WEB = Path(__file__).resolve().parents[1] / "web" / "src"
_PERIODO_2026 = "Maio 2026 a Abril 2027"
_PERIODO_2025 = "Maio 2025 a Abril 2026"


def _rascunho_pme(
    *,
    n_vidas: int = 12,
    operadora: str = "Porto Saúde",
    data: date | None = date(2026, 8, 1),
    reajuste_bps: int | None = None,
    estudo_id: str = "pme-teste",
    n_excluidas: int = 0,
):
    base = rascunho_demo_12_vidas()
    vidas = []
    total = n_vidas + n_excluidas
    for i in range(total):
        vidas.append(
            VidaRascunho(
                id=f"v{i}",
                nome=f"Beneficiário {i + 1}",
                nascimento=date(1980, 1, 1),
                incluida=i < n_vidas,
                subgrupo_atual_id="sg-1",
            )
        )
    sg = base.subgrupos_atuais[0].model_copy(
        update={"operadora": operadora, "reajuste_bps": reajuste_bps}
    )
    escolhas = base.escolhas.model_copy(update={"data_referencia_idade": data})
    return base.model_copy(
        update={
            "id": estudo_id,
            "vidas": vidas,
            "subgrupos_atuais": [sg],
            "escolhas": escolhas,
        }
    )


def test_01_menos_de_30_vidas_preenche_premio():
    r = _rascunho_pme(n_vidas=12, operadora="Porto Saúde", data=date(2026, 8, 1))
    assert vidas_incluidas_estudo(r) == 12
    assert vidas_incluidas_estudo(r) < LIMIAR_VIDAS_PME
    sug = sugestoes_do_rascunho(r)
    assert len(sug) == 1
    assert sug[0].origem == "tabela_pme"
    assert sug[0].periodo == _PERIODO_2026
    assert sug[0].reajuste_bps == 1247
    assert sug[0].reajuste_pct_exibicao == "12,47"
    preenchido = aplicar_sugestao_se_vazio(
        r.subgrupos_atuais[0].reajuste_bps, sug[0].reajuste_bps
    )
    assert preenchido == 1247


def test_02_trinta_ou_mais_em_branco_anistia_41():
    r = _rascunho_anistia_seis()
    n = vidas_incluidas_estudo(r)
    assert n == 41
    assert n >= LIMIAR_VIDAS_PME
    sug = sugestoes_do_rascunho(r)
    assert sug
    assert all(s.reajuste_bps is None for s in sug)
    assert all(s.origem is None for s in sug)
    for sg, s in zip(r.subgrupos_atuais, sug, strict=True):
        assert aplicar_sugestao_se_vazio(sg.reajuste_bps, s.reajuste_bps) == 1200

    r30 = _rascunho_pme(n_vidas=30, operadora="Porto Saúde", data=date(2026, 8, 1))
    s30 = sugestoes_do_rascunho(r30)[0]
    assert s30.reajuste_bps is None
    assert s30.periodo == _PERIODO_2026


def test_03_porto_2026_usa_premio_12_47_nao_reembolso_11_80():
    periodo, bps, pct, origem = sugerir_reajuste_plano(
        operadora="Porto Saúde",
        data_referencia=date(2026, 8, 1),
        vidas_incluidas=10,
    )
    assert origem == "tabela_pme"
    assert periodo == _PERIODO_2026
    assert bps == 1247
    assert pct == "12,47"
    assert bps != 1180
    linhas = [ln for ln in carregar_base() if ln.periodo == _PERIODO_2026]
    porto = [ln for ln in linhas if ln.chave_operadora == "Porto Seguro"]
    tipos = {ln.tipo: ln.reajuste_bps for ln in porto}
    assert tipos["premio"] == 1247
    assert tipos["reembolso"] == 1180


def test_04_operadora_fora_da_base_em_branco_sem_erro():
    r = _rascunho_pme(operadora="Alice", data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.operadora_canonica == "Alice"
    assert sug.reajuste_bps is None
    assert sug.origem is None
    assert sug.periodo == _PERIODO_2026


def test_05_cnu_2026_lacuna_nao_usa_periodo_vizinho():
    r = _rascunho_pme(operadora="CNU", data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.operadora_canonica == "CNU"
    assert sug.periodo == _PERIODO_2026
    assert sug.reajuste_bps is None
    periodo, bps, _, _ = sugerir_reajuste_plano(
        operadora="CNU",
        data_referencia=date(2025, 8, 1),
        vidas_incluidas=10,
    )
    assert periodo == _PERIODO_2025
    assert bps == 1950


def test_06_individuais_ans_nunca_casa():
    assert reconhecer_operadora_reajuste("Individuais (ANS)") is None
    assert reconhecer_operadora("Individuais (ANS)") is None
    r = _rascunho_pme(operadora="Individuais (ANS)", data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.reajuste_bps is None
    assert sug.operadora_canonica is None
    r2 = _rascunho_pme(operadora="AMIL", data=date(2026, 8, 1))
    assert sugestoes_do_rascunho(r2)[0].reajuste_bps == 1198


def test_07_cnu_nao_casa_com_seguros_unimed_nem_regional():
    assert reconhecer_operadora_reajuste("CNU") == "CNU"
    assert reconhecer_operadora_reajuste("Seguros Unimed") == "Seguros Unimed"
    assert reconhecer_operadora_reajuste("Unimed os Bandeirantes") == (
        "Unimed os Bandeirantes"
    )
    assert reconhecer_operadora_reajuste("Unimed Campinas") is None
    assert reconhecer_operadora_reajuste("Unimed") is None
    cnu = sugerir_reajuste_plano(
        operadora="CNU", data_referencia=date(2025, 6, 1), vidas_incluidas=5
    )[1]
    su = sugerir_reajuste_plano(
        operadora="Seguros Unimed",
        data_referencia=date(2025, 6, 1),
        vidas_incluidas=5,
    )[1]
    assert cnu == 1950
    assert su == 1192
    assert cnu != su


def test_08_valor_editado_nao_e_sobrescrito(tmp_path: Path):
    r = _rascunho_pme(reajuste_bps=1500, data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.reajuste_bps == 1247
    assert aplicar_sugestao_se_vazio(1500, sug.reajuste_bps) == 1500
    repo = SQLiteStudyRepository(tmp_path / "editado.db")
    repo.salvar_rascunho(r)
    carregado = repo.obter_rascunho(r.id)
    assert carregado is not None
    assert carregado.subgrupos_atuais[0].reajuste_bps == 1500
    de_novo = sugestoes_do_rascunho(carregado)[0]
    assert (
        aplicar_sugestao_se_vazio(
            carregado.subgrupos_atuais[0].reajuste_bps, de_novo.reajuste_bps
        )
        == 1500
    )
    client = TestClient(create_app(repo=repo, seed_demos=False))
    res = client.get(f"/api/estudos/{r.id}/rascunho")
    assert res.status_code == 200
    assert res.json()["subgrupos_atuais"][0]["reajuste_bps"] == 1500
    calc = client.post(f"/api/estudos/{r.id}/calcular")
    assert calc.status_code in {200, 400, 409, 422}
    de_novo2 = repo.obter_rascunho(r.id)
    assert de_novo2.subgrupos_atuais[0].reajuste_bps == 1500


def test_09_estudo_existente_com_reajuste_informado_intacto():
    r = _rascunho_anistia_seis()
    antes = [sg.reajuste_bps for sg in r.subgrupos_atuais]
    assert antes == [1200, 1200]
    for sg, s in zip(r.subgrupos_atuais, sugestoes_do_rascunho(r), strict=True):
        assert aplicar_sugestao_se_vazio(sg.reajuste_bps, s.reajuste_bps) == sg.reajuste_bps
    demo = rascunho_demo_12_vidas()
    assert demo.subgrupos_atuais[0].reajuste_bps == 1198
    s_demo = sugestoes_do_rascunho(demo)[0]
    assert aplicar_sugestao_se_vazio(1198, s_demo.reajuste_bps) == 1198


def test_10_base_malformada_informa_a_linha(tmp_path: Path):
    cab = "periodo;operadora;tipo;reajuste_pct;fonte;vigente_desde;atualizado_em\n"
    ruim = tmp_path / "ruim.csv"
    ruim.write_text(
        cab + "Maio 2026 a Abril 2027;Operadora Inventada;premio;10;x;;2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseReajustesPmeInvalida, match=r"registro 2") as exc:
        carregar_base(ruim)
    assert "Operadora Inventada" in str(exc.value)

    tipo_ruim = tmp_path / "tipo.csv"
    tipo_ruim.write_text(
        cab + "Maio 2026 a Abril 2027;Amil;moeda;10;x;;2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseReajustesPmeInvalida, match=r"registro 2.*tipo"):
        carregar_base(tipo_ruim)

    dup = tmp_path / "dup.csv"
    dup.write_text(
        cab
        + "Maio 2026 a Abril 2027;Amil;premio;10;x;;2026-01-01\n"
        + "Maio 2026 a Abril 2027;Amil;premio;11;x;;2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseReajustesPmeInvalida, match=r"registro 3.*duplicata"):
        carregar_base(dup)

    pct = tmp_path / "pct.csv"
    pct.write_text(
        cab + "Maio 2026 a Abril 2027;Amil;premio;abc;x;;2026-01-01\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseReajustesPmeInvalida, match=r"registro 2.*percentual"):
        carregar_base(pct)

    oficial = carregar_base()
    assert CAMINHO_BASE.is_file()
    assert any(ln.tipo == "premio" for ln in oficial)
    assert any(ln.tipo == "reembolso" for ln in oficial)


def test_11_gabarito_anistia_intacto(tmp_path: Path):
    r10 = _rascunho_dois_planos_gabarito(reajuste_bps=1000)
    m10, _ = _calcular_matriz(r10)
    snap10 = _aprovar_gabarito(tmp_path, r10)
    vm10 = construir_view_model(
        snap10, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(m10, vm10, gab)
    assert gab["reajuste"]["1200"]["consolidado_centavos"] == 4_847_931
    r12 = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap12 = _aprovar_gabarito(tmp_path, r12)
    vm12 = construir_view_model(
        snap12, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    assert vm12.totais_gerais.atual_centavos == 4_847_931
    prata = next(p for p in gab["propostas"] if p["chave"] == "prata")
    assert formatar_reais(prata["plano_a_centavos"]) == "R$ 23.607,17"
    assert formatar_reais(prata["plano_b_centavos"]) == "R$ 6.100,61"
    assert formatar_reais(4_847_931) == "R$ 48.479,31"


def test_12_hash_snapshot_inalterado(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-pme")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=_ids_seis()),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_14_seguro_novo_nao_preenche_nem_quebra():
    r = _rascunho_ivtec_novo()
    assert r.formato == "novo"
    assert r.subgrupos_atuais == []
    sug = sugestoes_do_rascunho(r)
    assert sug == []
    periodo, bps, pct, origem = sugerir_reajuste_plano(
        operadora="Amil",
        data_referencia=date(2026, 6, 30),
        vidas_incluidas=len(r.vidas_incluidas()),
        formato="novo",
    )
    assert periodo is None and bps is None and pct is None and origem is None


def test_15_periodo_aparece_na_interface():
    jsx = (_WEB / "ConfigEstudo.jsx").read_text(encoding="utf-8")
    assert "periodo-reajuste-pme" in jsx
    assert "origem-reajuste-pme" in jsx
    assert "Período de reajuste PME" in jsx
    assert "Tabela PME" in jsx
    r = _rascunho_pme(data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.periodo == _PERIODO_2026


def test_16_data_referencia_vazia_em_branco():
    r = _rascunho_pme(data=None, operadora="Porto Saúde")
    sug = sugestoes_do_rascunho(r)[0]
    assert sug.periodo is None
    assert sug.reajuste_bps is None
    assert sug.origem is None


def test_17_borda_do_periodo_30_04_vs_01_05():
    p_abril, bps_abril, pct_abril, _ = sugerir_reajuste_plano(
        operadora="Porto Saúde",
        data_referencia=date(2026, 4, 30),
        vidas_incluidas=10,
    )
    p_maio, bps_maio, pct_maio, _ = sugerir_reajuste_plano(
        operadora="Porto Saúde",
        data_referencia=date(2026, 5, 1),
        vidas_incluidas=10,
    )
    assert p_abril == _PERIODO_2025
    assert bps_abril == 1587
    assert pct_abril == "15,87"
    assert p_maio == _PERIODO_2026
    assert bps_maio == 1247
    assert pct_maio == "12,47"


def test_18_data_fora_da_base_nao_extrapola():
    for data_ref in (date(2015, 6, 1), date(2030, 1, 15)):
        periodo, bps, pct, origem = sugerir_reajuste_plano(
            operadora="Porto Saúde",
            data_referencia=data_ref,
            vidas_incluidas=10,
        )
        assert periodo is None
        assert bps is None
        assert pct is None
        assert origem is None


def test_gndi_e_porto_saude_via_aliases_canonicos():
    assert reconhecer_operadora_reajuste("GNDI") == "NotreDame"
    assert reconhecer_operadora_reajuste("Porto Saúde") == "Porto Seguro"
    assert reconhecer_operadora_reajuste("Careplus") == "Careplus"
    r = _rascunho_pme(operadora="GNDI", data=date(2026, 8, 1))
    assert sugestoes_do_rascunho(r)[0].reajuste_bps == 1290


def test_vidas_excluidas_nao_contam_no_corte_de_30():
    r = _rascunho_pme(n_vidas=29, n_excluidas=20, operadora="Porto Saúde")
    assert vidas_incluidas_estudo(r) == 29
    assert sugestoes_do_rascunho(r)[0].reajuste_bps == 1247


def test_api_sugestao_nao_grava_no_rascunho(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "api-pme.db")
    r = _rascunho_pme(reajuste_bps=None, data=date(2026, 8, 1))
    repo.salvar_rascunho(r)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    vazio = client.get(f"/api/estudos/{r.id}/rascunho")
    assert vazio.json()["subgrupos_atuais"][0]["reajuste_bps"] is None
    sug = client.get(f"/api/estudos/{r.id}/sugestao-reajuste-pme")
    assert sug.status_code == 200
    body = sug.json()
    assert body["vidas_incluidas"] == 12
    assert body["limiar_vidas"] == 30
    assert body["periodo"] == _PERIODO_2026
    assert body["por_plano"][0]["reajuste_bps"] == 1247
    assert body["por_plano"][0]["origem"] == "tabela_pme"
    ainda = client.get(f"/api/estudos/{r.id}/rascunho")
    assert ainda.json()["subgrupos_atuais"][0]["reajuste_bps"] is None
    borda = client.get(
        f"/api/estudos/{r.id}/sugestao-reajuste-pme",
        params={"data_referencia_idade": "2026-04-30"},
    )
    assert borda.json()["periodo"] == _PERIODO_2025
    assert borda.json()["por_plano"][0]["reajuste_bps"] == 1587


def test_formatar_pct_e_periodo_helper():
    assert formatar_pct_de_bps(1247) == "12,47"
    assert formatar_pct_de_bps(1800) == "18"
    assert formatar_pct_de_bps(1180) == "11,8"
    assert periodo_da_data(None) is None
    assert periodo_da_data(date(2026, 4, 30)) == _PERIODO_2025
    assert periodo_da_data(date(2026, 5, 1)) == _PERIODO_2026
