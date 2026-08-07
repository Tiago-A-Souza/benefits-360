"""Testes de paridade integral e endurecimento — ETAPA 2.2.6."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.draft_compiler import compile
from newport_app.draft_compiler.structural import RascunhoEstruturalInvalidoError
from newport_app.models.compilation import ResultadoCompilacao
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    ComponenteFinanceiroRascunho,
    CustoUnicoRascunho,
    DocumentoCotacaoRascunho,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
    TabelaFaixaRascunho,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas, rascunho_demo_41_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular
from newport_motor.types import SeveridadeValidacao

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "rascunhos"

SENSIVEL = re.compile(
    r"(benefici[aá]rio|R\$|\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)


def _carregar_json(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _carregar_rascunho(fixture_dir: str) -> RascunhoEstudo:
    return RascunhoEstudo.model_validate(_carregar_json(FIXTURES / fixture_dir / "rascunho.json"))


@pytest.mark.parametrize("fixture_dir", ["demo_12", "demo_41"])
def test_paridade_integral_por_fixture(fixture_dir: str):
    rascunho = _carregar_rascunho(fixture_dir)
    base = FIXTURES / fixture_dir

    resultado = compile(rascunho)
    assert resultado.compilavel, resultado.erros
    assert resultado.compilado is not None

    assert (
        resultado.compilado.effective_policy.model_dump(mode="json")
        == _carregar_json(base / "expected_policy.json")
    )
    assert (
        resultado.compilado.estudo_input.model_dump(mode="json")
        == _carregar_json(base / "expected_estudo_input.json")
    )

    motor = calcular(
        resultado.compilado.estudo_input,
        resultado.compilado.effective_policy,
    )
    assert motor.model_dump(mode="json") == _carregar_json(base / "expected_motor_result.json")


@pytest.mark.parametrize(
    ("seed_fn", "fixture_dir"),
    [
        (rascunho_demo_12_vidas, "demo_12"),
        (rascunho_demo_41_vidas, "demo_41"),
    ],
)
def test_seed_igual_fixture_rascunho(seed_fn, fixture_dir: str):
    seed = seed_fn().model_dump(mode="json")
    fixture = _carregar_json(FIXTURES / fixture_dir / "rascunho.json")
    assert seed == fixture


def test_p03_baseline_nao_confirmada_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.baseline_escolhido.confirmado = False
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-ESC-002" for e in resultado.erros)


def test_p04_data_referencia_ausente():
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.data_referencia_idade = None
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-ESC-001" for e in resultado.erros)


def test_p05_policy_set_inexistente():
    rascunho = rascunho_demo_12_vidas()
    rascunho.policy_set_versao = "versao-inexistente"
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-POL-001" for e in resultado.erros)


def test_p06_price_basis_por_faixa():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].price_basis = PriceBasisRascunho.INCLUI_IOF
    rascunho.opcoes_proposta[0].tabela[1].price_basis = PriceBasisRascunho.EXCLUI_IOF
    compilado = compile(rascunho)
    assert compilado.compilavel
    tabela = compilado.compilado.estudo_input.opcoes_plano[0].tabela  # type: ignore[union-attr]
    assert tabela[0].price_basis.value == "inclui_iof"
    assert tabela[1].price_basis.value == "exclui_iof"


def test_tabela_sem_price_basis_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].price_basis = PriceBasisRascunho.DESCONHECIDO
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-FIN-001" for e in resultado.erros)


def test_tabela_nao_confirmada_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].proveniencia.confirmado = False
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-FIN-002" for e in resultado.erros)


def test_custo_zero_explicito_compila():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].custos_unicos = [
        CustoUnicoRascunho(
            id="cu-1",
            descricao="Taxa fictícia",
            valor=ComponenteFinanceiroRascunho(
                centavos=0,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                proveniencia=ProvenienciaRascunho(
                    origem=OrigemValorRascunho.MANUAL,
                    confirmado=True,
                ),
            ),
        )
    ]
    resultado = compile(rascunho)
    assert resultado.compilavel
    custos = resultado.compilado.estudo_input.opcoes_plano[0].custos_unicos  # type: ignore[union-attr]
    assert custos[0].valor_centavos == 0


def test_custo_sem_valor_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].custos_unicos = [
        CustoUnicoRascunho(
            id="cu-1",
            descricao="Taxa fictícia",
            valor=ComponenteFinanceiroRascunho(
                centavos=None,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                proveniencia=ProvenienciaRascunho(
                    origem=OrigemValorRascunho.MANUAL,
                    confirmado=True,
                ),
            ),
        )
    ]
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-FIN-003" for e in resultado.erros)


def test_quantidade_zero_explicita_compila():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].quantidade_cotada = 0
    assert compile(rascunho).compilavel


def test_quantidade_ausente_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta[0].tabela[0].quantidade_cotada = None
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-QTD-001" for e in resultado.erros)


def test_documento_vinculado_no_estudo_input():
    rascunho = rascunho_demo_12_vidas()
    rascunho.documentos_cotacao = [
        DocumentoCotacaoRascunho(
            id="doc-1",
            operadora="Operadora Demo",
            estado_extracao="manual",
            parser_versao="manual@demo",
        )
    ]
    rascunho.opcoes_proposta[0].documento_cotacao_id = "doc-1"
    compilado = compile(rascunho)
    assert compilado.compilavel
    docs = compilado.compilado.estudo_input.documentos  # type: ignore[union-attr]
    assert len(docs) == 1
    assert docs[0].id == "doc-1"
    assert compilado.compilado.estudo_input.documento_por_id("doc-1") is not None  # type: ignore[union-attr]


def test_documento_pendente_bloqueia_compilacao():
    rascunho = rascunho_demo_12_vidas()
    rascunho.documentos_cotacao = [
        DocumentoCotacaoRascunho(
            id="doc-p",
            operadora="Operadora Demo",
            estado_extracao="pendente",
        )
    ]
    rascunho.opcoes_proposta[0].documento_cotacao_id = "doc-p"
    resultado = compile(rascunho)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-DOC-001" for e in resultado.erros)


def test_p07_nao_aplica_somente_operadora():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].tipo_fiscal = "operadora"
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    rascunho.opcoes_proposta[0].tipo_fiscal = "operadora"
    for faixa in rascunho.opcoes_proposta[0].tabela:
        faixa.price_basis = PriceBasisRascunho.NAO_APLICA
    compilado = compile(rascunho)
    assert compilado.compilavel
    assert (
        compilado.compilado.estudo_input.subgrupos_atuais[0].fatura_price_basis.value  # type: ignore[union-attr]
        == "exclui_iof"
    )

    rascunho_seg = rascunho_demo_12_vidas()
    rascunho_seg.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    resultado = compile(rascunho_seg)
    assert resultado.compilado is None
    assert any(e.codigo == "APP-BAS-001" for e in resultado.erros)


def test_p08_ids_duplicados_rejeitados_ao_salvar(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "dup.db")
    service = CalculoService(repo)
    rascunho = rascunho_demo_12_vidas()
    rascunho.vidas[1].id = rascunho.vidas[0].id
    with pytest.raises(RascunhoEstruturalInvalidoError) as exc:
        service.salvar_rascunho(rascunho)
    assert any(e.codigo == "APP-STR-001" for e in exc.value.erros)


def test_p08b_salvar_incompleto_permitido(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "inc.db")
    service = CalculoService(repo)
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas = EscolhasEstudo(
        data_referencia_idade=None,
        baseline_escolhido=CampoConfirmavelBaseline(valor=None, confirmado=False),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(valor=None, confirmado=False),
    )
    service.salvar_rascunho(rascunho)
    carregado = repo.obter_rascunho("demo-12")
    assert carregado is not None
    assert carregado.escolhas.baseline_escolhido.confirmado is False


def test_p09_invariante_resultado_compilacao():
    with pytest.raises(ValueError, match="compilado"):
        ResultadoCompilacao(compilado=None, erros=[], avisos=[])


def test_p10_api_calcular_incompleto_retorna_comparativo_com_bloqueios(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "api422.db")
    app = create_app(repo=repo)
    service = app.state.calculo_service
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.baseline_escolhido.confirmado = False
    service.salvar_rascunho(rascunho)
    client = TestClient(app)
    res = client.post("/api/estudos/demo-12/calcular")
    assert res.status_code == 200
    body = res.json()
    assert body["calculo_realizado"] is False
    assert any(b["codigo"] == "APP-ESC-002" for b in body["consistencia"]["bloqueios"])


def test_p11_api_salvar_incompleto_retorna_200(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "api200.db")
    app = create_app(repo=repo)
    client = TestClient(app)
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.precedencia_atual_vida.confirmado = False
    res = client.put("/api/estudos/demo-12", json=rascunho.model_dump(mode="json"))
    assert res.status_code == 200


def test_p12_mensagens_sem_pii_nem_valores():
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.data_referencia_idade = None
    rascunho.vidas[0].nome = "Nome Sensível Teste"
    resultado = compile(rascunho)
    for erro in resultado.erros:
        assert "Nome Sensível" not in erro.mensagem
        assert not SENSIVEL.search(erro.mensagem)


def test_erro_pydantic_sem_pii(tmp_path: Path):
    app = create_app(repo=SQLiteStudyRepository(tmp_path / "pyd.db"))
    client = TestClient(app)
    payload = rascunho_demo_12_vidas().model_dump(mode="json")
    del payload["rascunho_versao"]
    payload["vidas"][0]["nome"] = "Segredo Beneficiário"
    payload["vidas"][0]["nascimento"] = "1980-05-01"
    res = client.put("/api/estudos/demo-12", json=payload)
    assert res.status_code == 422
    corpo = json.dumps(res.json(), ensure_ascii=False)
    assert "Segredo Beneficiário" not in corpo
    assert "1980-05-01" not in corpo
    assert "input" not in corpo.lower()
    assert res.json()["erros"][0]["codigo"] == "APP-REQ-001"


def test_rascunho_versao_ausente_rejeitada(tmp_path: Path):
    app = create_app(repo=SQLiteStudyRepository(tmp_path / "ver.db"))
    client = TestClient(app)
    payload = rascunho_demo_12_vidas().model_dump(mode="json")
    del payload["rascunho_versao"]
    res = client.put("/api/estudos/demo-12", json=payload)
    assert res.status_code == 422
    assert any(e["caminho"].endswith("rascunho_versao") for e in res.json()["erros"])


def test_politica_h01_do_motor_result(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "h01.db")
    service = CalculoService(repo)
    service.garantir_rascunho(rascunho_demo_41_vidas())
    out = service.calcular("demo-41")
    alertas = [p for p in out.pendencias if p.tipo == "alerta"]
    assert len(alertas) >= 1
    assert "41 vidas" in alertas[0].descricao
    assert "29 vidas" in alertas[0].descricao


def test_precedencia_nao_confirmada():
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.precedencia_atual_vida.confirmado = False
    resultado = compile(rascunho)
    assert any(e.codigo == "APP-ESC-003" for e in resultado.erros)


def test_aviso_validade_somente_com_documento():
    rascunho = rascunho_demo_12_vidas()
    rascunho.documentos_cotacao = [
        DocumentoCotacaoRascunho(
            id="doc-1",
            operadora="Operadora Demo",
            estado_extracao="manual",
        )
    ]
    rascunho.opcoes_proposta[0].documento_cotacao_id = "doc-1"
    resultado = compile(rascunho)
    assert any(a.codigo == "APP-AVI-001" for a in resultado.avisos)


def test_metadados_pptx_ausentes_sem_aviso():
    rascunho = rascunho_demo_12_vidas()
    rascunho.metadados_pptx = None
    resultado = compile(rascunho)
    assert resultado.compilavel
    assert not resultado.avisos


def test_empresa_ficticia_nos_demos():
    r = rascunho_demo_12_vidas()
    assert r.empresa_cliente is not None
    assert r.empresa_cliente.nome == "Empresa Demonstração Ltda."


def test_h01_vem_do_motor_nao_do_compilador():
    rascunho = rascunho_demo_41_vidas()
    compilado = compile(rascunho)
    assert compilado.compilavel
    assert not any("H-01" in e.codigo for e in compilado.erros)
    motor = calcular(
        compilado.compilado.estudo_input,  # type: ignore[union-attr]
        compilado.compilado.effective_policy,  # type: ignore[union-attr]
    )
    assert any(
        v.codigo == "H-01" and v.severidade == SeveridadeValidacao.ALERTA
        for v in motor.validacoes
    )
