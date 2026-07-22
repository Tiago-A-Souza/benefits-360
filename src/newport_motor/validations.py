"""Validações e bloqueios B-02…B-08 (B-01 adiado para camada de aplicação)."""

from __future__ import annotations

from newport_motor.finance import componente_para_recorrente, tipo_fiscal_aplica_iof
from newport_motor.models import EstudoInput, OpcaoPlano, SubgrupoAtual, TabelaPrecoFaixa, Vida
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.result import Validacao
from newport_motor.types import (
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PrecedenciaAtualVida,
    PriceBasis,
    RoundingStrategy,
    SeveridadeValidacao,
    AlvoTipo,
)

def validar_escopo_vidas(estudo: EstudoInput, policy: EffectivePolicy) -> list[Validacao]:
    """B-08 (zero vidas) e H-01 (acima da faixa homologada configurável na policy)."""
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
    validacoes: list[Validacao] = []
    max_homologadas = policy.max_vidas_homologadas
    if max_homologadas is not None and count > max_homologadas:
        validacoes.append(
            Validacao(
                codigo="H-01",
                severidade=SeveridadeValidacao.ALERTA,
                mensagem=(
                    f"Vidas incluídas ({count}) excedem a faixa homologada "
                    f"({max_homologadas}); revisão adicional necessária antes da aprovação."
                ),
                alvo_ref="estudo",
            )
        )
    return validacoes


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
        if policy.baseline_escolhido is None:
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
            elif sg.reajuste_bps < 0:
                validacoes.append(
                    Validacao(
                        codigo="B-07",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Reajuste negativo ({sg.reajuste_bps} bps) no subgrupo {sg.id} "
                            "não homologado no piloto; suporte futuro dependerá de política "
                            "explícita por estudo (DP-04)."
                        ),
                        alvo_ref=f"subgrupo:{sg.id}:reajuste_bps",
                    )
                )
        validacoes.extend(_validar_precedencia_atual(estudo, policy))
    validacoes.extend(_validar_estrategia_piloto(policy))
    return validacoes


def _validar_estrategia_piloto(policy: EffectivePolicy) -> list[Validacao]:
    """Piloto: somente por_vida_entao_soma homologada (Alternativa A)."""
    if policy.estrategia_arredondamento == RoundingStrategy.POR_VIDA_ENTAO_SOMA:
        return []
    return [
        Validacao(
            codigo="B-07",
            severidade=SeveridadeValidacao.BLOQUEANTE,
            mensagem=(
                f"Estratégia de arredondamento '{policy.estrategia_arredondamento.value}' "
                "não homologada no piloto; use 'por_vida_entao_soma' (DP-11)."
            ),
            alvo_ref="policy.estrategia_arredondamento",
        )
    ]


def _validar_precedencia_atual(
    estudo: EstudoInput, policy: EffectivePolicy
) -> list[Validacao]:
    if policy.data_referencia_idade is None:
        return []
    from newport_motor.faixa import faixa_de_idade, idade_completa_em

    validacoes: list[Validacao] = []
    for vida in estudo.vidas_incluidas():
        if not vida.subgrupo_atual_id or vida.valor_fatura_centavos is None:
            continue
        subgrupo = estudo.subgrupo_por_id(vida.subgrupo_atual_id)
        if subgrupo is None or not subgrupo.tabela_atual:
            continue
        if vida.nascimento > policy.data_referencia_idade:
            continue
        idade = idade_completa_em(vida.nascimento, policy.data_referencia_idade)
        faixa = faixa_de_idade(idade)
        if not any(t.faixa == faixa for t in subgrupo.tabela_atual):
            continue
        if policy.precedencia_atual_vida is None:
            validacoes.append(
                Validacao(
                    codigo="B-07",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id}: tabela atual e fatura coexistem; "
                        "precedencia_atual_vida obrigatória (DP-02)."
                    ),
                    alvo_ref=f"vida:{vida.id}:precedencia",
                )
            )
            break
    return validacoes


def validar_b05_nascimento_referencia(
    estudo: EstudoInput, policy: EffectivePolicy
) -> list[Validacao]:
    if policy.data_referencia_idade is None:
        return []
    validacoes: list[Validacao] = []
    for vida in estudo.vidas_incluidas():
        if vida.nascimento > policy.data_referencia_idade:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id}: nascimento ({vida.nascimento.isoformat()}) "
                        f"posterior à data de referência "
                        f"({policy.data_referencia_idade.isoformat()})."
                    ),
                    alvo_ref=f"vida:{vida.id}:nascimento",
                )
            )
    return validacoes


