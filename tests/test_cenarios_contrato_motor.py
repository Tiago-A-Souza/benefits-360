"""Contrato app ↔ motor para cenários multi-subgrupo e seguro novo."""

from __future__ import annotations

from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.adapters.motor_out import _detalhe_tecnico_bloqueio, _traduzir_validacao
from newport_app.api.main import create_app
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
)
from newport_app.models.responses import BloqueioComparativo
from newport_app.policy.registry import default_registry
from newport_app.rascunho.cenarios_sync import (
    cenarios_sincronizados,
    sincronizar_cenarios,
    subgrupos_com_vidas,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular
from newport_motor.result import MotorResult


def _rascunho_atef(n_opcoes: int = 4):
    base = rascunho_demo_12_vidas()
    opcoes: list[OpcaoPropostaRascunho] = []
    for i in range(n_opcoes):
        op = deepcopy(base.opcoes_proposta[0])
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Proposta {i + 1}"
        op.extracao_id = f"ext-{i + 1}" if i % 2 == 0 else None
        opcoes.append(op)
    base.opcoes_proposta = opcoes
    base.cenarios = []
    return base


def _rascunho_dois_subgrupos(n_opcoes: int = 2):
    base = _rascunho_atef(n_opcoes)
    sg2 = deepcopy(base.subgrupos_atuais[0])
    sg2.id = "sg-2"
    sg2.plano_nome = "Plano atual B"
    base.subgrupos_atuais.append(sg2)
    for i, vida in enumerate(base.vidas):
        if i >= len(base.vidas) // 2:
            vida.subgrupo_atual_id = "sg-2"
    base.cenarios = []
    from newport_app.rascunho.cenarios_sync import garantir_cenarios_uniformes_multi

    sincronizar_cenarios(base)
    garantir_cenarios_uniformes_multi(base)
    return base


def _rascunho_seguro_novo(n_vidas: int = 12, n_opcoes: int = 2):
    base = rascunho_demo_12_vidas()
    opcoes: list[OpcaoPropostaRascunho] = []
    for i in range(n_opcoes):
        op = deepcopy(base.opcoes_proposta[0])
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Proposta {i + 1}"
        op.tipo_fiscal = "operadora"
        opcoes.append(op)
    vidas = [
        v.model_copy(update={"id": f"v{i}", "subgrupo_atual_id": None, "valor_fatura": None})
        for i, v in enumerate(base.vidas[:n_vidas])
    ]
    return base.model_copy(
        update={
            "id": "novo-contrato",
            "formato": "novo",
            "titulo": "Seguro novo — contrato app/motor",
            "vidas": vidas,
            "subgrupos_atuais": [],
            "opcoes_proposta": opcoes,
            "cenarios": [],
            "escolhas": EscolhasEstudo(
                data_referencia_idade=date(2026, 6, 30),
                baseline_escolhido=CampoConfirmavelBaseline(),
                precedencia_atual_vida=CampoConfirmavelPrecedencia(),
            ),
        }
    )


def _estrutura_ui_antiga_quebrada(rascunho):
    """Dois cenários com uma atribuição cada — padrão da UI antes da correção."""
    base_cenario = rascunho_demo_12_vidas().cenarios[0]
    return [
        base_cenario.model_copy(
            update={
                "id": "c1",
                "atribuicoes": [
                    base_cenario.atribuicoes[0].model_copy(
                        update={"opcao_plano_id": "op-1", "alvo_id": "sg-1"}
                    )
                ],
            }
        ),
        base_cenario.model_copy(
            update={
                "id": "c2",
                "atribuicoes": [
                    base_cenario.atribuicoes[0].model_copy(
                        update={
                            "id": "a2",
                            "opcao_plano_id": "op-2",
                            "alvo_id": "sg-2",
                        }
                    )
                ],
            }
        ),
    ]


def _assert_invariante_sincronizado_sem_b06(rascunho) -> None:
    assert cenarios_sincronizados(rascunho), "Pré-condição: rascunho deve estar sincronizado"
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel, [e.mensagem for e in compilado.erros]
    assert compilado.compilado is not None
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    b06 = [v for v in motor.validacoes if v.codigo == "B-06"]
    assert not b06, [v.mensagem for v in b06]


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "contrato.db")


@pytest.fixture
def client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def test_estrutura_parcial_nao_sincronizada():
    rascunho = _rascunho_dois_subgrupos(2)
    rascunho.cenarios = _estrutura_ui_antiga_quebrada(rascunho)
    assert not cenarios_sincronizados(rascunho)


