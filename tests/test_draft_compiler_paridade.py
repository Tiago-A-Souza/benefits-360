"""Testes de paridade do compilador — ETAPA 2.2."""

from __future__ import annotations

import json
import re
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
    EscolhasEstudo,
    PriceBasisRascunho,
    RascunhoEstudo,
)
from newport_app.models.compilation import ResultadoCompilacao
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


def _resumo_motor(rascunho: RascunhoEstudo) -> dict:
    compilado = compile(rascunho)
    assert compilado.compilavel and compilado.compilado is not None
    resultado = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    vidas = 0
    proposta = None
    if resultado.cenarios:
        cenario = resultado.cenarios[0]
        proposta = cenario.total_proposta_centavos.centavos
        for secao in cenario.secoes:
            vidas += sum(len(sg.vidas) for sg in secao.subgrupos)
    return {
        "proposta_total_centavos": proposta,
        "vidas_count": vidas,
        "tem_bloqueio": resultado.tem_bloqueio,
        "codigos_validacao": sorted({v.codigo for v in resultado.validacoes}),
    }


@pytest.mark.parametrize(
    ("seed_fn", "fixture_dir"),
    [
        (rascunho_demo_12_vidas, "demo_12"),
        (rascunho_demo_41_vidas, "demo_41"),
    ],
    ids=["P-01-demo-12", "P-02-demo-41"],
)
def test_paridade_compilacao_e_motor(seed_fn, fixture_dir: str):
    rascunho = seed_fn()
    base = FIXTURES / fixture_dir

    compilado = compile(rascunho)
    assert compilado.compilavel
    assert compilado.compilado is not None
    assert not compilado.erros

    policy_esperada = json.loads((base / "expected_policy.json").read_text(encoding="utf-8"))
    assert compilado.compilado.effective_policy.model_dump(mode="json") == policy_esperada

    motor_esperado = json.loads((base / "expected_motor.json").read_text(encoding="utf-8"))
    assert _resumo_motor(rascunho) == motor_esperado


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


def test_p07_nao_aplica_somente_operadora():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].tipo_fiscal = "operadora"
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
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


def test_p10_api_calcular_incompleto_retorna_422(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "api422.db")
    app = create_app(repo=repo)
    service = app.state.calculo_service
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.baseline_escolhido.confirmado = False
    service.salvar_rascunho(rascunho)
    client = TestClient(app)
    res = client.post("/api/estudos/demo-12/calcular")
    assert res.status_code == 422
    assert "compiler_versao" in res.json()["detail"]


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


def test_precedencia_nao_confirmada():
    rascunho = rascunho_demo_12_vidas()
    rascunho.escolhas.precedencia_atual_vida.confirmado = False
    resultado = compile(rascunho)
    assert any(e.codigo == "APP-ESC-003" for e in resultado.erros)


def test_aviso_validade_somente_com_documento():
    rascunho = rascunho_demo_12_vidas()
    resultado = compile(rascunho)
    assert not any(a.codigo == "APP-AVI-001" for a in resultado.avisos)


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
