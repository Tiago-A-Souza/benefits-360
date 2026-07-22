"""MotorResult → resposta amigável para a interface."""

from __future__ import annotations

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import (
    AuditoriaItem,
    ComparativoResponse,
    EstudoResumo,
    PendenciaItem,
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
) -> PendenciaItem:
    if codigo == "H-01":
        n = len(rascunho.vidas_incluidas())
        max_h = rascunho.escolhas.max_beneficiarios_homologados or 29
        return PendenciaItem(
            tipo="alerta",
            titulo="Quantidade acima da faixa homologada",
            descricao=mensagem_faixa_homologada(n, max_h),
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
            pendencias.append(_traduzir_validacao(val.codigo, val.mensagem, rascunho))

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
    beneficiarios_calculados = 0
    if resultado.cenarios:
        cenario = resultado.cenarios[0]
        if cenario.secoes:
            secao = cenario.secoes[0]
            beneficiarios_calculados = sum(len(sg.vidas) for sg in secao.subgrupos)
            atual = cenario.total_atual_baseline_centavos
            proposta = cenario.total_proposta_centavos
            diff_m = cenario.diff_mes_centavos
            diff_a = cenario.diff_ano_centavos
            if atual and proposta and diff_m and diff_a:
                baseline = (
                    "Contrato reajustado"
                    if rascunho.escolhas.valor_atual_referencia == "reajustado"
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
        pendencias=pendencias,
        auditoria=auditoria,
    )
