"""Lógica de cálculo financeiro por vida, subgrupo e cenário."""

from __future__ import annotations

from newport_motor.faixa import faixa_em
from newport_motor.iof import tipo_fiscal_aplica_iof, valores_vidas_com_iof
from newport_motor.models import EstudoInput, OpcaoPlano, SubgrupoAtual, Vida
from newport_motor.money import apply_rate_bps
from newport_motor.policy import EffectivePolicy
from newport_motor.reconciliation import valor_calc
from newport_motor.result import ResultadoSubgrupo, ResultadoVida, ScenarioResult, ScenarioSectionResult
from newport_motor.types import (
    BaselineEscolhido,
    FormatoEstudo,
    MoneyCents,
    RegimeCopartTipo,
)


def _valor_faixa_tabela(opcao: OpcaoPlano, faixa: int) -> int:
    entry = next(t for t in opcao.tabela if t.faixa == faixa)
    return entry.valor_centavos


def _calcular_atual_vida(
    vida: Vida,
    subgrupo: SubgrupoAtual,
    faixa: int,
    policy: EffectivePolicy,
) -> tuple[int, int]:
    """Retorna (vigente, reajustado) em centavos com IOF conforme tipo fiscal."""
    if subgrupo.tabela_atual:
        base = next(
            (t.valor_centavos for t in subgrupo.tabela_atual if t.faixa == faixa),
            0,
        )
    elif vida.valor_fatura_centavos is not None:
        base = vida.valor_fatura_centavos
    else:
        return 0, 0

    aplica_iof = tipo_fiscal_aplica_iof(subgrupo.tipo_fiscal)
    valores_iof = valores_vidas_com_iof(
        [base], aplica_iof, policy.iof_bps, policy.estrategia_arredondamento
    )
    vigente = int(valores_iof[0])

    if subgrupo.reajuste_bps is None:
        return vigente, vigente
    reajustado = apply_rate_bps(vigente, subgrupo.reajuste_bps)
    return vigente, reajustado


def _calcular_proposta_vida(
    opcao: OpcaoPlano,
    faixa: int,
    policy: EffectivePolicy,
) -> int:
    base = _valor_faixa_tabela(opcao, faixa)
    aplica_iof = tipo_fiscal_aplica_iof(opcao.tipo_fiscal)
    valores_iof = valores_vidas_com_iof(
        [base], aplica_iof, policy.iof_bps, policy.estrategia_arredondamento
    )
    return int(valores_iof[0])


def _rotulo_regime(tipo: RegimeCopartTipo) -> str:
    mapa = {
        RegimeCopartTipo.SEM: "sem_copart",
        RegimeCopartTipo.PARCIAL: "copart_parcial",
        RegimeCopartTipo.PERCENTUAL: "com_copart",
        RegimeCopartTipo.CUSTOMIZADA: "copart_customizada",
    }
    return mapa[tipo]


def calcular_cenario(
    estudo: EstudoInput,
    cenario_id: str,
    atribuicoes: dict[str, str],
    policy: EffectivePolicy,
) -> ScenarioResult:
    baseline = (
        policy.baseline_escolhido.value
        if policy.baseline_escolhido
        else BaselineEscolhido.REAJUSTADO.value
    )

    # Agrupa subgrupos/vidas por regime da opção atribuída
    secoes_map: dict[RegimeCopartTipo, ScenarioSectionResult] = {}

    if estudo.formato == FormatoEstudo.RENOVACAO:
        subgrupos_processados: set[str] = set()
        for vida in estudo.vidas_incluidas():
            sg_id = vida.subgrupo_atual_id
            if not sg_id or sg_id in subgrupos_processados:
                continue
            subgrupos_processados.add(sg_id)
            opcao_id = atribuicoes.get(sg_id)
            if not opcao_id:
                continue
            opcao = estudo.opcao_por_id(opcao_id)
            subgrupo = estudo.subgrupo_por_id(sg_id)
            if not opcao or not subgrupo:
                continue
            regime = estudo.regime_por_id(opcao.regime_copart_id)
            if not regime:
                continue
            if regime.tipo not in secoes_map:
                secoes_map[regime.tipo] = ScenarioSectionResult(
                    regime_tipo=regime.tipo,
                    rotulo_derivado=_rotulo_regime(regime.tipo),
                )
            resultado_sg = _calcular_subgrupo_renovacao(
                estudo, subgrupo, opcao, policy
            )
            secoes_map[regime.tipo].subgrupos.append(resultado_sg)
    else:
        # Novo negócio: agrupa vidas por opção atribuída
        vidas_por_opcao: dict[str, list[Vida]] = {}
        for vida in estudo.vidas_incluidas():
            opcao_id = atribuicoes.get(vida.id)
            if opcao_id:
                vidas_por_opcao.setdefault(opcao_id, []).append(vida)
        for opcao_id, vidas in vidas_por_opcao.items():
            opcao = estudo.opcao_por_id(opcao_id)
            if not opcao:
                continue
            regime = estudo.regime_por_id(opcao.regime_copart_id)
            if not regime:
                continue
            if regime.tipo not in secoes_map:
                secoes_map[regime.tipo] = ScenarioSectionResult(
                    regime_tipo=regime.tipo,
                    rotulo_derivado=_rotulo_regime(regime.tipo),
                )
            resultado_sg = _calcular_subgrupo_novo(vidas, opcao, policy)
            secoes_map[regime.tipo].subgrupos.append(resultado_sg)

    secoes = list(secoes_map.values())
    for secao in secoes:
        _consolidar_secao(secao, baseline)

    cenario = ScenarioResult(
        cenario_id=cenario_id,
        baseline_apresentado=baseline,
        secoes=secoes,
    )
    _consolidar_cenario(cenario)
    return cenario


