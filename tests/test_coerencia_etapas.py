"""Coerência de apresentação e valores entre etapas."""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.cotacao_pdf.estimativa import estimar_opcao_candidata, estimar_opcao_rascunho
from newport_app.draft_compiler import compile
from newport_app.models.cotacao_pdf import FaixaExtraida, OpcaoCotacaoCandidata, ValorExtraido
from newport_app.models.draft import PriceBasisRascunho
from newport_app.models.presentation import (
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
    TotaisGeraisApresentacao,
)
from newport_app.presentation.html_renderer import render_html
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_motor.engine import calcular
from newport_motor.faixa import faixa_em
from newport_motor.money import apply_rate_bps
from tests.fixtures.siscor.xlsx_builder import planilha_12_vidas, planilha_41_vidas_2_planos

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "test.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    app = create_app(
        repo=repo,
        import_repo=imp,
        uploads_dir=tmp_path / "uploads",
        seed_demos=False,
    )
    return TestClient(app)


def _importar(client: TestClient, estudo_id: str, xlsx: bytes):
    files = {
        "arquivo": (
            "planilha.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return client.post(f"/api/estudos/{estudo_id}/importar-siscor", files=files)


def _vm_com_proposta(op_id: str, plano_nome: str) -> PresentationViewModel:
    return PresentationViewModel(
        titulo="Estudo teste",
        data_apresentacao="07/08/2026",
        estudo_id="est-test",
        modo="faixas",
        propostas_selecionadas=[op_id],
        totais_gerais=TotaisGeraisApresentacao(
            atual_centavos=500_000,
            propostas={op_id: 600_000},
            diff_mensal={op_id: 100_000},
        ),
        secoes_regime=[
            SecaoRegimeApresentacao(
                regime_rotulo="Sem coparticipação",
                regime_tipo="sem",
                propostas=[
                    PropostaApresentacao(
                        opcao_id=op_id,
                        operadora="Operadora Fictícia",
                        plano_nome=plano_nome,
                        regime_rotulo="Sem coparticipação",
                        regime_tipo="sem",
                    )
                ],
            )
        ],
    )


def _opcao_seguradora_exclui_iof(valor_unit: int = 100_000) -> OpcaoCotacaoCandidata:
    tabela = []
    for faixa in range(10):
        tabela.append(
            FaixaExtraida(
                faixa=faixa,
                valor=ValorExtraido(
                    id=f"v{faixa}",
                    rotulo="Valor",
                    centavos=valor_unit,
                    price_basis=PriceBasisRascunho.EXCLUI_IOF,
                ),
                quantidade=ValorExtraido(id=f"q{faixa}", rotulo="Qtd", inteiro=0),
            )
        )
    return OpcaoCotacaoCandidata(
        id="op-test",
        tipo_fiscal=ValorExtraido(id="tf", rotulo="Tipo fiscal", texto="seguradora"),
        tabela=tabela,
    )


def test_html_totais_gerais_sem_uuid_e_com_nome_plano():
    rascunho = rascunho_demo_12_vidas()
    op_id = rascunho.opcoes_proposta[0].id
    nome_plano = rascunho.opcoes_proposta[0].plano_nome
    html = render_html(_vm_com_proposta(op_id, nome_plano))
    assert not _UUID_RE.search(html)
    assert nome_plano in html
    assert op_id not in html


def test_html_rotulos_totais_coincidem_com_tabelas_faixa():
    rascunho = rascunho_demo_12_vidas()
    op_id = rascunho.opcoes_proposta[0].id
    nome = rascunho.opcoes_proposta[0].plano_nome
    html = render_html(_vm_com_proposta(op_id, nome))
    assert html.count(nome) >= 2


def test_html_opcao_sem_plano_nome_usa_rotulo_numerado():
    op_id = str(uuid.uuid4())
    html = render_html(_vm_com_proposta(op_id, ""))
    assert "Proposta 1" in html
    assert op_id not in html


def test_estimativa_seguradora_exclui_iof_aplica_iof():
    opcao = _opcao_seguradora_exclui_iof()
    total = estimar_opcao_candidata(opcao, {0: 3})
    esperado = apply_rate_bps(100_000, 238) * 3
    assert total == esperado


def test_estimativa_operadora_sem_alteracao():
    opcao = _opcao_seguradora_exclui_iof()
    opcao.tipo_fiscal = ValorExtraido(id="tf", rotulo="Tipo fiscal", texto="operadora")
    total = estimar_opcao_candidata(opcao, {0: 4})
    assert total == 400_000


def test_estimativa_rascunho_igual_total_motor_demo_12():
    rascunho = rascunho_demo_12_vidas()
    data_ref = rascunho.escolhas.data_referencia_idade
    assert data_ref is not None
    quantidades: dict[int, int] = {}
    for vida in rascunho.vidas_incluidas():
        _, faixa = faixa_em(vida.nascimento, data_ref)
        quantidades[faixa] = quantidades.get(faixa, 0) + 1

    op = rascunho.opcoes_proposta[0]
    estimativa = estimar_opcao_rascunho(op, quantidades)
    assert estimativa is not None

    compilado = compile(rascunho)
    assert compilado.compilado is not None
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    total_motor = motor.cenarios[0].total_proposta_centavos
    centavos_motor = total_motor.centavos if hasattr(total_motor, "centavos") else total_motor
    assert estimativa == centavos_motor


def test_resumo_beneficiarios_apos_confirmar_lote(client: TestClient):
    client.post(
        "/api/estudos",
        json={"id": "cab-41", "titulo": "Cab 41", "nome_empresa": "Cab"},
    )
    _importar(client, "cab-41", planilha_41_vidas_2_planos())
    antes = client.get("/api/estudos/cab-41").json()
    assert antes["beneficiarios_incluidos"] == 0

    client.post("/api/estudos/cab-41/conferencia-siscor/confirmar-lote")
    depois = client.get("/api/estudos/cab-41").json()
    assert depois["beneficiarios_incluidos"] == 41
    assert depois["beneficiarios_rotulo"] == "41 beneficiários"


def test_resumo_atualiza_apos_exclusao(client: TestClient):
    client.post(
        "/api/estudos",
        json={"id": "cab-exc", "titulo": "Cab exc", "nome_empresa": "Cab"},
    )
    _importar(client, "cab-exc", planilha_12_vidas())
    client.post("/api/estudos/cab-exc/conferencia-siscor/confirmar-lote")
    assert client.get("/api/estudos/cab-exc").json()["beneficiarios_incluidos"] == 12

    conf = client.get("/api/estudos/cab-exc/conferencia-siscor").json()
    linha_id = conf["linhas"][0]["id"]
    client.patch(
        f"/api/estudos/cab-exc/conferencia-siscor/linhas/{linha_id}",
        json={"excluida": True, "motivo_exclusao": "Desligamento."},
    )
    resumo = client.get("/api/estudos/cab-exc").json()
    assert resumo["beneficiarios_incluidos"] == 11