def test_estrutura_completa_sincronizada():
    rascunho = _rascunho_dois_subgrupos(2)
    sincronizar_cenarios(rascunho)
    assert cenarios_sincronizados(rascunho)
    assert len(rascunho.cenarios) == 2
    for i, cenario in enumerate(rascunho.cenarios):
        assert len(cenario.atribuicoes) == 2
        assert {a.alvo_id for a in cenario.atribuicoes} == {"sg-1", "sg-2"}
        assert all(a.opcao_plano_id == f"op-{i + 1}" for a in cenario.atribuicoes)


def test_invariante_sincronizado_implica_motor_sem_b06():
    rascunho = _rascunho_dois_subgrupos(3)
    sincronizar_cenarios(rascunho)
    _assert_invariante_sincronizado_sem_b06(rascunho)


def test_tres_propostas_dois_subgrupos_mesma_proposta_por_cenario(repo):
    rascunho = _rascunho_dois_subgrupos(3)
    sincronizar_cenarios(rascunho)
    repo.salvar_rascunho(rascunho)

    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert cenarios_sincronizados(salvo)
    assert len(salvo.cenarios) == 3
    assert sum(len(c.atribuicoes) for c in salvo.cenarios) == 6

    _assert_invariante_sincronizado_sem_b06(salvo)
    resp = CalculoService(repo).calcular(rascunho.id)
    assert resp.calculo_realizado is True
    assert not any(b.codigo == "B-06" for b in resp.consistencia.bloqueios)


def test_combo_misto_rotulo_pacote(repo):
    rascunho = _rascunho_dois_subgrupos(2)
    op2 = deepcopy(rascunho.opcoes_proposta[0])
    op2.id = "op-2"
    op2.plano_nome = "Proposta B"
    op2.regime_copart_id = "regime-parcial"
    rascunho.opcoes_proposta[1] = op2
    if not any(r.id == "regime-parcial" for r in rascunho.regimes_copart):
        from newport_app.models.draft import RegimeCopartRascunho

        rascunho.regimes_copart.append(
            RegimeCopartRascunho(id="regime-parcial", tipo="parcial")
        )

    sincronizar_cenarios(rascunho)
    c0 = rascunho.cenarios[0]
    atribuicoes = [
        c0.atribuicoes[0].model_copy(update={"opcao_plano_id": "op-1"}),
        c0.atribuicoes[1].model_copy(update={"opcao_plano_id": "op-2"}),
    ]
    rascunho.cenarios[0] = c0.model_copy(update={"atribuicoes": atribuicoes})

    assert cenarios_sincronizados(rascunho)
    _assert_invariante_sincronizado_sem_b06(rascunho)

    repo.salvar_rascunho(rascunho)
    resp = CalculoService(repo).calcular(rascunho.id)
    assert resp.calculo_realizado is True
    assert resp.propostas[0].plano_nome == "Proposta 1 + Proposta B"
    assert resp.propostas[0].regime_coparticipacao == "Pacote misto"


def test_subgrupo_sem_vidas_nao_exige_atribuicao():
    rascunho = _rascunho_dois_subgrupos(2)
    sg3 = deepcopy(rascunho.subgrupos_atuais[0])
    sg3.id = "sg-3"
    sg3.plano_nome = "Plano sem vidas"
    rascunho.subgrupos_atuais.append(sg3)

    sincronizar_cenarios(rascunho)
    assert cenarios_sincronizados(rascunho)
    assert subgrupos_com_vidas(rascunho) == ["sg-1", "sg-2"]
    for cenario in rascunho.cenarios:
        assert "sg-3" not in {a.alvo_id for a in cenario.atribuicoes}

    _assert_invariante_sincronizado_sem_b06(rascunho)


def test_unico_subgrupo_sem_regressao(repo):
    rascunho = _rascunho_atef(4)
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert cenarios_sincronizados(salvo)
    assert len(salvo.cenarios) == 4
    _assert_invariante_sincronizado_sem_b06(salvo)


def test_api_multi_subgrupo_calcular_sem_bloqueio(client: TestClient, repo):
    rascunho = _rascunho_dois_subgrupos(3)
    rascunho.id = "multi-3x2"
    repo.salvar_rascunho(rascunho)

    res = client.post(f"/api/estudos/{rascunho.id}/calcular")
    assert res.status_code == 200
    data = res.json()
    assert data["calculo_realizado"] is True
    assert not any(b["codigo"] == "B-06" for b in data["consistencia"]["bloqueios"])


