"""Validações e bloqueios B-02…B-08 (B-01 adiado para camada de aplicação)."""

from __future__ import annotations

from newport_motor.models import EstudoInput, OpcaoPlano
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro
from newport_motor.result import Validacao
from newport_motor.types import (
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PriceBasis,
    SeveridadeValidacao,
)

PILOTO_MAX_VIDAS = 29


def validar_b08_escopo_piloto(estudo: EstudoInput) -> list[Validacao]:
    count = len(estudo.vidas_incluidas())
    if count == 0:
        return [
            Validacao(
                codigo="B-08",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem="Estudo sem vidas incluídas.",
                alvo_ref="estudo",
            )
        ]
    if count > PILOTO_MAX_VIDAS:
        return [
            Validacao(
                codigo="B-08",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem=f"Vidas incluídas ({count}) excedem o piloto (máx. {PILOTO_MAX_VIDAS}).",
                alvo_ref="estudo",
            )
        ]
    return []


def validar_b07_politica_obrigatoria(
    estudo: EstudoInput, policy: EffectivePolicy
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    if policy.data_referencia_idade is None:
        validacoes.append(
            Validacao(
                codigo="B-07",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem="Data de referência de idade obrigatória (DP-01).",
                alvo_ref="policy.data_referencia_idade",
            )
        )
    if estudo.formato == FormatoEstudo.RENOVACAO:
        baseline = policy.baseline_escolhido
        if baseline is None:
            validacoes.append(
                Validacao(
                    codigo="B-07",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem="Baseline de comparação obrigatório em renovação (DP-03).",
                    alvo_ref="policy.baseline_escolhido",
                )
            )
        for sg in estudo.subgrupos_atuais:
            if sg.reajuste_bps is None:
                validacoes.append(
                    Validacao(
                        codigo="B-07",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Reajuste não definido para subgrupo {sg.id} (DP-04).",
                        alvo_ref=f"subgrupo:{sg.id}",
                    )
                )
    return validacoes


def _componente_precisa_confirmacao(comp: ComponenteFinanceiro | None) -> bool:
    if comp is None:
        return False
    prov = comp.proveniencia
    if prov.origem == OrigemValor.IA and not prov.confirmado:
        return True
    return False


def validar_b03_valores_nao_confirmados(estudo: EstudoInput) -> list[Validacao]:
    validacoes: list[Validacao] = []
    docs_alerta = {
        d.id
        for d in estudo.documentos
        if d.estado_extracao
        in (EstadoExtracao.EXTRAIDO_COM_ALERTA, EstadoExtracao.FALHA_EXTRACAO)
    }

    for opcao in estudo.opcoes_plano:
        if opcao.documento_id and opcao.documento_id in docs_alerta:
            for comp_name, comp in [
                ("premio_saude", opcao.premio_saude),
                ("iof", opcao.iof),
                ("total_recorrente", opcao.total_recorrente),
                ("total_primeira_parcela", opcao.total_primeira_parcela),
            ]:
                if comp and not comp.proveniencia.confirmado:
                    validacoes.append(
                        Validacao(
                            codigo="B-03",
                            severidade=SeveridadeValidacao.BLOQUEANTE,
                            mensagem=(
                                f"Campo {comp_name} da opção {opcao.id} não confirmado "
                                f"com documento em estado de alerta/falha."
                            ),
                            alvo_ref=f"opcao:{opcao.id}:{comp_name}",
                        )
                    )
        for comp_name, comp in [
            ("premio_saude", opcao.premio_saude),
            ("iof", opcao.iof),
            ("total_recorrente", opcao.total_recorrente),
            ("total_primeira_parcela", opcao.total_primeira_parcela),
        ]:
            if _componente_precisa_confirmacao(comp):
                validacoes.append(
                    Validacao(
                        codigo="B-03",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Valor {comp_name} com origem IA não confirmado (opção {opcao.id}).",
                        alvo_ref=f"opcao:{opcao.id}:{comp_name}",
                    )
                )
        for faixa in opcao.tabela:
            if faixa.proveniencia.origem == OrigemValor.IA and not faixa.proveniencia.confirmado:
                validacoes.append(
                    Validacao(
                        codigo="B-03",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Faixa {faixa.faixa} com origem IA não confirmada "
                            f"(opção {opcao.id})."
                        ),
                        alvo_ref=f"opcao:{opcao.id}:faixa:{faixa.faixa}",
                    )
                )
    return validacoes