def validar_b05_baseline_atual_renovacao(
    estudo: EstudoInput, policy: EffectivePolicy
) -> list[Validacao]:
    if estudo.formato != FormatoEstudo.RENOVACAO or policy.data_referencia_idade is None:
        return []
    from newport_motor.faixa import faixa_de_idade, idade_completa_em

    validacoes: list[Validacao] = []
    for vida in estudo.vidas_incluidas():
        if vida.nascimento > policy.data_referencia_idade:
            continue
        if not vida.subgrupo_atual_id:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id} em renovação sem subgrupo_atual_id; "
                        "baseline atual obrigatório."
                    ),
                    alvo_ref=f"vida:{vida.id}:subgrupo_atual_id",
                )
            )
            continue
        subgrupo = estudo.subgrupo_por_id(vida.subgrupo_atual_id)
        if subgrupo is None:
            continue
        idade = idade_completa_em(vida.nascimento, policy.data_referencia_idade)
        faixa = faixa_de_idade(idade)
        if not _vida_tem_fonte_atual(vida, subgrupo, faixa):
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id}: sem fonte válida para baseline atual "
                        f"(fatura ou tabela atual faixa {faixa})."
                    ),
                    alvo_ref=f"vida:{vida.id}:baseline_atual",
                )
            )
    return validacoes


def _vida_tem_fonte_atual(vida: Vida, subgrupo: SubgrupoAtual, faixa: int) -> bool:
    tem_fatura = vida.valor_fatura_centavos is not None
    tem_tabela = any(t.faixa == faixa for t in subgrupo.tabela_atual)
    if tem_fatura:
        basis = vida.fatura_price_basis or subgrupo.fatura_price_basis
        if basis != PriceBasis.DESCONHECIDO:
            return True
    if tem_tabela:
        return True
    return False


def validar_b05_opcoes_obrigatorias(estudo: EstudoInput) -> list[Validacao]:
    if not estudo.vidas_incluidas() or not estudo.cenarios:
        return []
    if not estudo.opcoes_plano:
        return [
            Validacao(
                codigo="B-05",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem="Estudo sem opção de proposta utilizável.",
                alvo_ref="estudo:opcoes_plano",
            )
        ]
    return []


def validar_b05_primeira_parcela_custos(estudo: EstudoInput) -> list[Validacao]:
    validacoes: list[Validacao] = []
    for opcao in estudo.opcoes_plano:
        if (
            opcao.total_primeira_parcela is None
            or opcao.total_primeira_parcela.centavos is None
        ):
            continue
        custos = sum(c.valor_centavos for c in opcao.custos_unicos)
        if opcao.total_primeira_parcela.centavos < custos:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Primeira parcela ({opcao.total_primeira_parcela.centavos}c) "
                        f"menor que a soma dos custos únicos ({custos}c) "
                        f"(opção {opcao.id})."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:total_primeira_parcela",
                )
            )
    return validacoes


def validar_entrada_estrutural(estudo: EstudoInput) -> list[Validacao]:
    """Atribuições inválidas, faixas e valores — antes do cálculo."""
    validacoes: list[Validacao] = []
    vidas_ids = {v.id for v in estudo.vidas}
    subgrupos_ids = {s.id for s in estudo.subgrupos_atuais}
    opcoes_ids = {o.id for o in estudo.opcoes_plano}

    for cenario in estudo.cenarios:
        for atr in cenario.atribuicoes:
            if atr.opcao_plano_id not in opcoes_ids:
                validacoes.append(
                    Validacao(
                        codigo="B-05",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Opção {atr.opcao_plano_id} inexistente (atribuição {atr.id}).",
                        alvo_ref=f"atribuicao:{atr.id}",
                    )
                )
            if atr.alvo_tipo == AlvoTipo.SUBGRUPO and atr.alvo_id not in subgrupos_ids:
                validacoes.append(
                    Validacao(
                        codigo="B-06",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Subgrupo {atr.alvo_id} inexistente (atribuição {atr.id}).",
                        alvo_ref=f"atribuicao:{atr.id}",
                    )
                )
            if atr.alvo_tipo == AlvoTipo.VIDA and atr.alvo_id not in vidas_ids:
                validacoes.append(
                    Validacao(
                        codigo="B-06",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=f"Vida {atr.alvo_id} inexistente (atribuição {atr.id}).",
                        alvo_ref=f"atribuicao:{atr.id}",
                    )
                )

    for opcao in estudo.opcoes_plano:
        validacoes.extend(_validar_price_basis_componentes(opcao))
        validacoes.extend(_validar_tabela(opcao.tabela, f"opcao:{opcao.id}"))

    validacoes.extend(validar_b05_primeira_parcela_custos(estudo))
    validacoes.extend(validar_b05_referencias_documentais(estudo))

    for sg in estudo.subgrupos_atuais:
        validacoes.extend(_validar_tabela(sg.tabela_atual, f"subgrupo:{sg.id}"))
        if sg.fatura_price_basis == PriceBasis.DESCONHECIDO:
            for v in estudo.vidas_incluidas():
                if v.subgrupo_atual_id == sg.id and v.valor_fatura_centavos is not None:
                    if v.fatura_price_basis is None or v.fatura_price_basis == PriceBasis.DESCONHECIDO:
                        validacoes.append(
                            Validacao(
                                codigo="B-02",
                                severidade=SeveridadeValidacao.BLOQUEANTE,
                                mensagem=(
                                    f"fatura_price_basis desconhecido (vida {v.id}, subgrupo {sg.id})."
                                ),
                                alvo_ref=f"vida:{v.id}:fatura_price_basis",
                            )
                        )

    return validacoes


