"""Lógica de cálculo financeiro por vida, subgrupo e cenário."""

from __future__ import annotations

from newport_motor.faixa import faixa_em
from newport_motor.finance import (
    normalizar_vidas_para_recorrente,
    para_base_exclui_iof,
    total_recorrente_de_bases_exclui,
    tipo_fiscal_aplica_iof,
)
from newport_motor.models import EstudoInput, OpcaoPlano, SubgrupoAtual, Vida
from newport_motor.money import apply_rate_bps
from newport_motor.policy import EffectivePolicy
from newport_motor.reconciliation import valor_calc
from newport_motor.result import ResultadoSubgrupo, ResultadoVida, ScenarioResult, ScenarioSectionResult
from newport_motor.types import (
    BaselineEscolhido,
    FormatoEstudo,
    PrecedenciaAtualVida,
    PriceBasis,
    RegimeCopartTipo,
)


def _valor_faixa_tabela(opcao: OpcaoPlano, faixa: int) -> tuple[int, PriceBasis]:
    entry = next(t for t in opcao.tabela if t.faixa == faixa)
    return entry.valor_centavos, entry.price_basis


def _base_atual_vida(
    vida: Vida,
    subgrupo: SubgrupoAtual,
    faixa: int,
    policy: EffectivePolicy,
) -> tuple[int, PriceBasis] | None:
    tem_tabela = bool(subgrupo.tabela_atual) and any(
        t.faixa == faixa for t in subgrupo.tabela_atual
    )
    tem_fatura = vida.valor_fatura_centavos is not None

    if tem_tabela and tem_fatura:
        if policy.precedencia_atual_vida == PrecedenciaAtualVida.TABELA_ATUAL:
            entry = next(t for t in subgrupo.tabela_atual if t.faixa == faixa)
            return entry.valor_centavos, entry.price_basis
        if policy.precedencia_atual_vida == PrecedenciaAtualVida.VALOR_FATURA:
            basis = vida.fatura_price_basis or subgrupo.fatura_price_basis
            if basis == PriceBasis.DESCONHECIDO:
                return None
            return vida.valor_fatura_centavos, basis
        return None

    if tem_tabela:
        entry = next(t for t in subgrupo.tabela_atual if t.faixa == faixa)
        return entry.valor_centavos, entry.price_basis

    if tem_fatura:
        basis = vida.fatura_price_basis or subgrupo.fatura_price_basis
        if basis == PriceBasis.DESCONHECIDO:
            return None
        return vida.valor_fatura_centavos, basis

    return None


def _recorrente_vida(
    valor: int,
    basis: PriceBasis,
    tipo_fiscal,
    policy: EffectivePolicy,
) -> int:
    vals = normalizar_vidas_para_recorrente(
        [(valor, basis)],
        tipo_fiscal,
        policy.iof_bps,
        policy.estrategia_arredondamento,
    )
    return int(vals[0])


def _calcular_atual_vida(
    vida: Vida,
    subgrupo: SubgrupoAtual,
    faixa: int,
    policy: EffectivePolicy,
) -> tuple[int, int]:
    base_info = _base_atual_vida(vida, subgrupo, faixa, policy)
    if base_info is None:
        return 0, 0
    valor, basis = base_info
    vigente = _recorrente_vida(valor, basis, subgrupo.tipo_fiscal, policy)
    if subgrupo.reajuste_bps is None:
        return vigente, vigente
    reajustado = apply_rate_bps(vigente, subgrupo.reajuste_bps)
    return vigente, reajustado


def _calcular_proposta_vida(
    opcao: OpcaoPlano,
    faixa: int,
    policy: EffectivePolicy,
) -> int:
    valor, basis = _valor_faixa_tabela(opcao, faixa)
    return _recorrente_vida(valor, basis, opcao.tipo_fiscal, policy)


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
        v for v in estudo.vidas_incluidas() if v.subgrupo_atual_id == subgrupo.id
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
        v.atual_reajustado_centavos.centavos for v in vidas if v.atual_reajustado_centavos
    )
    return ResultadoSubgrupo(
        subgrupo_id=subgrupo_id,
        opcao_plano_id=opcao_id,
        subtotal_proposta_centavos=valor_calc(sub_prop),
        subtotal_atual_vigente_centavos=valor_calc(sub_vig),
        subtotal_atual_reajustado_centavos=valor_calc(sub_reaj),
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


def agregar_por_opcao_no_cenario(
    estudo: EstudoInput,
    cenario_id: str,
    atribuicoes: dict[str, str],
    resultado: ScenarioResult,
) -> dict[str, dict]:
    """Agrupa vidas e subtotais por opcao_plano_id para reconciliação agregada."""
    por_opcao: dict[str, dict] = {}

    for secao in resultado.secoes:
        for sg in secao.subgrupos:
            if not sg.opcao_plano_id:
                continue
            oid = sg.opcao_plano_id
            if oid not in por_opcao:
                por_opcao[oid] = {"vidas": [], "subgrupos": [], "total": 0}
            subgrupo = estudo.subgrupo_por_id(sg.subgrupo_id)
            for rv in sg.vidas:
                vida = next((v for v in estudo.vidas if v.id == rv.vida_id), None)
                if vida and rv.proposta_centavos:
                    por_opcao[oid]["vidas"].append((vida, rv.proposta_centavos.centavos))
            por_opcao[oid]["subgrupos"].append(
                {
                    "subgrupo_id": sg.subgrupo_id,
                    "subtotal": sg.subtotal_proposta_centavos.centavos,
                    "subtotal_impresso": subgrupo.subtotal_impresso if subgrupo else None,
                }
            )
            por_opcao[oid]["total"] += sg.subtotal_proposta_centavos.centavos

    return por_opcao
