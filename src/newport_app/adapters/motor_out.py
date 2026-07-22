"""MotorResult → resposta amigável para a interface."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    AuditoriaItem,
    ComparativoResponse,
    DetalheVidaComparativo,
    EstudoResumo,
    PendenciaItem,
    SecaoComparativo,
    TotaisComparativo,
)
from newport_app.presentation.textos import (
    descricao_estudo,
    formatar_tipo_estudo,
    mensagem_faixa_homologada,
    plural_beneficiarios,
    rotulos_diferenca,
)
from newport_motor.result import MotorResult
from newport_motor.types import SeveridadeValidacao

_TRADUCOES: dict[str, tuple[str, str, str | None]] = {
    "B-08": (
        "bloqueio",
        "Nenhum beneficiário incluído",
        "Inclua ao menos um beneficiário antes de calcular.",
        "Revise a lista de beneficiários do estudo.",
    ),
    "B-07": (
        "bloqueio",
        "Escolha obrigatória pendente",
        "Falta definir uma opção do estudo necessária para o cálculo.",
        "Complete as escolhas na etapa de configuração do estudo.",
    ),
    "B-02": (
        "bloqueio",
        "Valores não conferem",
        "Algum total informado não bate com o calculado dentro da tolerância permitida.",
        "Revise os valores digitados ou ajuste os totais informados no documento.",
    ),
    "B-03": (
        "bloqueio",
        "Confirmação de origem pendente",
        "Há valores que ainda precisam ser confirmados manualmente.",
        "Confirme a origem de cada valor destacado.",
    ),
    "B-04": (
        "bloqueio",
        "Idade e valor não compatíveis",
        "O valor de um beneficiário não combina com a faixa etária esperada.",
        "Corrija o valor na fonte ou justifique a exceção.",
    ),
    "B-05": (
        "bloqueio",
        "Informação obrigatória ausente",
        "Faltam dados necessários para concluir o cálculo.",
        "Complete os campos indicados na auditoria técnica.",
    ),
    "B-06": (
        "bloqueio",
        "Atribuição de plano incompleta",
        "Nem todo grupo ou beneficiário está vinculado a uma proposta no cenário.",
        "Atribua a proposta a todos os grupos do estudo.",
    ),
}


def _formatar_reais_opcional(valor) -> str | None:
    if valor is None:
        return None
    return _formatar_reais(valor.centavos)


def _rotulo_regime(tipo: str) -> str:
    mapa = {
        "sem": "Sem coparticipação",
        "parcial": "Coparticipação parcial",
        "percentual": "Coparticipação percentual",
        "customizada": "Coparticipação customizada",
    }
    return mapa.get(tipo, tipo)


def _montar_secoes(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> tuple[list[SecaoComparativo], int]:
    if not resultado.cenarios:
        return [], 0
    cenario = resultado.cenarios[0]
    vidas_por_id = {v.id: v for v in rascunho.vidas}
    subgrupos_por_id = {s.id: s for s in rascunho.subgrupos_atuais}
    secoes: list[SecaoComparativo] = []
    total_benef = 0
    for secao_motor in cenario.secoes:
        detalhes: list[DetalheVidaComparativo] = []
        for sg in secao_motor.subgrupos:
            sg_rasc = subgrupos_por_id.get(sg.subgrupo_id)
            plano_nome = sg_rasc.plano_nome if sg_rasc else None
            for rv in sg.vidas:
                vida = vidas_por_id.get(rv.vida_id)
                baseline_val = rv.atual_reajustado_centavos or rv.atual_vigente_centavos
                detalhes.append(
                    DetalheVidaComparativo(
                        vida_id=rv.vida_id,
                        nome=vida.nome if vida else rv.vida_id,
                        idade=rv.idade,
                        faixa=rv.faixa,
                        parentesco=vida.parentesco.value if vida and vida.parentesco else None,
                        plano_atual=plano_nome,
                        atual_reais=_formatar_reais_opcional(baseline_val),
                        proposta_reais=_formatar_reais_opcional(rv.proposta_centavos),
                        diff_mes_reais=_formatar_reais_opcional(rv.diff_mes_centavos),
                    )
                )
        total_benef += len(detalhes)
        semantica = None
        rotulo_mes = None
        diff_mes_exib = None
        diff_ano_exib = None
        if secao_motor.diff_mes_centavos and secao_motor.diff_ano_centavos:
            semantica, rotulo_mes, _ = rotulos_diferenca(
                secao_motor.diff_mes_centavos.centavos,
                secao_motor.diff_ano_centavos.centavos,
            )
            if semantica == "empate":
                diff_mes_exib = 0
                diff_ano_exib = 0
            elif semantica == "economia":
                diff_mes_exib = abs(secao_motor.diff_mes_centavos.centavos)
                diff_ano_exib = abs(secao_motor.diff_ano_centavos.centavos)
            else:
                diff_mes_exib = secao_motor.diff_mes_centavos.centavos
                diff_ano_exib = secao_motor.diff_ano_centavos.centavos
        secoes.append(
            SecaoComparativo(
                rotulo=secao_motor.rotulo_derivado or _rotulo_regime(secao_motor.regime_tipo.value),
                regime_tipo=secao_motor.regime_tipo.value,
                atual_mensal_reais=_formatar_reais_opcional(secao_motor.total_atual_baseline_centavos),
                proposta_mensal_reais=_formatar_reais_opcional(secao_motor.total_proposta_centavos),
                diferenca_mensal_reais=(
                    _formatar_reais(diff_mes_exib) if diff_mes_exib is not None else None
                ),
                diferenca_anual_reais=(
                    _formatar_reais(diff_ano_exib) if diff_ano_exib is not None else None
                ),
                diferenca_semantica=semantica,
                rotulo_diferenca_mensal=rotulo_mes,
                vidas=detalhes,
            )
        )
    return secoes, total_benef


def _validade_proposta(rascunho: RascunhoEstudo) -> str | None:
    for op in rascunho.opcoes_proposta:
        if op.validade_oficial:
            return op.validade_oficial.isoformat()
    return None


def _formatar_reais(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    valor = abs(centavos)
    reais, cents = divmod(valor, 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


def _traduzir_validacao(
    codigo: str,
    mensagem_motor: str,
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> PendenciaItem:
    if codigo == "H-01":
        n = len(rascunho.vidas_incluidas())
        max_h = resultado.politicas_efetivas.get("max_vidas_homologadas", 29)
        return PendenciaItem(
            tipo="alerta",
            titulo="Quantidade acima da faixa homologada",
            descricao=mensagem_faixa_homologada(n, int(max_h) if max_h is not None else 29),
            acao_sugerida="Confirme com o revisor que a quantidade foi conferida.",
        )
    if codigo in _TRADUCOES:
        tipo, titulo, descricao, acao = _TRADUCOES[codigo]
        return PendenciaItem(tipo=tipo, titulo=titulo, descricao=descricao, acao_sugerida=acao)
    return PendenciaItem(
        tipo="bloqueio",
        titulo="Pendência no cálculo",
        descricao=mensagem_motor,
        acao_sugerida="Consulte a auditoria técnica ou corrija os dados do estudo.",
    )


def rascunho_para_resumo(rascunho: RascunhoEstudo) -> EstudoResumo:
    n = len(rascunho.vidas_incluidas())
    return EstudoResumo(
        id=rascunho.id,
        titulo=rascunho.titulo,
        formato=rascunho.formato,
        formato_exibicao=formatar_tipo_estudo(rascunho.formato),
        beneficiarios_incluidos=n,
        beneficiarios_rotulo=plural_beneficiarios(n),
        descricao=descricao_estudo(rascunho.formato, n),
    )


def motor_result_para_comparativo(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> ComparativoResponse:
    pendencias: list[PendenciaItem] = []
    vistos: set[str] = set()
    for val in resultado.validacoes:
        if val.codigo in vistos:
            continue
        vistos.add(val.codigo)
        if val.severidade in (
            SeveridadeValidacao.BLOQUEANTE,
            SeveridadeValidacao.ALERTA,
        ):
            pendencias.append(
                _traduzir_validacao(val.codigo, val.mensagem, rascunho, resultado)
            )

    auditoria = [
        AuditoriaItem(
            codigo=v.codigo,
            severidade=v.severidade.value,
            mensagem=v.mensagem,
            alvo=v.alvo_ref,
        )
        for v in resultado.validacoes
    ]

    totais: TotaisComparativo | None = None
    secoes, beneficiarios_calculados = _montar_secoes(rascunho, resultado)
    if resultado.cenarios:
        cenario = resultado.cenarios[0]
        atual = cenario.total_atual_baseline_centavos
        proposta = cenario.total_proposta_centavos
        diff_m = cenario.diff_mes_centavos
        diff_a = cenario.diff_ano_centavos
        if atual and proposta and diff_m and diff_a:
            baseline = (
                "Contrato reajustado"
                if rascunho.escolhas.baseline_escolhido.valor == "reajustado"
                else "Contrato vigente"
            )
            semantica, rotulo_mes, rotulo_ano = rotulos_diferenca(
                diff_m.centavos,
                diff_a.centavos,
            )
            if semantica == "empate":
                diff_mes_exib = 0
                diff_ano_exib = 0
            elif semantica == "economia":
                diff_mes_exib = abs(diff_m.centavos)
                diff_ano_exib = abs(diff_a.centavos)
            else:
                diff_mes_exib = diff_m.centavos
                diff_ano_exib = diff_a.centavos
            totais = TotaisComparativo(
                atual_mensal_reais=_formatar_reais(atual.centavos),
                proposta_mensal_reais=_formatar_reais(proposta.centavos),
                diferenca_mensal_reais=_formatar_reais(diff_mes_exib),
                diferenca_anual_reais=_formatar_reais(diff_ano_exib),
                diferenca_semantica=semantica,
                rotulo_diferenca_mensal=rotulo_mes,
                rotulo_diferenca_anual=rotulo_ano,
                baseline_rotulo=baseline,
            )

    return ComparativoResponse(
        estudo_id=rascunho.id,
        titulo=rascunho.titulo,
        beneficiarios_calculados=beneficiarios_calculados,
        calculo_realizado=bool(resultado.cenarios),
        totais=totais,
        secoes=secoes,
        validade_proposta=_validade_proposta(rascunho),
        pendencias=pendencias,
        auditoria=auditoria,
    )