def _validar_tabela(tabela: list[TabelaPrecoFaixa], alvo: str) -> list[Validacao]:
    validacoes: list[Validacao] = []
    faixas_vistas: set[int] = set()
    for t in tabela:
        if t.faixa < 0 or t.faixa > 9:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"Faixa {t.faixa} fora do intervalo 0–9 ({alvo}).",
                    alvo_ref=f"{alvo}:faixa:{t.faixa}",
                )
            )
        if t.faixa in faixas_vistas:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"Faixa {t.faixa} duplicada ({alvo}).",
                    alvo_ref=f"{alvo}:faixa:{t.faixa}",
                )
            )
        faixas_vistas.add(t.faixa)
        if t.valor_centavos < 0:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"valor_centavos negativo na faixa {t.faixa} ({alvo}).",
                    alvo_ref=f"{alvo}:faixa:{t.faixa}",
                )
            )
        if t.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"price_basis desconhecido na faixa {t.faixa} ({alvo}).",
                    alvo_ref=f"{alvo}:faixa:{t.faixa}:price_basis",
                )
            )
    return validacoes


def _validar_price_basis_componentes(opcao: OpcaoPlano) -> list[Validacao]:
    validacoes: list[Validacao] = []
    for comp_name, comp in [
        ("premio_saude", opcao.premio_saude),
        ("iof", opcao.iof),
        ("total_recorrente", opcao.total_recorrente),
        ("total_primeira_parcela", opcao.total_primeira_parcela),
        ("subtotal_impresso", opcao.subtotal_impresso),
    ]:
        if comp and comp.centavos is not None and comp.price_basis == PriceBasis.DESCONHECIDO:
            validacoes.append(
                Validacao(
                    codigo="B-02",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"price_basis desconhecido em {comp_name} (opção {opcao.id}); "
                        "declaração obrigatória antes do cálculo (DP-02)."
                    ),
                    alvo_ref=f"opcao:{opcao.id}:{comp_name}",
                )
            )
    return validacoes


def validar_b05_referencias_documentais(estudo: EstudoInput) -> list[Validacao]:
    """documento_id referenciado deve existir em estudo.documentos."""
    docs_ids = {d.id for d in estudo.documentos}
    validacoes: list[Validacao] = []

    def _checar(doc_id: str | None, alvo_ref: str) -> None:
        if doc_id and doc_id not in docs_ids:
            validacoes.append(
                Validacao(
                    codigo="B-05",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=f"Documento '{doc_id}' inexistente ({alvo_ref}).",
                    alvo_ref=alvo_ref,
                )
            )

    for opcao in estudo.opcoes_plano:
        _checar(opcao.documento_id, f"opcao:{opcao.id}:documento_id")
        for comp_name, comp in [
            ("premio_saude", opcao.premio_saude),
            ("iof", opcao.iof),
            ("total_recorrente", opcao.total_recorrente),
            ("total_primeira_parcela", opcao.total_primeira_parcela),
            ("subtotal_impresso", opcao.subtotal_impresso),
        ]:
            if comp:
                _checar(
                    comp.proveniencia.documento_id,
                    f"opcao:{opcao.id}:{comp_name}:documento_id",
                )
        for faixa in opcao.tabela:
            _checar(
                faixa.proveniencia.documento_id,
                f"opcao:{opcao.id}:faixa:{faixa.faixa}:documento_id",
            )
        for cu in opcao.custos_unicos:
            _checar(
                cu.proveniencia.documento_id,
                f"opcao:{opcao.id}:custo_unico:{cu.id}:documento_id",
            )

    for vida in estudo.vidas:
        prov = vida.fatura_proveniencia
        if prov:
            _checar(prov.documento_id, f"vida:{vida.id}:fatura:documento_id")

    for sg in estudo.subgrupos_atuais:
        if sg.subtotal_impresso:
            _checar(
                sg.subtotal_impresso.proveniencia.documento_id,
                f"subgrupo:{sg.id}:subtotal_impresso:documento_id",
            )
        for faixa in sg.tabela_atual:
            _checar(
                faixa.proveniencia.documento_id,
                f"subgrupo:{sg.id}:tabela_atual:faixa:{faixa.faixa}:documento_id",
            )

    return validacoes