def validar_b05_dados_obrigatorios(
    estudo: EstudoInput, opcoes_usadas: set[str]
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    for opcao_id in opcoes_usadas:
        opcao = estudo.opcao_por_id(opcao_id)
        if opcao is None:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"Opção de plano {opcao_id} referenciada mas ausente.",
                    alvo_ref=f"opcao:{opcao_id}",
                )
            )
            continue
        regime = estudo.regime_por_id(opcao.regime_copart_id)
        if regime is None:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"Regime de copart {opcao.regime_copart_id} indefinido (DP-06).",
                    alvo_ref=f"opcao:{opcao_id}",
                )
            )
        faixas = {t.faixa for t in opcao.tabela}
        for f in range(10):
            if f not in faixas:
                validacoes.append(
                    Validacao(
                        codigo="B-05",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Tabela incompleta: faixa {f} ausente (opção {opcao_id}).",
                        alvo_ref=f"opcao:{opcao_id}:faixa:{f}",
                    )
                )
    return validacoes


def validar_b06_atribuicoes(estudo: EstudoInput) -> list[Validacao]:
    validacoes: list[Validacao] = []
    vidas_incl = {v.id for v in estudo.vidas_incluidas()}
    subgrupos = {s.id for s in estudo.subgrupos_atuais}

    for cenario in estudo.cenarios:
        atrib_por_alvo: dict[str, str] = {}
        for atr in cenario.atribuicoes:
            atrib_por_alvo[atr.alvo_id] = atr.opcao_plano_id

        alvos_esperados: set[str] = set()
        if estudo.formato == FormatoEstudo.RENOVACAO:
            for v in estudo.vidas_incluidas():
                if v.subgrupo_atual_id:
                    alvos_esperados.add(v.subgrupo_atual_id)
        else:
            alvos_esperados = vidas_incl

        for alvo_id in alvos_esperados:
            if alvo_id not in atrib_por_alvo:
                validacoes.append(
                    Validacao(
                        codigo="B-06",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Alvo {alvo_id} sem atribuição no cenário {cenario.id}.",
                        alvo_ref=f"cenario:{cenario.id}:alvo:{alvo_id}",
                    )
                )

        # Regimes mistos sob mesmo rótulo de seção são bloqueados em engine (P6)
        regimes_por_subgrupo: dict[str, str] = {}
        for atr in cenario.atribuicoes:
            if atr.alvo_tipo == "subgrupo" and atr.alvo_id in subgrupos:
                opcao = estudo.opcao_por_id(atr.opcao_plano_id)
                if opcao:
                    regime = estudo.regime_por_id(opcao.regime_copart_id)
                    if regime:
                        regimes_por_subgrupo[atr.alvo_id] = regime.tipo.value

    return validacoes


def validar_b04_idade_valor(
    estudo: EstudoInput,
    policy: EffectivePolicy,
    tolerancia_vida: int,
) -> list[Validacao]:
    """P8: só roda com tabela atual comparável identificada."""
    from newport_motor.faixa import faixa_em
    from newport_motor.iof import tipo_fiscal_aplica_iof, valor_com_iof

    if policy.data_referencia_idade is None:
        return []

    validacoes: list[Validacao] = []
    for vida in estudo.vidas_incluidas():
        if vida.idade_valor_resolvido or vida.idade_valor_override_justificado:
            continue
        if vida.valor_fatura_centavos is None or not vida.subgrupo_atual_id:
            continue
        subgrupo = estudo.subgrupo_por_id(vida.subgrupo_atual_id)
        if subgrupo is None or not subgrupo.tabela_atual:
            continue

        _, faixa = faixa_em(vida.nascimento, policy.data_referencia_idade)
        tabela_faixa = next((t for t in subgrupo.tabela_atual if t.faixa == faixa), None)
        if tabela_faixa is None:
            validacoes.append(
                Validacao(
                    codigo="B-04",
                    severidade=SeveridadeValidacao.ALERTA,
                    mensagem=(
                        f"Vida {vida.id}: sem faixa {faixa} na tabela atual comparável."
                    ),
                    alvo_ref=f"vida:{vida.id}",
                )
            )
            continue

        aplica_iof = tipo_fiscal_aplica_iof(subgrupo.tipo_fiscal)
        esperado = valor_com_iof(
            tabela_faixa.valor_centavos, aplica_iof, policy.iof_bps
        )
        diff = abs(int(esperado) - vida.valor_fatura_centavos)
        if diff > tolerancia_vida:
            validacoes.append(
                Validacao(
                    codigo="B-04",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id}: valor fatura ({vida.valor_fatura_centavos}c) "
                        f"diverge da tabela atual na faixa {faixa} "
                        f"(esperado {int(esperado)}c, diff {diff}c)."
                    ),
                    alvo_ref=f"vida:{vida.id}",
                )
            )
    return validacoes


def validar_price_basis_desconhecido(opcao: OpcaoPlano) -> list[Validacao]:
    validacoes: list[Validacao] = []
    for comp_name, comp in [
        ("premio_saude", opcao.premio_saude),
        ("total_recorrente", opcao.total_recorrente),
    ]:
        if comp and comp.price_basis == PriceBasis.DESCONHECIDO and comp.centavos is not None:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"price_basis desconhecido em {comp_name} (opção {opcao.id}); "
                        "declaração obrigatória (DP-02)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:{comp_name}",
                )
            )
    return validacoes
