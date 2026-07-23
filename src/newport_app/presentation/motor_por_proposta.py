"""Recálculo por proposta a partir do snapshot — sem alterar regras do motor."""

from __future__ import annotations

from dataclasses import dataclass, field

from newport_app.draft_compiler import compile
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.snapshot import SnapshotCalculo
from newport_app.policy.registry import PolicySetRegistry, default_registry
from newport_motor.engine import calcular
from newport_motor.result import MotorResult


class PropostaNaoCalculavelError(Exception):
    def __init__(self, opcoes_invalidas: list[str]) -> None:
        self.opcoes_invalidas = opcoes_invalidas
        super().__init__(
            f"Propostas não calculáveis para apresentação: {', '.join(opcoes_invalidas)}"
        )


@dataclass
class VidaCalculoProposta:
    vida_id: str
    faixa: int | None
    idade: int | None
    vigente_centavos: int | None
    reajustado_centavos: int | None
    proposta_centavos: int | None
    diff_mes_centavos: int | None
    regime_tipo: str
    subgrupo_id: str


@dataclass
class SecaoCalculoProposta:
    regime_tipo: str
    rotulo: str
    total_atual_baseline_centavos: int | None
    total_proposta_centavos: int | None
    diff_mes_centavos: int | None
    diff_ano_centavos: int | None
    vidas: dict[str, VidaCalculoProposta] = field(default_factory=dict)


@dataclass
class CalculoProposta:
    opcao_id: str
    secoes: list[SecaoCalculoProposta]
    total_atual_centavos: int | None
    total_proposta_centavos: int | None
    diff_mes_centavos: int | None
    diff_ano_centavos: int | None


def _atribuir_proposta_unica(rascunho: RascunhoEstudo, opcao_id: str) -> RascunhoEstudo:
    copia = rascunho.model_copy(deep=True)
    if not copia.cenarios:
        return copia
    cenario = copia.cenarios[0]
    for atr in cenario.atribuicoes:
        if atr.alvo_tipo == "subgrupo":
            atr.opcao_plano_id = opcao_id
    return copia


def _extrair_calculo(motor: MotorResult, opcao_id: str) -> CalculoProposta:
    secoes: list[SecaoCalculoProposta] = []
    if not motor.cenarios:
        return CalculoProposta(
            opcao_id=opcao_id,
            secoes=[],
            total_atual_centavos=None,
            total_proposta_centavos=None,
            diff_mes_centavos=None,
            diff_ano_centavos=None,
        )
    cenario = motor.cenarios[0]
    for secao in cenario.secoes:
        vidas_map: dict[str, VidaCalculoProposta] = {}
        for sg in secao.subgrupos:
            for rv in sg.vidas:
                vidas_map[rv.vida_id] = VidaCalculoProposta(
                    vida_id=rv.vida_id,
                    faixa=rv.faixa,
                    idade=rv.idade,
                    vigente_centavos=(
                        rv.atual_vigente_centavos.centavos
                        if rv.atual_vigente_centavos
                        else None
                    ),
                    reajustado_centavos=(
                        rv.atual_reajustado_centavos.centavos
                        if rv.atual_reajustado_centavos
                        else None
                    ),
                    proposta_centavos=(
                        rv.proposta_centavos.centavos if rv.proposta_centavos else None
                    ),
                    diff_mes_centavos=(
                        rv.diff_mes_centavos.centavos if rv.diff_mes_centavos else None
                    ),
                    regime_tipo=secao.regime_tipo.value,
                    subgrupo_id=sg.subgrupo_id,
                )
        secoes.append(
            SecaoCalculoProposta(
                regime_tipo=secao.regime_tipo.value,
                rotulo=secao.rotulo_derivado or secao.regime_tipo.value,
                total_atual_baseline_centavos=(
                    secao.total_atual_baseline_centavos.centavos
                    if secao.total_atual_baseline_centavos
                    else None
                ),
                total_proposta_centavos=(
                    secao.total_proposta_centavos.centavos
                    if secao.total_proposta_centavos
                    else None
                ),
                diff_mes_centavos=(
                    secao.diff_mes_centavos.centavos if secao.diff_mes_centavos else None
                ),
                diff_ano_centavos=(
                    secao.diff_ano_centavos.centavos if secao.diff_ano_centavos else None
                ),
                vidas=vidas_map,
            )
        )
    return CalculoProposta(
        opcao_id=opcao_id,
        secoes=secoes,
        total_atual_centavos=(
            cenario.total_atual_baseline_centavos.centavos
            if cenario.total_atual_baseline_centavos
            else None
        ),
        total_proposta_centavos=(
            cenario.total_proposta_centavos.centavos if cenario.total_proposta_centavos else None
        ),
        diff_mes_centavos=(
            cenario.diff_mes_centavos.centavos if cenario.diff_mes_centavos else None
        ),
        diff_ano_centavos=(
            cenario.diff_ano_centavos.centavos if cenario.diff_ano_centavos else None
        ),
    )


def calcular_propostas_do_snapshot(
    snap: SnapshotCalculo,
    opcao_ids: list[str],
    *,
    policy_registry: PolicySetRegistry | None = None,
) -> dict[str, CalculoProposta]:
    rascunho = RascunhoEstudo.model_validate(snap.payload["rascunho"])
    registry = policy_registry or default_registry
    opcoes_validas = {o.id for o in rascunho.opcoes_proposta}
    invalidas = [oid for oid in opcao_ids if oid not in opcoes_validas]
    if invalidas:
        raise PropostaNaoCalculavelError(invalidas)

    resultados: dict[str, CalculoProposta] = {}
    falhas: list[str] = []
    for op_id in opcao_ids:
        r_atrib = _atribuir_proposta_unica(rascunho, op_id)
        compilado = compile(r_atrib, policy_registry=registry)
        if not compilado.compilavel:
            falhas.append(op_id)
            continue
        assert compilado.compilado is not None
        motor = calcular(
            compilado.compilado.estudo_input,
            compilado.compilado.effective_policy,
        )
        if motor.tem_bloqueio:
            falhas.append(op_id)
            continue
        resultados[op_id] = _extrair_calculo(motor, op_id)

    if falhas:
        raise PropostaNaoCalculavelError(falhas)
    return resultados


def calcular_atual_do_snapshot(snap: SnapshotCalculo) -> CalculoProposta:
    motor = MotorResult.model_validate(snap.payload["motor_result"])
    cenario_id = snap.payload.get("rascunho", {}).get("cenarios", [{}])[0].get("id", "c1")
    op_id = (
        snap.payload.get("rascunho", {})
        .get("cenarios", [{}])[0]
        .get("atribuicoes", [{}])[0]
        .get("opcao_plano_id", "atual")
    )
    calc = _extrair_calculo(motor, op_id)
    calc.opcao_id = cenario_id
    return calc