def _calcular_subgrupo_renovacao(
    estudo: EstudoInput,
    subgrupo: SubgrupoAtual,
    opcao: OpcaoPlano,
    policy: EffectivePolicy,
) -> ResultadoSubgrupo:
    assert policy.data_referencia_idade is not None
    vidas_sg = [
        v
        for v in estudo.vidas_incluidas()
        if v.subgrupo_atual_id == subgrupo.id
    ]
    resultados_vidas: list[ResultadoVida] = []
    baseline = policy.baseline_escolhido or BaselineEscolhido.REAJUSTADO

    for vida in vidas_sg:
        idade, faixa = faixa_em(vida.nascimento, policy.data_referencia_idade)
        vigente, reajustado = _calcular_atual_vida(vida, subgrupo, faixa, policy)
        proposta = _calcular_proposta_vida(opcao, faixa, policy)
        atual_baseline = reajustado if baseline == BaselineEscolhido.REAJUSTADO else vigente
        diff_mes = proposta - atual_baseline
        resultados_vidas.append(
            ResultadoVida(
                vida_id=vida.id,
                idade=idade,
                faixa=faixa,
                atual_vigente_centavos=valor_calc(vigente),
                atual_reajustado_centavos=valor_calc(reajustado),
                proposta_centavos=valor_calc(proposta),
                diff_mes_centavos=valor_calc(diff_mes),
                diff_ano_centavos=valor_calc(diff_mes * 12),
            )
        )

    return _montar_resultado_subgrupo(subgrupo.id, opcao.id, resultados_vidas)


def _calcular_subgrupo_novo(
    vidas: list[Vida],
    opcao: OpcaoPlano,
    policy: EffectivePolicy,
) -> ResultadoSubgrupo:
    assert policy.data_referencia_idade is not None
    resultados_vidas: list[ResultadoVida] = []
    for vida in vidas:
        idade, faixa = faixa_em(vida.nascimento, policy.data_referencia_idade)
        proposta = _calcular_proposta_vida(opcao, faixa, policy)
        resultados_vidas.append(
            ResultadoVida(
                vida_id=vida.id,
                idade=idade,
                faixa=faixa,
                proposta_centavos=valor_calc(proposta),
            )
        )
    return _montar_resultado_subgrupo(f"novo-{opcao.id}", opcao.id, resultados_vidas)


def _montar_resultado_subgrupo(
    subgrupo_id: str,
    opcao_id: str,
    vidas: list[ResultadoVida],
) -> ResultadoSubgrupo:
    sub_prop = sum(v.proposta_centavos.centavos for v in vidas if v.proposta_centavos)
    sub_vig = sum(
        v.atual_vigente_centavos.centavos for v in vidas if v.atual_vigente_centavos
    )
    sub_reaj = sum(
        v.atual_reajustado_centavos.centavos
        for v in vidas
        if v.atual_reajustado_centavos
    )
    return ResultadoSubgrupo(
        subgrupo_id=subgrupo_id,
        opcao_plano_id=opcao_id,
        subtotal_proposta_centavos=valor_calc(sub_prop) if sub_prop else None,
        subtotal_atual_vigente_centavos=valor_calc(sub_vig) if sub_vig else None,
        subtotal_atual_reajustado_centavos=valor_calc(sub_reaj) if sub_reaj else None,
        vidas=vidas,
    )


def _consolidar_secao(secao: ScenarioSectionResult, baseline: str) -> None:
    from newport_motor.reconciliation import somar_valores

    props = [sg.subtotal_proposta_centavos for sg in secao.subgrupos if sg.subtotal_proposta_centavos]
    if props:
        secao.total_proposta_centavos = somar_valores(props)

    if baseline == BaselineEscolhido.REAJUSTADO.value:
        atuais = [
            sg.subtotal_atual_reajustado_centavos
            for sg in secao.subgrupos
            if sg.subtotal_atual_reajustado_centavos
        ]
    else:
        atuais = [
            sg.subtotal_atual_vigente_centavos
            for sg in secao.subgrupos
            if sg.subtotal_atual_vigente_centavos
        ]
    if atuais:
        secao.total_atual_baseline_centavos = somar_valores(atuais)

    if secao.total_proposta_centavos and secao.total_atual_baseline_centavos:
        diff = (
            secao.total_proposta_centavos.centavos
            - secao.total_atual_baseline_centavos.centavos
        )
        secao.diff_mes_centavos = valor_calc(diff)
        secao.diff_ano_centavos = valor_calc(diff * 12)


def _consolidar_cenario(cenario: ScenarioResult) -> None:
    from newport_motor.reconciliation import somar_valores

    props = [s.total_proposta_centavos for s in cenario.secoes if s.total_proposta_centavos]
    if props:
        cenario.total_proposta_centavos = somar_valores(props)
    atuais = [
        s.total_atual_baseline_centavos for s in cenario.secoes if s.total_atual_baseline_centavos
    ]
    if atuais:
        cenario.total_atual_baseline_centavos = somar_valores(atuais)
    if cenario.total_proposta_centavos and cenario.total_atual_baseline_centavos:
        diff = (
            cenario.total_proposta_centavos.centavos
            - cenario.total_atual_baseline_centavos.centavos
        )
        cenario.diff_mes_centavos = valor_calc(diff)
        cenario.diff_ano_centavos = valor_calc(diff * 12)
