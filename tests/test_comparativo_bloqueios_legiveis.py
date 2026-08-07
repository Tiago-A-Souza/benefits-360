"""Mensagens de bloqueio legíveis e agrupadas por (codigo, alvo)."""

from __future__ import annotations

from datetime import date

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    SubgrupoAtualRascunho,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_motor.engine import calcular
from newport_motor.models import AtribuicaoPlano, Cenario, EstudoInput
from newport_motor.result import MotorResult, Validacao
from newport_motor.types import FormatoEstudo, RegimeCopartTipo, SeveridadeValidacao
from tests.conftest import opcao_plano, policy_completa, regime, subgrupo_atual, vida_ficticia


def _rascunho_dois_subgrupos():
    base = rascunho_demo_12_vidas()
    tpl = base.subgrupos_atuais[0]
    return base.model_copy(
        update={
            "subgrupos_atuais": [
                tpl.model_copy(
                    update={"id": "sg-a", "plano_nome": "AMIL S750 - Apto.", "reajuste_bps": None}
                ),
                tpl.model_copy(
                    update={
                        "id": "sg-b",
                        "plano_nome": "AMIL ONE S2500 - Apto.",
                        "reajuste_bps": None,
                    }
                ),
            ]
        }
    )


def test_dois_subgrupos_sem_reajuste_mensagens_distintas_sem_uuid():
    rascunho = _rascunho_dois_subgrupos()
    reg = regime(RegimeCopartTipo.SEM)
    v1 = vida_ficticia("v1", date(1990, 1, 1), "sg-a")
    v2 = vida_ficticia("v2", date(1988, 1, 1), "sg-b")
    op = opcao_plano("op-1")
    sg_a = subgrupo_atual("sg-a").model_copy(update={"reajuste_bps": None})
    sg_b = subgrupo_atual("sg-b").model_copy(
        update={"reajuste_bps": None, "plano_nome": "AMIL ONE S2500 - Apto."}
    )
    cenario = Cenario(
        id="c1",
        atribuicoes=[
            AtribuicaoPlano(id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-1"),
            AtribuicaoPlano(id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-1"),
        ],
    )
    estudo = EstudoInput(
        id="estudo-b07",
        formato=FormatoEstudo.RENOVACAO,
        vidas=[v1, v2],
        subgrupos_atuais=[sg_a, sg_b],
        opcoes_plano=[op],
        regimes_copart=[reg],
        cenarios=[cenario],
    )
    motor = calcular(estudo, policy_completa())
    resp = montar_comparativo(rascunho, motor_result=motor)

    bloqueios_b07 = [b for b in resp.consistencia.bloqueios if b.codigo == "B-07"]
    assert len(bloqueios_b07) == 2
    rotulos = {b.alvo_rotulo for b in bloqueios_b07}
    assert rotulos == {"AMIL S750 - Apto.", "AMIL ONE S2500 - Apto."}
    for bloqueio in bloqueios_b07:
        assert "sg-a" not in bloqueio.mensagem
        assert "sg-b" not in bloqueio.mensagem
        assert "«AMIL" in bloqueio.mensagem
        assert bloqueio.detalhe_tecnico
        assert "motor:" in bloqueio.detalhe_tecnico


def test_b06_tres_cenarios_agrupados_em_um_item():
    rascunho = rascunho_demo_12_vidas()
    alvo_id = "sg-extra"
    tpl = rascunho.subgrupos_atuais[0]
    rascunho.subgrupos_atuais.append(
        tpl.model_copy(
            update={
                "id": alvo_id,
                "plano_nome": "AMIL ONE S2500 - Apto.",
            }
        )
    )
    for vida in rascunho.vidas[6:]:
        vida.subgrupo_atual_id = alvo_id

    op_id = rascunho.opcoes_proposta[0].id
    sg_principal = rascunho.subgrupos_atuais[0].id
    rascunho.cenarios = [
        CenarioRascunho(
            id=f"c{i}",
            rotulo=f"Cenário {i}",
            atribuicoes=[
                AtribuicaoRascunho(
                    id=f"a{i}a",
                    alvo_tipo="subgrupo",
                    alvo_id=sg_principal,
                    opcao_plano_id=op_id,
                )
            ],
        )
        for i in range(1, 4)
    ]

    compilado = compile(rascunho)
    assert compilado.compilavel
    motor = calcular(
        compilado.compilado.estudo_input,
        compilado.compilado.effective_policy,
    )
    resp = montar_comparativo(rascunho, motor_result=motor)

    bloqueios_b06 = [b for b in resp.consistencia.bloqueios if b.codigo == "B-06"]
    assert len(bloqueios_b06) == 1
    b06 = bloqueios_b06[0]
    assert b06.quantidade == 3
    assert b06.mensagem == "Sem atribuição em 3 cenários."
    assert b06.alvo_rotulo == "AMIL ONE S2500 - Apto."
    assert alvo_id not in b06.mensagem


def test_alvo_sem_nome_resolvivel_exibe_id():
    alvo_id = "sg-desconhecido-xyz"
    rascunho = rascunho_demo_12_vidas()
    motor = MotorResult(
        estudo_id=rascunho.id,
        validacoes=[
            Validacao(
                codigo="B-06",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem=f"Alvo {alvo_id} sem atribuição no cenário c1.",
                alvo_ref=f"cenario:c1:alvo:{alvo_id}",
            )
        ],
    )
    resp = montar_comparativo(rascunho, motor_result=motor)
    bloqueio = resp.consistencia.bloqueios[0]
    assert alvo_id in bloqueio.mensagem or alvo_id in (bloqueio.detalhe_tecnico or "")
    assert bloqueio.alvo_rotulo == alvo_id
    assert bloqueio.detalhe_tecnico
