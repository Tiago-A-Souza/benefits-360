"""Testes de linguagem e apresentação — ETAPA 2.1 patch."""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient

from newport_app.adapters.motor_out import motor_result_para_comparativo, rascunho_para_resumo
from newport_app.models.draft import EscolhasEstudo, RascunhoEstudo, VidaRascunho
from newport_app.presentation.textos import (
    descricao_estudo,
    mensagem_faixa_homologada,
    plural_beneficiarios,
    rotulos_diferenca,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import CalculoService
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_motor.engine import calcular
from newport_app.adapters.motor_in import rascunho_para_estudo_input, rascunho_para_policy


def test_plural_singular():
    assert plural_beneficiarios(1) == "1 beneficiário"


def test_plural_multiplo():
    assert plural_beneficiarios(12) == "12 beneficiários"
    assert plural_beneficiarios(41) == "41 beneficiários"


def test_descricao_renovacao_acentuada():
    texto = descricao_estudo("renovacao", 12)
    assert "renovação" in texto
    assert "renovacao" not in texto
    assert "12 beneficiários" in texto
    assert "beneficiário(s)" not in texto


def test_rotulos_aumento():
    sem, mes, ano = rotulos_diferenca(100_00, 1_200_00)
    assert sem == "aumento"
    assert mes == "Aumento mensal"
    assert ano == "Aumento anual"


def test_rotulos_economia():
    sem, mes, ano = rotulos_diferenca(-50_00, -600_00)
    assert sem == "economia"
    assert mes == "Economia mensal"
    assert ano == "Economia anual"


def test_rotulos_empate():
    sem, mes, ano = rotulos_diferenca(0, 0)
    assert sem == "empate"
    assert mes == "Sem diferença mensal"
    assert ano == "Sem diferença anual"


def test_mensagem_faixa_41_versus_29():
    msg = mensagem_faixa_homologada(41, 29)
    assert "41 vidas" in msg
    assert "29 vidas" in msg
    assert "faixa operacional homologada" in msg


def test_resumo_demo_12_linguagem():
    resumo = rascunho_para_resumo(rascunho_demo_12_vidas())
    assert resumo.formato_exibicao == "renovação"
    assert resumo.beneficiarios_rotulo == "12 beneficiários"
    assert "renovação" in resumo.descricao


def test_resumo_uma_vida():
    base = rascunho_demo_12_vidas()
    r = RascunhoEstudo(
        id="demo-1",
        titulo="Teste 1 vida",
        formato="renovacao",
        vidas=[
            VidaRascunho(
                id="v0",
                nome="Beneficiário fictício 1",
                nascimento=date(1980, 1, 1),
                incluida=True,
                subgrupo_atual_id="sg-1",
            )
        ],
        subgrupos_atuais=base.subgrupos_atuais,
        opcoes_proposta=base.opcoes_proposta,
        regimes_copart=base.regimes_copart,
        cenarios=base.cenarios,
        escolhas=base.escolhas,
    )
    resumo = rascunho_para_resumo(r)
    assert resumo.beneficiarios_rotulo == "1 beneficiário"
    assert "1 beneficiário" in resumo.descricao


def test_comparativo_demo_12_rotulo_aumento():
    rascunho = rascunho_demo_12_vidas()
    resultado = calcular(rascunho_para_estudo_input(rascunho), rascunho_para_policy(rascunho))
    resp = motor_result_para_comparativo(rascunho, resultado)
    assert resp.totais is not None
    assert resp.totais.diferenca_semantica == "aumento"
    assert resp.totais.rotulo_diferenca_mensal == "Aumento mensal"
    assert resp.totais.rotulo_diferenca_anual == "Aumento anual"


def test_comparativo_economia_rascunho_temporario():
    """Economia via rascunho de teste — não altera seed demo-12."""
    rascunho = rascunho_demo_12_vidas()
    rascunho.id = "test-economia"
    for faixa in rascunho.opcoes_proposta[0].tabela:
        faixa.valor_centavos = 10_000
    resultado = calcular(rascunho_para_estudo_input(rascunho), rascunho_para_policy(rascunho))
    resp = motor_result_para_comparativo(rascunho, resultado)
    assert resp.totais is not None
    assert resp.totais.diferenca_semantica == "economia"
    assert resp.totais.rotulo_diferenca_mensal == "Economia mensal"
    assert not resp.totais.diferenca_mensal_reais.startswith("-")


@pytest.fixture
def client(tmp_path):
    repo = SQLiteStudyRepository(tmp_path / "t.db")
    from newport_app.api.main import create_app

    return TestClient(create_app(repo=repo))


def test_api_demo_12_aumento(client: TestClient):
    res = client.post("/api/estudos/demo-12/calcular")
    totais = res.json()["totais"]
    assert totais["diferenca_semantica"] == "aumento"
    assert totais["rotulo_diferenca_mensal"] == "Aumento mensal"


def test_api_demo_41_aviso_numerico(client: TestClient):
    res = client.post("/api/estudos/demo-41/calcular")
    alertas = [p for p in res.json()["pendencias"] if p["tipo"] == "alerta"]
    assert len(alertas) >= 1
    desc = alertas[0]["descricao"]
    assert "41 vidas" in desc
    assert "29 vidas" in desc
