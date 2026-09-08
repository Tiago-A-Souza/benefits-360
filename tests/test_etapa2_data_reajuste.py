"""Etapa 2 — data de referência acima do reajuste, sugestão reativa."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.reajuste_pme import (
    aplicar_sugestao_se_vazio,
    sugerir_reajuste_plano,
    sugestoes_do_rascunho,
    vidas_incluidas_estudo,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.policy.registry import default_registry
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_motor.faixa import faixa_em
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
from tests.test_reajuste_pme import _PERIODO_2026, _rascunho_pme
from newport_app.models.snapshot import GerarApresentacaoRequest

_WEB = Path(__file__).resolve().parents[1] / "web" / "src"
_JSX = _WEB / "ConfigEstudo.jsx"
_MSG = "Informe a data de referência para o sistema sugerir o reajuste."


def _amil_29_dois_planos(*, data: date | None):
    r = _rascunho_pme(
        n_vidas=29,
        operadora="AMIL",
        data=data,
        estudo_id="amil-29-dois",
    )
    sg_a = r.subgrupos_atuais[0].model_copy(
        update={"id": "sg-1", "plano_nome": "AMIL S750 - Apto."}
    )
    sg_b = r.subgrupos_atuais[0].model_copy(
        update={"id": "sg-one", "plano_nome": "AMIL ONE S2500 - Apto."}
    )
    vidas = []
    for i, v in enumerate(r.vidas):
        sid = "sg-1" if i < 20 else "sg-one"
        vidas.append(v.model_copy(update={"subgrupo_atual_id": sid}))
    return r.model_copy(update={"subgrupos_atuais": [sg_a, sg_b], "vidas": vidas})


def test_01_importado_sem_data_reajuste_branco_com_mensagem():
    r = _amil_29_dois_planos(data=None)
    assert r.escolhas.data_referencia_idade is None
    sug = sugestoes_do_rascunho(r)
    assert vidas_incluidas_estudo(r) == 29
    assert all(s.reajuste_bps is None for s in sug)
    jsx = _JSX.read_text(encoding="utf-8")
    assert _MSG in jsx
    assert "aviso-data-reajuste" in jsx


def test_02_data_01_08_2026_sugere_11_98_nos_dois_planos():
    r = _amil_29_dois_planos(data=date(2026, 8, 1))
    sug = sugestoes_do_rascunho(r)
    assert len(sug) == 2
    for s in sug:
        assert s.periodo == _PERIODO_2026
        assert s.reajuste_bps == 1198
        assert s.reajuste_pct_exibicao == "11,98"
        assert s.origem == "tabela_pme"
        assert s.operadora_canonica == "Amil"
    jsx = _JSX.read_text(encoding="utf-8")
    assert "Período de reajuste PME" in jsx
    assert "data_referencia_idade" in jsx
    assert "obterSugestaoReajustePme(estudoId, rascunho.escolhas?.data_referencia_idade)" in jsx


def test_03_apagar_data_volta_sugestao_a_branco():
    assert aplicar_sugestao_se_vazio(None, 1198) == 1198
    assert aplicar_sugestao_se_vazio(None, None) is None
    r = _amil_29_dois_planos(data=None)
    assert all(s.reajuste_bps is None for s in sugestoes_do_rascunho(r))


def test_04_apagar_data_nao_apaga_valor_digitado():
    jsx = _JSX.read_text(encoding="utf-8")
    assert "if (editados.has(sg.id)) continue;" in jsx
    assert "if (original != null && original !== naCarga) continue;" in jsx
    assert aplicar_sugestao_se_vazio(1500, None) == 1500
    assert aplicar_sugestao_se_vazio(1500, 1198) == 1500


def test_05_valor_editado_permanece_salvar_recarregar(tmp_path: Path):
    r = _amil_29_dois_planos(data=date(2026, 8, 1))
    sgs = [
        sg.model_copy(update={"reajuste_bps": 1500 if i == 0 else sg.reajuste_bps})
        for i, sg in enumerate(r.subgrupos_atuais)
    ]
    r = r.model_copy(update={"subgrupos_atuais": sgs})
    repo = SQLiteStudyRepository(tmp_path / "edit.db")
    repo.salvar_rascunho(r)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    body = client.get(f"/api/estudos/{r.id}/rascunho").json()
    assert body["subgrupos_atuais"][0]["reajuste_bps"] == 1500
    sug = client.get(
        f"/api/estudos/{r.id}/sugestao-reajuste-pme",
        params={"data_referencia_idade": "2026-08-01"},
    ).json()
    assert sug["por_plano"][0]["reajuste_bps"] == 1198
    assert aplicar_sugestao_se_vazio(1500, 1198) == 1500
    client.post(f"/api/estudos/{r.id}/calcular")
    de_novo = repo.obter_rascunho(r.id)
    assert de_novo.subgrupos_atuais[0].reajuste_bps == 1500


def test_06_anistia_41_sem_sugestao_mesmo_com_data():
    r = _rascunho_anistia_seis()
    assert vidas_incluidas_estudo(r) == 41
    assert r.escolhas.data_referencia_idade is not None
    sug = sugestoes_do_rascunho(r)
    assert all(s.reajuste_bps is None for s in sug)
    r30 = _rascunho_pme(n_vidas=30, operadora="AMIL", data=date(2026, 8, 1))
    assert sugestoes_do_rascunho(r30)[0].reajuste_bps is None


def test_07_data_continua_definindo_idades():
    nasc = date(1990, 6, 15)
    idade_a, faixa_a = faixa_em(nasc, date(2018, 6, 15))
    idade_b, faixa_b = faixa_em(nasc, date(2019, 6, 15))
    assert idade_a == 28
    assert idade_b == 29
    assert faixa_a != faixa_b
    mapper = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "newport_app"
        / "draft_compiler"
        / "mapper.py"
    ).read_text(encoding="utf-8")
    assert "data_referencia_idade=esc.data_referencia_idade" in mapper


def test_08_borda_periodo_porto():
    _, bps_abril, pct_abril, _ = sugerir_reajuste_plano(
        operadora="Porto Saúde",
        data_referencia=date(2026, 4, 30),
        vidas_incluidas=10,
    )
    _, bps_maio, pct_maio, _ = sugerir_reajuste_plano(
        operadora="Porto Saúde",
        data_referencia=date(2026, 5, 1),
        vidas_incluidas=10,
    )
    assert bps_abril == 1587 and pct_abril == "15,87"
    assert bps_maio == 1247 and pct_maio == "12,47"


def test_09_data_vazia_sem_valor_por_omissao():
    jsx = _JSX.read_text(encoding="utf-8")
    assert "new Date()" not in jsx
    assert "date.today" not in jsx
    siscor = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "newport_app"
        / "services"
        / "importacao_siscor.py"
    ).read_text(encoding="utf-8")
    assert not re.search(r"data_referencia_idade\s*=", siscor)
    r = _amil_29_dois_planos(data=None)
    assert r.escolhas.data_referencia_idade is None


def test_10_secao_comparacao_mantem_referencia_e_origem():
    jsx = _JSX.read_text(encoding="utf-8")
    idx_data = jsx.find('className="data-referencia-reajuste"')
    idx_planos = jsx.find('className="plan-card"')
    idx_comp = jsx.find("Referência da comparação")
    assert 0 <= idx_data < idx_planos < idx_comp
    depois = jsx[idx_comp:]
    assert "data-referencia-reajuste" not in depois
    assert "Referência do contrato" in jsx
    assert "Origem dos valores atuais" in jsx
    assert "Contrato vigente" in jsx
    assert "Contrato reajustado" in jsx


def test_11_gabarito_anistia_intacto(tmp_path: Path):
    r10 = _rascunho_dois_planos_gabarito(reajuste_bps=1000)
    m10, _ = _calcular_matriz(r10)
    snap10 = _aprovar_gabarito(tmp_path, r10)
    vm10 = construir_view_model(
        snap10, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(m10, vm10, gab)
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


def test_12_hash_snapshot_inalterado(tmp_path: Path, capsys):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-data-pme")
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


def test_query_vazia_sobrescreve_data_salva(tmp_path: Path):
    r = _amil_29_dois_planos(data=date(2026, 8, 1))
    repo = SQLiteStudyRepository(tmp_path / "query-vazia.db")
    repo.salvar_rascunho(r)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    com = client.get(f"/api/estudos/{r.id}/sugestao-reajuste-pme").json()
    assert com["por_plano"][0]["reajuste_bps"] == 1198
    vazio = client.get(
        f"/api/estudos/{r.id}/sugestao-reajuste-pme",
        params={"data_referencia_idade": ""},
    ).json()
    assert vazio["periodo"] is None
    assert vazio["data_referencia_idade"] is None
    assert vazio["por_plano"][0]["reajuste_bps"] is None
    salvo = repo.obter_rascunho(r.id)
    assert salvo.escolhas.data_referencia_idade == date(2026, 8, 1)