def _validar_b03_proveniencia(
    estudo: EstudoInput,
    alvo_ref: str,
    prov: ProvenienciaCampo,
    rotulo: str,
    doc_fallback: str | None = None,
) -> list[Validacao]:
    validacoes: list[Validacao] = []
    doc_id = prov.documento_id or doc_fallback
    if prov.origem == OrigemValor.IA and not prov.confirmado:
        validacoes.append(
            Validacao(
                codigo="B-03",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem=f"{rotulo} com origem IA não confirmada.",
                alvo_ref=alvo_ref,
            )
        )
    elif not prov.confirmado and doc_id and _documento_em_alerta(estudo, doc_id):
        validacoes.append(
            Validacao(
                codigo="B-03",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem=(
                    f"{rotulo} não confirmado com documento em estado de alerta/falha."
                ),
                alvo_ref=alvo_ref,
            )
        )
    return validacoes


def _documento_em_alerta(estudo: EstudoInput, doc_id: str | None) -> bool:
    if not doc_id:
        return False
    doc = estudo.documento_por_id(doc_id)
    if doc is None:
        return False
    return doc.estado_extracao in (
        EstadoExtracao.EXTRAIDO_COM_ALERTA,
        EstadoExtracao.FALHA_EXTRACAO,
    )


def validar_b03_valores_nao_confirmados(estudo: EstudoInput) -> list[Validacao]:
    validacoes: list[Validacao] = []

    for vida in estudo.vidas_incluidas():
        if vida.valor_fatura_centavos is None:
            continue
        prov = vida.proveniencia_fatura_efetiva()
        assert prov is not None
        validacoes.extend(
            _validar_b03_proveniencia(
                estudo,
                f"vida:{vida.id}:fatura",
                prov,
                f"Fatura atual da vida {vida.id}",
            )
        )

    for sg in estudo.subgrupos_atuais:
        if sg.subtotal_impresso:
            validacoes.extend(
                _validar_b03_proveniencia(
                    estudo,
                    f"subgrupo:{sg.id}:subtotal_impresso",
                    sg.subtotal_impresso.proveniencia,
                    f"Subtotal atual do subgrupo {sg.id}",
                )
            )
        for faixa in sg.tabela_atual:
            validacoes.extend(
                _validar_b03_proveniencia(
                    estudo,
                    f"subgrupo:{sg.id}:tabela_atual:faixa:{faixa.faixa}",
                    faixa.proveniencia,
                    f"Faixa {faixa.faixa} da tabela atual (subgrupo {sg.id})",
                )
            )

    for opcao in estudo.opcoes_plano:
        doc_fb = opcao.documento_id
        for comp_name, comp in [
            ("premio_saude", opcao.premio_saude),
            ("iof", opcao.iof),
            ("total_recorrente", opcao.total_recorrente),
            ("total_primeira_parcela", opcao.total_primeira_parcela),
            ("subtotal_impresso", opcao.subtotal_impresso),
        ]:
            if comp:
                validacoes.extend(
                    _validar_b03_proveniencia(
                        estudo,
                        f"opcao:{opcao.id}:{comp_name}",
                        comp.proveniencia,
                        f"Campo {comp_name} da opção {opcao.id}",
                        doc_fallback=doc_fb,
                    )
                )
        for faixa in opcao.tabela:
            validacoes.extend(
                _validar_b03_proveniencia(
                    estudo,
                    f"opcao:{opcao.id}:faixa:{faixa.faixa}",
                    faixa.proveniencia,
                    f"Faixa {faixa.faixa} da opção {opcao.id}",
                    doc_fallback=doc_fb,
                )
            )
        for cu in opcao.custos_unicos:
            validacoes.extend(
                _validar_b03_proveniencia(
                    estudo,
                    f"opcao:{opcao.id}:custo_unico:{cu.id}",
                    cu.proveniencia,
                    f"Custo único {cu.id} da opção {opcao.id}",
                    doc_fallback=doc_fb,
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

    if estudo.vidas_incluidas() and not estudo.cenarios:
        validacoes.append(
            Validacao(
                codigo="B-06",
                severidade=SeveridadeValidacao.BLOQUEANTE,
                mensagem="Estudo com vidas incluídas sem cenários definidos.",
                alvo_ref="estudo:cenarios",
            )
        )
        return validacoes

    for cenario in estudo.cenarios:
        atrib_por_alvo: dict[str, str] = {}
        for atr in cenario.atribuicoes:
            if estudo.formato == FormatoEstudo.NOVO and atr.alvo_tipo != AlvoTipo.VIDA:
                validacoes.append(
                    Validacao(
                        codigo="B-06",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Atribuição {atr.id}: seguro novo exige alvo_tipo=vida "
                            f"(recebido '{atr.alvo_tipo.value}')."
                        ),
                        alvo_ref=f"atribuicao:{atr.id}:alvo_tipo",
                    )
                )
            if estudo.formato == FormatoEstudo.RENOVACAO and atr.alvo_tipo != AlvoTipo.SUBGRUPO:
                validacoes.append(
                    Validacao(
                        codigo="B-06",
                        severidade=SeveridadeValidacao.BLOQUEANTE,
                        mensagem=(
                            f"Atribuição {atr.id}: renovação exige alvo_tipo=subgrupo "
                            f"(recebido '{atr.alvo_tipo.value}')."
                        ),
                        alvo_ref=f"atribuicao:{atr.id}:alvo_tipo",
                    )
                )
            atrib_por_alvo[atr.alvo_id] = atr.opcao_plano_id

        if estudo.formato == FormatoEstudo.RENOVACAO:
            alvos_esperados = {
                v.subgrupo_atual_id
                for v in estudo.vidas_incluidas()
                if v.subgrupo_atual_id
            }
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
    return validacoes


def validar_b04_idade_valor(
    estudo: EstudoInput,
    policy: EffectivePolicy,
    tolerancia_vida: int,
) -> list[Validacao]:
    """P8: só roda com tabela atual comparável; usa precedência explícita."""
    from newport_motor.faixa import faixa_de_idade, idade_completa_em

    if policy.data_referencia_idade is None:
        return []

    validacoes: list[Validacao] = []
    for vida in estudo.vidas_incluidas():
        if vida.idade_valor_resolvido or vida.idade_valor_override_justificado:
            continue
        if vida.nascimento > policy.data_referencia_idade:
            continue
        if not vida.subgrupo_atual_id:
            continue
        subgrupo = estudo.subgrupo_por_id(vida.subgrupo_atual_id)
        if subgrupo is None or not subgrupo.tabela_atual:
            continue
        if vida.valor_fatura_centavos is None:
            continue

        idade = idade_completa_em(vida.nascimento, policy.data_referencia_idade)
        faixa = faixa_de_idade(idade)
        tabela_faixa = next((t for t in subgrupo.tabela_atual if t.faixa == faixa), None)
        if tabela_faixa is None:
            validacoes.append(
                Validacao(
                    codigo="B-04",
                    severidade=SeveridadeValidacao.ALERTA,
                    mensagem=f"Vida {vida.id}: sem faixa {faixa} na tabela atual comparável.",
                    alvo_ref=f"vida:{vida.id}",
                )
            )
            continue

        # B-04 compara fatura vs tabela (independente da precedência de cálculo)
        aplica_iof = tipo_fiscal_aplica_iof(subgrupo.tipo_fiscal)
        esperado_tabela = int(
            componente_para_recorrente(
                tabela_faixa.valor_centavos,
                tabela_faixa.price_basis,
                subgrupo.tipo_fiscal,
                policy.iof_bps,
            )
        )
        basis_fatura = vida.fatura_price_basis or subgrupo.fatura_price_basis
        if basis_fatura == PriceBasis.DESCONHECIDO:
            continue
        fatura_rec = int(
            componente_para_recorrente(
                vida.valor_fatura_centavos,
                basis_fatura,
                subgrupo.tipo_fiscal,
                policy.iof_bps,
            )
        )
        diff = abs(esperado_tabela - fatura_rec)
        if diff > tolerancia_vida:
            validacoes.append(
                Validacao(
                    codigo="B-04",
                    severidade=SeveridadeValidacao.BLOQUEANTE,
                    mensagem=(
                        f"Vida {vida.id}: fatura ({fatura_rec}c recorrente) diverge da "
                        f"tabela atual faixa {faixa} ({esperado_tabela}c, diff {diff}c)."
                    ),
                    alvo_ref=f"vida:{vida.id}",
                )
            )
    return validacoes