def test_estrutura_antiga_gera_b06_no_motor():
    rascunho = _rascunho_dois_subgrupos(2)
    rascunho.cenarios = _estrutura_ui_antiga_quebrada(rascunho)
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel
    assert compilado.compilado is not None
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    b06 = [v for v in motor.validacoes if v.codigo == "B-06"]
    assert b06


def test_seguro_novo_12_vidas_2_propostas_sem_bloqueio(repo):
    rascunho = _rascunho_seguro_novo(12, 2)
    sincronizar_cenarios(rascunho)
    assert cenarios_sincronizados(rascunho)
    assert len(rascunho.cenarios) == 2
    assert sum(len(c.atribuicoes) for c in rascunho.cenarios) == 24
    for cenario in rascunho.cenarios:
        assert all(a.alvo_tipo == "vida" for a in cenario.atribuicoes)
        assert {a.alvo_id for a in cenario.atribuicoes} == {f"v{i}" for i in range(12)}

    _assert_invariante_sincronizado_sem_b06(rascunho)
    repo.salvar_rascunho(rascunho)
    resp = CalculoService(repo).calcular(rascunho.id)
    assert resp.calculo_realizado is True
    assert not any(b.codigo == "B-06" for b in resp.consistencia.bloqueios)


def test_seguro_novo_compila_sem_baseline_nem_precedencia():
    rascunho = _rascunho_seguro_novo(3, 1)
    sincronizar_cenarios(rascunho)
    assert rascunho.escolhas.baseline_escolhido.valor is None
    assert rascunho.escolhas.precedencia_atual_vida.valor is None
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel, [e.mensagem for e in compilado.erros]
    assert not any(e.codigo in ("APP-ESC-002", "APP-ESC-003") for e in compilado.erros)
    assert compilado.compilado is not None
    assert compilado.compilado.effective_policy.baseline_escolhido is None
    assert compilado.compilado.effective_policy.precedencia_atual_vida is None
    _assert_invariante_sincronizado_sem_b06(rascunho)


def test_seguro_novo_com_subgrupos_siscor_ignora_plano_vigente():
    """Base SISCOR pode criar subgrupos; em seguro novo o alvo continua sendo a vida."""
    rascunho = _rascunho_seguro_novo(4, 1)
    sg = deepcopy(rascunho_demo_12_vidas().subgrupos_atuais[0])
    sg.id = "sg-siscor"
    rascunho.subgrupos_atuais = [sg]
    for vida in rascunho.vidas:
        vida.subgrupo_atual_id = "sg-siscor"
    sincronizar_cenarios(rascunho)
    assert cenarios_sincronizados(rascunho)
    assert all(a.alvo_tipo == "vida" for c in rascunho.cenarios for a in c.atribuicoes)
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel
    assert compilado.compilado is not None
    assert compilado.compilado.estudo_input.subgrupos_atuais == []
    _assert_invariante_sincronizado_sem_b06(rascunho)


def test_b06_orientacao_depende_do_formato():
    rascunho_novo = _rascunho_seguro_novo(1, 1)
    rascunho_ren = rascunho_demo_12_vidas()
    motor_vazio = MotorResult(estudo_id="x")
    trad_novo = _traduzir_validacao("B-06", "falta", rascunho_novo, motor_vazio)
    trad_ren = _traduzir_validacao("B-06", "falta", rascunho_ren, motor_vazio)
    assert "vidas" in (trad_novo.acao_sugerida or "").lower()
    assert "grupos" in (trad_ren.acao_sugerida or "").lower()


def test_detalhe_tecnico_preserva_todos_os_itens_do_grupo():
    items = [
        BloqueioComparativo(
            codigo="B-07",
            mensagem="msg humana 1",
            mensagem_motor="motor bruto um",
            severidade="bloqueante",
            alvo_ref="subgrupo:sg-a",
            origem="motor",
        ),
        BloqueioComparativo(
            codigo="B-07",
            mensagem="msg humana 2",
            mensagem_motor="motor bruto dois",
            severidade="bloqueante",
            alvo_ref="subgrupo:sg-b",
            origem="motor",
        ),
    ]
    detalhe = _detalhe_tecnico_bloqueio(items)
    assert detalhe is not None
    assert "subgrupo:sg-a" in detalhe
    assert "subgrupo:sg-b" in detalhe
    assert "motor bruto um" in detalhe
    assert "motor bruto dois" in detalhe

    unico = _detalhe_tecnico_bloqueio(items[:1])
    assert unico is not None
    assert "motor bruto um" in unico
