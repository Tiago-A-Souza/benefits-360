"""MotorResult → resposta amigável para a interface."""

from __future__ import annotations

import re
from collections import defaultdict

from newport_app.agregacao_faixa import agregar_valores_faixa
from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.compilation import ErroCompilacao
from newport_app.services.comparativo_ui import ordem_apresentacao_rascunho
from newport_app.services.pendencias import bloqueios_comparativo_de_erros, pendencias_compilacao
from newport_app.models.responses import (
    AuditoriaItem,
    BloqueioComparativo,
    ColunaFaixaPropostaComparativo,
    ComparativoResponse,
    ConsistenciaComparativo,
    DetalheVidaComparativo,
    EstudoResumo,
    FaixaPlanoComparativo,
    PendenciaItem,
    PlanoAtualComparativo,
    RecorteSubgrupoComparativo,
    ResultadoPropostaComparativo,
    SecaoComparativo,
    TotaisComparativo,
    TotaisComparativoNumerico,
)
from newport_app.presentation.formatacao import formatar_data_br
from newport_app.presentation.rotulos import qualificar_rotulos_propostas
from newport_app.presentation.textos import (
    descricao_estudo,
    formatar_tipo_estudo,
    mensagem_faixa_homologada,
    plural_beneficiarios,
    rotulos_diferenca,
)
from newport_motor.calculation import cenario_coluna_da_grade
from newport_motor.result import MotorResult, ScenarioResult
from newport_motor.types import RegimeCopartTipo, SeveridadeValidacao

_TRADUCOES: dict[str, tuple[str, str, str, str | None]] = {
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
        "Atribua a proposta a todos os alvos exigidos pelo formato do estudo.",
    ),
}


def _formatar_reais_opcional(valor) -> str | None:
    if valor is None:
        return None
    return _formatar_reais(valor.centavos)


def _rotulo_regime(tipo: str, percentual: int | None = None) -> str:
    if tipo == "percentual" and percentual is not None:
        return f"Coparticipação {percentual}%"
    mapa = {
        "sem": "Sem coparticipação",
        "parcial": "Coparticipação parcial (terapias)",
        "percentual": "Coparticipação percentual",
        "misto": "Pacote misto",
    }
    return mapa.get(tipo, tipo)


def _grupo_regime(tipo: str) -> str:
    return "sem_copart" if tipo == "sem" else "com_copart"


def _baseline_rotulo(rascunho: RascunhoEstudo) -> str:
    return (
        "Contrato reajustado"
        if rascunho.escolhas.baseline_escolhido.valor == "reajustado"
        else "Contrato vigente"
    )


def _formatar_reais(centavos: int) -> str:
    sinal = "-" if centavos < 0 else ""
    valor = abs(centavos)
    reais, cents = divmod(valor, 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


def _formatar_percentual(atual_centavos: int, proposta_centavos: int) -> str | None:
    if atual_centavos == 0:
        return None
    pct = ((proposta_centavos - atual_centavos) / atual_centavos) * 100
    sinal = "+" if pct > 0 else ""
    texto = f"{pct:.1f}".replace(".", ",")
    return f"{sinal}{texto}%"


def _centavos_valor(valor) -> int | None:
    if valor is None:
        return None
    return valor.centavos


def _calcular_diff_bps(atual_centavos: int, proposta_centavos: int) -> int | None:
    from newport_app.presentation.reajuste import bps_variacao

    return bps_variacao(atual_centavos, proposta_centavos)


def _rotulo_faixa(faixa: int | None) -> str | None:
    if faixa is None or faixa < 0 or faixa >= len(ROTULOS_FAIXA):
        return None
    return ROTULOS_FAIXA[faixa]


def _montar_numerico_cenario(
    cenario: ScenarioResult,
    *,
    seguro_novo: bool = False,
) -> TotaisComparativoNumerico | None:
    proposta = cenario.total_proposta_centavos
    if not proposta:
        return None
    if seguro_novo:
        return TotaisComparativoNumerico(
            proposta_mensal_centavos=proposta.centavos,
        )
    atual = cenario.total_atual_baseline_centavos
    diff_m = cenario.diff_mes_centavos
    diff_a = cenario.diff_ano_centavos
    if not (atual and diff_m and diff_a):
        return TotaisComparativoNumerico(
            atual_mensal_centavos=atual.centavos if atual else None,
            proposta_mensal_centavos=proposta.centavos,
        )
    semantica, _, _ = rotulos_diferenca(diff_m.centavos, diff_a.centavos)
    return TotaisComparativoNumerico(
        atual_mensal_centavos=atual.centavos,
        proposta_mensal_centavos=proposta.centavos,
        diff_mes_centavos=diff_m.centavos,
        diff_ano_centavos=diff_a.centavos,
        diff_bps=_calcular_diff_bps(atual.centavos, proposta.centavos),
        diferenca_semantica=semantica,
    )


def _regime_label_rascunho(rascunho: RascunhoEstudo, regime_id: str | None) -> str | None:
    if not regime_id:
        return None
    for reg in rascunho.regimes_copart:
        if reg.id == regime_id:
            return _rotulo_regime(reg.tipo, reg.percentual)
    return None


def _baseline_escolhido(rascunho: RascunhoEstudo) -> str:
    escolhido = rascunho.escolhas.baseline_escolhido
    if escolhido and escolhido.valor == "vigente":
        return "vigente"
    return "reajustado"


def _agregar_subtotais_por_subgrupo(cenario: ScenarioResult) -> dict[str, dict[str, int | bool]]:
    """Soma subtotais do motor por subgrupo_id em todas as seções do cenário."""
    agregado: dict[str, dict[str, int | bool]] = {}
    for secao in cenario.secoes:
        for sg in secao.subgrupos:
            slot = agregado.setdefault(
                sg.subgrupo_id,
                {
                    "vigente": 0,
                    "reajustado": 0,
                    "proposta": 0,
                    "diff_mes": 0,
                    "diff_ano": 0,
                    "tem_vigente": False,
                    "tem_reajustado": False,
                    "tem_proposta": False,
                },
            )
            if sg.subtotal_atual_vigente_centavos is not None:
                slot["vigente"] = int(slot["vigente"]) + sg.subtotal_atual_vigente_centavos.centavos
                slot["tem_vigente"] = True
            if sg.subtotal_atual_reajustado_centavos is not None:
                slot["reajustado"] = int(slot["reajustado"]) + sg.subtotal_atual_reajustado_centavos.centavos
                slot["tem_reajustado"] = True
            if sg.subtotal_proposta_centavos is not None:
                slot["proposta"] = int(slot["proposta"]) + sg.subtotal_proposta_centavos.centavos
                slot["tem_proposta"] = True
            for rv in sg.vidas:
                if rv.diff_mes_centavos is not None:
                    slot["diff_mes"] = int(slot["diff_mes"]) + rv.diff_mes_centavos.centavos
                if rv.diff_ano_centavos is not None:
                    slot["diff_ano"] = int(slot["diff_ano"]) + rv.diff_ano_centavos.centavos
    return agregado


def _vidas_incluidas_subgrupo(rascunho: RascunhoEstudo, subgrupo_id: str) -> int:
    return sum(
        1
        for v in rascunho.vidas
        if v.incluida and v.subgrupo_atual_id == subgrupo_id
    )


def _centavos_flag(slot: dict[str, int | bool] | None, campo: str, flag: str) -> int | None:
    if not slot or not slot.get(flag):
        return None
    return int(slot[campo])


def _montar_recortes_subgrupo(
    rascunho: RascunhoEstudo,
    cenario: ScenarioResult,
) -> list[RecorteSubgrupoComparativo]:
    if rascunho.formato == "novo" or not rascunho.subgrupos_atuais:
        return []
    agregado = _agregar_subtotais_por_subgrupo(cenario)
    baseline = _baseline_escolhido(rascunho)
    recortes: list[RecorteSubgrupoComparativo] = []
    for sg in rascunho.subgrupos_atuais:
        slot = agregado.get(sg.id)
        proposta = _centavos_flag(slot, "proposta", "tem_proposta")
        vigente = _centavos_flag(slot, "vigente", "tem_vigente")
        reajustado = _centavos_flag(slot, "reajustado", "tem_reajustado")
        mensal = reajustado if baseline == "reajustado" else vigente
        if slot is None:
            diff_mes = None
            diff_ano = None
        else:
            diff_mes = int(slot["diff_mes"])
            diff_ano = int(slot["diff_ano"])
        recortes.append(
            RecorteSubgrupoComparativo(
                subgrupo_id=sg.id,
                plano_nome=sg.plano_nome,
                proposta_centavos=proposta,
                diff_mes_centavos=diff_mes,
                diff_ano_centavos=diff_ano,
                diff_bps=(
                    _calcular_diff_bps(mensal, proposta)
                    if mensal is not None and proposta is not None
                    else None
                ),
                proposta_reais=_formatar_reais(proposta) if proposta is not None else None,
                diff_mes_reais=_formatar_reais(diff_mes) if diff_mes is not None else None,
                diff_ano_reais=_formatar_reais(diff_ano) if diff_ano is not None else None,
            )
        )
    return recortes


def _chave_contrato_subgrupo(slot: dict[str, int | bool] | None) -> tuple[int | None, int | None]:
    return (
        _centavos_flag(slot, "vigente", "tem_vigente"),
        _centavos_flag(slot, "reajustado", "tem_reajustado"),
    )


def _montar_faixas_plano_comparativo(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
    subgrupo_id: str,
) -> list[FaixaPlanoComparativo]:
    from newport_app.rascunho.cenarios_sync import opcoes_usadas_nos_cenarios

    vigentes: dict[int, list[int]] = defaultdict(list)
    reajustados: dict[int, list[int]] = defaultdict(list)
    propostas: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    opcao_ids = opcoes_usadas_nos_cenarios(rascunho)

    # Vigente/reajustado: qualquer célula da grade (ou cenário) daquele subgrupo.
    fonte_vidas = None
    for cel in resultado.grade_opcao_subgrupo:
        if cel.subgrupo_id == subgrupo_id and cel.vidas:
            fonte_vidas = cel
            break
    if fonte_vidas is None:
        for cenario in resultado.cenarios:
            for secao in cenario.secoes:
                for sg in secao.subgrupos:
                    if sg.subgrupo_id == subgrupo_id and sg.vidas:
                        fonte_vidas = sg
                        break
                if fonte_vidas is not None:
                    break
            if fonte_vidas is not None:
                break

    if fonte_vidas is not None:
        for rv in fonte_vidas.vidas:
            fx = rv.faixa
            if fx is None or fx < 0 or fx > 9:
                continue
            vig = _centavos_valor(rv.atual_vigente_centavos)
            reaj = _centavos_valor(rv.atual_reajustado_centavos)
            if vig is not None:
                vigentes[fx].append(vig)
            if reaj is not None:
                reajustados[fx].append(reaj)

    if resultado.grade_opcao_subgrupo:
        for cel in resultado.grade_opcao_subgrupo:
            if cel.subgrupo_id != subgrupo_id or not cel.opcao_plano_id:
                continue
            for rv in cel.vidas:
                fx = rv.faixa
                if fx is None or fx < 0 or fx > 9:
                    continue
                prop = _centavos_valor(rv.proposta_centavos)
                if prop is not None:
                    propostas[fx][cel.opcao_plano_id].append(prop)
    else:
        for cenario in resultado.cenarios:
            opcao_id, _, _ = _metadados_coluna_cenario(rascunho, cenario.cenario_id)
            if not opcao_id:
                continue
            if opcao_id not in opcao_ids:
                opcao_ids.append(opcao_id)
            for secao in cenario.secoes:
                for sg in secao.subgrupos:
                    if sg.subgrupo_id != subgrupo_id:
                        continue
                    for rv in sg.vidas:
                        fx = rv.faixa
                        if fx is None or fx < 0 or fx > 9:
                            continue
                        prop = _centavos_valor(rv.proposta_centavos)
                        if prop is not None:
                            propostas[fx][opcao_id].append(prop)

    faixas: list[FaixaPlanoComparativo] = []
    for fx in range(10):
        vals_v = vigentes.get(fx, [])
        vals_r = reajustados.get(fx, [])
        if not vals_v and not vals_r and not any(propostas[fx].values()):
            continue
        unit_v, tot_v, obs_v = agregar_valores_faixa(vals_v)
        unit_r, tot_r, obs_r = agregar_valores_faixa(vals_r)
        cols = []
        for op_id in opcao_ids:
            vals_p = propostas[fx].get(op_id, [])
            unit_p, sub_p, _ = agregar_valores_faixa(vals_p)
            cols.append(
                ColunaFaixaPropostaComparativo(
                    opcao_id=op_id,
                    unitario_centavos=unit_p,
                    quantidade=len(vals_p),
                    subtotal_centavos=sub_p,
                )
            )
        faixas.append(
            FaixaPlanoComparativo(
                faixa=fx,
                rotulo=_rotulo_faixa(fx) or "—",
                quantidade=len(vals_v) or len(vals_r) or max((c.quantidade for c in cols), default=0),
                vigente_unitario_centavos=unit_v,
                vigente_total_centavos=tot_v,
                reajustado_unitario_centavos=unit_r,
                reajustado_total_centavos=tot_r,
                observacao_valor=obs_v or obs_r,
                propostas=cols,
            )
        )
    return faixas


def _montar_faixas_seguro_novo_comparativo(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> list[FaixaPlanoComparativo]:
    """Faixas de seguro novo — mesma forma da renovação, sem coluna de contrato atual."""
    if rascunho.formato != "novo":
        return []
    propostas: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    opcao_ids: list[str] = []
    for cenario in resultado.cenarios:
        opcao_id, _, _ = _metadados_coluna_cenario(rascunho, cenario.cenario_id)
        if not opcao_id:
            continue
        if opcao_id not in opcao_ids:
            opcao_ids.append(opcao_id)
        for secao in cenario.secoes:
            for sg in secao.subgrupos:
                for rv in sg.vidas:
                    fx = rv.faixa
                    if fx is None or fx < 0 or fx > 9:
                        continue
                    prop = _centavos_valor(rv.proposta_centavos)
                    if prop is not None:
                        propostas[fx][opcao_id].append(prop)

    faixas: list[FaixaPlanoComparativo] = []
    for fx in range(10):
        if not any(propostas[fx].values()):
            continue
        cols: list[ColunaFaixaPropostaComparativo] = []
        obs: str | None = None
        quantidade = 0
        for op_id in opcao_ids:
            vals_p = propostas[fx].get(op_id, [])
            unit_p, sub_p, obs_p = agregar_valores_faixa(vals_p)
            if obs_p:
                obs = obs_p
            quantidade = max(quantidade, len(vals_p))
            cols.append(
                ColunaFaixaPropostaComparativo(
                    opcao_id=op_id,
                    unitario_centavos=unit_p,
                    quantidade=len(vals_p),
                    subtotal_centavos=sub_p,
                )
            )
        faixas.append(
            FaixaPlanoComparativo(
                faixa=fx,
                rotulo=_rotulo_faixa(fx) or "—",
                quantidade=quantidade,
                observacao_valor=obs,
                propostas=cols,
            )
        )
    return faixas


def _montar_planos_atuais(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> tuple[list[PlanoAtualComparativo], list[PendenciaItem]]:
    if rascunho.formato == "novo" or not rascunho.subgrupos_atuais:
        return [], []

    agregados = [_agregar_subtotais_por_subgrupo(c) for c in resultado.cenarios]
    pendencias: list[PendenciaItem] = []
    if len(agregados) >= 2:
        ids = {sg.id for sg in rascunho.subgrupos_atuais}
        for agg in agregados:
            ids.update(agg)
        divergiu = any(
            len({_chave_contrato_subgrupo(agg.get(sg_id)) for agg in agregados}) > 1
            for sg_id in ids
        )
        if divergiu:
            pendencias.append(
                PendenciaItem(
                    tipo="bloqueio",
                    titulo="Contrato vigente divergente entre cenários",
                    descricao=(
                        "Os subtotais do contrato atual não coincidem em todos os cenários "
                        "calculados. O contrato vigente é o mesmo e deveria produzir os "
                        "mesmos valores em cada proposta."
                    ),
                    acao_sugerida="Recalcule o estudo e revise os planos vigentes.",
                    codigo="APP-CMP-002",
                    etapa=5,
                )
            )

    referencia = next((agg for agg in agregados if agg), {})
    baseline = _baseline_escolhido(rascunho)
    planos: list[PlanoAtualComparativo] = []
    for sg in rascunho.subgrupos_atuais:
        slot = referencia.get(sg.id)
        vigente = _centavos_flag(slot, "vigente", "tem_vigente")
        reajustado = _centavos_flag(slot, "reajustado", "tem_reajustado")
        mensal = reajustado if baseline == "reajustado" else vigente
        planos.append(
            PlanoAtualComparativo(
                subgrupo_id=sg.id,
                plano_nome=sg.plano_nome,
                operadora=sg.operadora,
                acomodacao=sg.acomodacao,
                regime_coparticipacao=_regime_label_rascunho(rascunho, sg.regime_copart_id),
                vidas=_vidas_incluidas_subgrupo(rascunho, sg.id),
                vigente_centavos=vigente,
                reajustado_centavos=reajustado,
                mensal_centavos=mensal,
                vigente_reais=_formatar_reais(vigente) if vigente is not None else None,
                reajustado_reais=_formatar_reais(reajustado) if reajustado is not None else None,
                mensal_reais=_formatar_reais(mensal) if mensal is not None else None,
                faixas=_montar_faixas_plano_comparativo(rascunho, resultado, sg.id),
            )
        )
    return planos, pendencias


def _calcular_destaques(
    propostas: list[ResultadoPropostaComparativo],
    *,
    seguro_novo: bool = False,
) -> None:
    ok = [
        p
        for p in propostas
        if p.calculo_realizado
        and p.numerico
        and p.numerico.proposta_mensal_centavos is not None
    ]
    if len(ok) < 2:
        return

    def _prop_centavos(p: ResultadoPropostaComparativo) -> int:
        assert p.numerico and p.numerico.proposta_mensal_centavos is not None
        return p.numerico.proposta_mensal_centavos

    menor_mensal = min(ok, key=_prop_centavos)
    menor_mensal.destaques.append("menor_mensalidade")

    if seguro_novo:
        return

    aumentos = [
        p
        for p in ok
        if p.numerico
        and p.numerico.diff_mes_centavos is not None
        and p.numerico.diff_mes_centavos > 0
    ]
    if aumentos:
        menor_aumento = min(
            aumentos,
            key=lambda p: p.numerico.diff_mes_centavos if p.numerico else 0,
        )
        menor_aumento.destaques.append("menor_aumento")

    economias = [
        p
        for p in ok
        if p.numerico
        and p.numerico.diff_mes_centavos is not None
        and p.numerico.diff_mes_centavos < 0
    ]
    if economias:
        maior_economia = min(
            economias,
            key=lambda p: p.numerico.diff_mes_centavos if p.numerico else 0,
        )
        maior_economia.destaques.append("maior_economia")

    mais_proximo = min(
        ok,
        key=lambda p: abs(p.numerico.diff_mes_centavos or 0) if p.numerico else 0,
    )
    mais_proximo.destaques.append("mais_proximo_atual")


def _aplicar_diffs_entre_propostas(
    propostas: list[ResultadoPropostaComparativo],
) -> None:
    """Em seguro novo não há base vigente — diferença é contra a menor proposta."""
    ok = [
        p
        for p in propostas
        if p.numerico and p.numerico.proposta_mensal_centavos is not None
    ]
    if not ok:
        return
    menor = min(p.numerico.proposta_mensal_centavos for p in ok)  # type: ignore[union-attr]
    for p in ok:
        assert p.numerico is not None
        prop = p.numerico.proposta_mensal_centavos
        assert prop is not None
        diff = prop - menor
        semantica, rotulo_mes, rotulo_ano = rotulos_diferenca(diff, diff * 12)
        diff_mes_exib = _diff_exibicao_centavos(diff, semantica)
        diff_ano_exib = _diff_exibicao_centavos(diff * 12, semantica)
        p.numerico.diff_mes_centavos = diff
        p.numerico.diff_ano_centavos = diff * 12
        p.numerico.diff_bps = _calcular_diff_bps(menor, prop) if menor else None
        p.numerico.diferenca_semantica = semantica
        if p.totais is not None:
            p.totais.diferenca_mensal_reais = _formatar_reais(diff_mes_exib)
            p.totais.diferenca_anual_reais = _formatar_reais(diff_ano_exib)
            p.totais.diferenca_semantica = semantica
            p.totais.rotulo_diferenca_mensal = rotulo_mes
            p.totais.rotulo_diferenca_anual = rotulo_ano


def _diff_exibicao_centavos(diff_centavos: int, semantica: str) -> int:
    if semantica == "empate":
        return 0
    if semantica == "economia":
        return abs(diff_centavos)
    return diff_centavos


def _montar_totais_cenario(
    cenario: ScenarioResult,
    rascunho: RascunhoEstudo,
    *,
    seguro_novo: bool = False,
) -> TotaisComparativo | None:
    proposta = cenario.total_proposta_centavos
    if not proposta:
        return None
    if seguro_novo:
        return TotaisComparativo(
            proposta_mensal_reais=_formatar_reais(proposta.centavos),
        )
    atual = cenario.total_atual_baseline_centavos
    diff_m = cenario.diff_mes_centavos
    diff_a = cenario.diff_ano_centavos
    if not (atual and diff_m and diff_a):
        return TotaisComparativo(
            proposta_mensal_reais=_formatar_reais(proposta.centavos),
            atual_mensal_reais=_formatar_reais(atual.centavos) if atual else None,
            baseline_rotulo=_baseline_rotulo(rascunho) if atual else None,
        )
    semantica, rotulo_mes, rotulo_ano = rotulos_diferenca(
        diff_m.centavos,
        diff_a.centavos,
    )
    diff_mes_exib = _diff_exibicao_centavos(diff_m.centavos, semantica)
    diff_ano_exib = _diff_exibicao_centavos(diff_a.centavos, semantica)
    return TotaisComparativo(
        atual_mensal_reais=_formatar_reais(atual.centavos),
        proposta_mensal_reais=_formatar_reais(proposta.centavos),
        diferenca_mensal_reais=_formatar_reais(diff_mes_exib),
        diferenca_anual_reais=_formatar_reais(diff_ano_exib),
        diferenca_semantica=semantica,
        rotulo_diferenca_mensal=rotulo_mes,
        rotulo_diferenca_anual=rotulo_ano,
        baseline_rotulo=_baseline_rotulo(rascunho),
    )


def _montar_secoes_cenario(
    rascunho: RascunhoEstudo,
    cenario: ScenarioResult,
) -> tuple[list[SecaoComparativo], int]:
    """Monta seções do comparativo a partir dos subgrupos do motor.

    Em renovação os ids batem com ``subgrupos_atuais``; em seguro novo o motor
    usa ids sintéticos ``novo-{opcao}`` e as vidas vêm nesse agrupamento.
    """
    vidas_por_id = {v.id: v for v in rascunho.vidas}
    subgrupos_por_id = {s.id: s for s in rascunho.subgrupos_atuais}
    seguro_novo = rascunho.formato == "novo"
    secoes: list[SecaoComparativo] = []
    total_benef = 0
    for secao_motor in cenario.secoes:
        detalhes: list[DetalheVidaComparativo] = []
        for sg in secao_motor.subgrupos:
            sg_rasc = None if seguro_novo else subgrupos_por_id.get(sg.subgrupo_id)
            plano_nome = sg_rasc.plano_nome if sg_rasc else None
            baseline = _baseline_escolhido(rascunho)
            for rv in sg.vidas:
                vida = vidas_por_id.get(rv.vida_id)
                if seguro_novo:
                    baseline_val = None
                    diff_val = None
                else:
                    baseline_val = (
                        rv.atual_vigente_centavos
                        if baseline == "vigente"
                        else rv.atual_reajustado_centavos
                    )
                    diff_val = rv.diff_mes_centavos
                detalhes.append(
                    DetalheVidaComparativo(
                        vida_id=rv.vida_id,
                        nome=vida.nome if vida else rv.vida_id,
                        idade=rv.idade,
                        faixa=rv.faixa,
                        faixa_rotulo=_rotulo_faixa(rv.faixa),
                        parentesco=vida.parentesco.value if vida and vida.parentesco else None,
                        plano_atual=plano_nome,
                        subgrupo_id=None if seguro_novo else sg.subgrupo_id,
                        atual_reais=_formatar_reais_opcional(baseline_val),
                        proposta_reais=_formatar_reais_opcional(rv.proposta_centavos),
                        diff_mes_reais=_formatar_reais_opcional(diff_val),
                        atual_centavos=_centavos_valor(baseline_val),
                        vigente_centavos=_centavos_valor(rv.atual_vigente_centavos),
                        reajustado_centavos=_centavos_valor(rv.atual_reajustado_centavos),
                        proposta_centavos=_centavos_valor(rv.proposta_centavos),
                        diff_mes_centavos=_centavos_valor(diff_val),
                    )
                )
        total_benef += len(detalhes)
        semantica = None
        rotulo_mes = None
        diff_mes_exib = None
        diff_ano_exib = None
        if (
            not seguro_novo
            and secao_motor.diff_mes_centavos
            and secao_motor.diff_ano_centavos
        ):
            semantica, rotulo_mes, _ = rotulos_diferenca(
                secao_motor.diff_mes_centavos.centavos,
                secao_motor.diff_ano_centavos.centavos,
            )
            diff_mes_exib = _diff_exibicao_centavos(
                secao_motor.diff_mes_centavos.centavos, semantica
            )
            diff_ano_exib = _diff_exibicao_centavos(
                secao_motor.diff_ano_centavos.centavos, semantica
            )
        secoes.append(
            SecaoComparativo(
                rotulo=secao_motor.rotulo_derivado or _rotulo_regime(secao_motor.regime_tipo.value),
                regime_tipo=secao_motor.regime_tipo.value,
                atual_mensal_reais=(
                    None
                    if seguro_novo
                    else _formatar_reais_opcional(secao_motor.total_atual_baseline_centavos)
                ),
                proposta_mensal_reais=_formatar_reais_opcional(
                    secao_motor.total_proposta_centavos
                ),
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


def _regime_tipo_opcao(rascunho: RascunhoEstudo, opcao_id: str) -> str:
    op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    if op is None or not op.regime_copart_id:
        return "sem"
    for regime in rascunho.regimes_copart:
        if regime.id == op.regime_copart_id:
            return regime.tipo
    return op.regime_copart_id.replace("regime-", "")


def _regime_tipo_cenario(rascunho: RascunhoEstudo, cenario_id: str) -> str:
    cenario = next((c for c in rascunho.cenarios if c.id == cenario_id), None)
    if cenario is None:
        return "sem"
    tipos = {
        _regime_tipo_opcao(rascunho, atr.opcao_plano_id)
        for atr in cenario.atribuicoes
        if atr.opcao_plano_id
    }
    if len(tipos) == 1:
        return tipos.pop()
    return "misto"


def _metadados_coluna_cenario(
    rascunho: RascunhoEstudo,
    cenario_id: str,
) -> tuple[str | None, str, str]:
    from newport_app.rascunho.cenarios_sync import opcao_referencia_cenario, rotulo_cenario

    cenario = next((c for c in rascunho.cenarios if c.id == cenario_id), None)
    if cenario is None:
        return None, "", "sem"
    opcao_id = opcao_referencia_cenario(cenario)
    plano_nome = rotulo_cenario(rascunho, cenario)
    regime_tipo = _regime_tipo_cenario(rascunho, cenario_id)
    return opcao_id, plano_nome, regime_tipo


def _pendencias_proposta(
    *,
    calculo_realizado: bool,
) -> list[PendenciaItem]:
    if calculo_realizado:
        return []
    return [
        PendenciaItem(
            tipo="bloqueio",
            titulo="Proposta não calculada",
            descricao="Este cenário não produziu resultado no motor.",
            acao_sugerida="Revise atribuições e dados da proposta na etapa anterior.",
        )
    ]


def _regime_tipo_opcao(rascunho: RascunhoEstudo, opcao_id: str) -> str:
    op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    if op is None or not op.regime_copart_id:
        return "sem"
    reg = next((r for r in rascunho.regimes_copart if r.id == op.regime_copart_id), None)
    if reg is None:
        return "sem"
    return reg.tipo


def _montar_proposta_de_cenario_motor(
    rascunho: RascunhoEstudo,
    *,
    opcao_id: str,
    cenario_id: str,
    plano_nome: str,
    regime_tipo: str,
    cenario_motor: ScenarioResult | None,
    seguro_novo: bool,
) -> ResultadoPropostaComparativo:
    op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
    calculo_realizado = cenario_motor is not None
    if cenario_motor is None:
        return ResultadoPropostaComparativo(
            opcao_id=opcao_id,
            cenario_id=cenario_id,
            plano_nome=plano_nome or "Proposta sem nome",
            operadora=op.operadora if op else "",
            acomodacao=op.acomodacao if op else None,
            validade_oficial=formatar_data_br(op.validade_oficial) if op else None,
            regime_coparticipacao=(
                _rotulo_regime(regime_tipo)
                if regime_tipo == "misto"
                else (
                    _regime_label_rascunho(
                        rascunho, op.regime_copart_id if op else None
                    )
                    or _rotulo_regime(regime_tipo)
                )
            ),
            regime_tipo=regime_tipo,
            grupo_regime=_grupo_regime(regime_tipo),
            totais=None,
            numerico=None,
            diferenca_percentual=None,
            faixas=[],
            destaques=[],
            secoes=[],
            subgrupos=[],
            pendencias=_pendencias_proposta(calculo_realizado=False),
            calculo_realizado=False,
        )

    secoes, _ = _montar_secoes_cenario(rascunho, cenario_motor)
    recortes = _montar_recortes_subgrupo(rascunho, cenario_motor)
    totais = _montar_totais_cenario(
        cenario_motor, rascunho, seguro_novo=seguro_novo
    )
    numerico = _montar_numerico_cenario(cenario_motor, seguro_novo=seguro_novo)
    diff_pct = None
    if (
        not seguro_novo
        and numerico
        and numerico.atual_mensal_centavos is not None
    ):
        diff_pct = _formatar_percentual(
            numerico.atual_mensal_centavos,
            numerico.proposta_mensal_centavos or 0,
        )
    return ResultadoPropostaComparativo(
        opcao_id=opcao_id,
        cenario_id=cenario_id,
        plano_nome=plano_nome or "Proposta sem nome",
        operadora=op.operadora if op else "",
        acomodacao=op.acomodacao if op else None,
        validade_oficial=formatar_data_br(op.validade_oficial) if op else None,
        regime_coparticipacao=(
            _rotulo_regime(regime_tipo)
            if regime_tipo == "misto"
            else (
                _regime_label_rascunho(
                    rascunho, op.regime_copart_id if op else None
                )
                or _rotulo_regime(regime_tipo)
            )
        ),
        regime_tipo=regime_tipo,
        grupo_regime=_grupo_regime(regime_tipo),
        totais=totais,
        numerico=numerico,
        diferenca_percentual=diff_pct,
        faixas=[],
        destaques=[],
        secoes=secoes,
        subgrupos=recortes,
        pendencias=_pendencias_proposta(calculo_realizado=True),
        calculo_realizado=True,
    )


def _montar_propostas(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> list[ResultadoPropostaComparativo]:
    from newport_app.rascunho.cenarios_sync import opcoes_usadas_nos_cenarios

    seguro_novo = rascunho.formato == "novo"
    propostas: list[ResultadoPropostaComparativo] = []

    # Renovação com grade: uma coluna por plano usado (não por cenário).
    if not seguro_novo and resultado.grade_opcao_subgrupo:
        baseline = _baseline_escolhido(rascunho)
        for opcao_id in opcoes_usadas_nos_cenarios(rascunho):
            regime_tipo = _regime_tipo_opcao(rascunho, opcao_id)
            try:
                regime_enum = RegimeCopartTipo(regime_tipo)
            except ValueError:
                regime_enum = RegimeCopartTipo.SEM
            cenario_motor = cenario_coluna_da_grade(
                resultado.grade_opcao_subgrupo,
                opcao_id,
                regime_tipo=regime_enum,
                baseline=baseline,
            )
            op = next((o for o in rascunho.opcoes_proposta if o.id == opcao_id), None)
            plano_nome = (op.plano_nome if op and op.plano_nome else None) or opcao_id
            propostas.append(
                _montar_proposta_de_cenario_motor(
                    rascunho,
                    opcao_id=opcao_id,
                    cenario_id=f"col-{opcao_id}",
                    plano_nome=plano_nome,
                    regime_tipo=regime_tipo,
                    cenario_motor=cenario_motor,
                    seguro_novo=False,
                )
            )
        _calcular_destaques(propostas, seguro_novo=False)
        qualificar_rotulos_propostas(rascunho, propostas)
        return propostas

    # Seguro novo (ou renovação sem grade): uma coluna por cenário.
    cenarios_motor = {c.cenario_id: c for c in resultado.cenarios}
    for cenario_rasc in rascunho.cenarios:
        opcao_id, plano_nome, regime_tipo = _metadados_coluna_cenario(
            rascunho, cenario_rasc.id
        )
        if not opcao_id:
            continue
        propostas.append(
            _montar_proposta_de_cenario_motor(
                rascunho,
                opcao_id=opcao_id,
                cenario_id=cenario_rasc.id,
                plano_nome=plano_nome,
                regime_tipo=regime_tipo,
                cenario_motor=cenarios_motor.get(cenario_rasc.id),
                seguro_novo=seguro_novo,
            )
        )

    if seguro_novo:
        _aplicar_diffs_entre_propostas(propostas)
    _calcular_destaques(propostas, seguro_novo=seguro_novo)
    qualificar_rotulos_propostas(rascunho, propostas)
    return propostas


_ROTULOS_POLICY: dict[str, str] = {
    "policy.data_referencia_idade": "Data de referência para idade",
    "policy.baseline_escolhido": "Baseline do plano atual",
    "policy.estrategia_arredondamento": "Estratégia de arredondamento",
    "policy.precedencia_atual_vida": "Precedência do valor atual",
}


def _etapa_sugerida_bloqueio(codigo: str, alvo_ref: str | None) -> int | None:
    if codigo == "B-06":
        return 4
    if codigo == "B-07":
        if alvo_ref and alvo_ref.startswith("policy."):
            return 1
        return 2
    if codigo in ("B-02", "B-03", "B-05"):
        if alvo_ref and alvo_ref.startswith("opcao:"):
            return 3
        if alvo_ref and alvo_ref.startswith("subgrupo:"):
            return 2
        return 3
    if codigo == "B-04":
        return 2
    if codigo == "B-08":
        return 1
    return None


def _resolver_alvo_ref(rascunho: RascunhoEstudo, alvo_ref: str | None) -> str | None:
    if not alvo_ref:
        return None
    if alvo_ref in ("estudo", "estudo:cenarios", "estudo:opcoes_plano"):
        return {
            "estudo": "Estudo",
            "estudo:cenarios": "Cenários do estudo",
            "estudo:opcoes_plano": "Opções de plano",
        }[alvo_ref]
    if alvo_ref.startswith("policy."):
        return _ROTULOS_POLICY.get(alvo_ref, alvo_ref.replace("policy.", "Política: "))
    if alvo_ref.startswith("subgrupo:"):
        partes = alvo_ref.split(":")
        sg_id = partes[1]
        for sg in rascunho.subgrupos_atuais:
            if sg.id == sg_id:
                return sg.plano_nome or sg.id
        return sg_id
    if alvo_ref.startswith("opcao:"):
        partes = alvo_ref.split(":")
        op_id = partes[1]
        for op in rascunho.opcoes_proposta:
            if op.id == op_id:
                if len(partes) > 2:
                    return f"{op.plano_nome} ({partes[2]})"
                return op.plano_nome
        return op_id
    if alvo_ref.startswith("cenario:") and ":alvo:" in alvo_ref:
        alvo_id = alvo_ref.split(":alvo:", 1)[1]
        for sg in rascunho.subgrupos_atuais:
            if sg.id == alvo_id:
                return sg.plano_nome or sg.id
        for vida in rascunho.vidas:
            if vida.id == alvo_id:
                return vida.nome or vida.id
        return alvo_id
    if alvo_ref.startswith("cenario:"):
        c_id = alvo_ref.split(":")[1]
        for cenario in rascunho.cenarios:
            if cenario.id == c_id:
                return cenario.rotulo or c_id
        return c_id
    if alvo_ref.startswith("vida:"):
        v_id = alvo_ref.split(":")[1]
        for vida in rascunho.vidas:
            if vida.id == v_id:
                return vida.nome or v_id
        return v_id
    if alvo_ref.startswith("atribuicao:"):
        atr_id = alvo_ref.split(":")[1]
        for cenario in rascunho.cenarios:
            for atr in cenario.atribuicoes:
                if atr.id == atr_id:
                    rotulo = _resolver_alvo_ref(
                        rascunho, f"{atr.alvo_tipo}:{atr.alvo_id}"
                    )
                    return rotulo or atr_id
        return atr_id
    return alvo_ref


_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.I,
)


def _extrair_alvo_id_para_agrupamento(alvo_ref: str | None) -> str | None:
    if not alvo_ref:
        return None
    if ":alvo:" in alvo_ref:
        return alvo_ref.split(":alvo:", 1)[1]
    if alvo_ref.startswith(("subgrupo:", "vida:", "opcao:", "cenario:", "atribuicao:")):
        return alvo_ref.split(":", 1)[1].split(":")[0]
    return alvo_ref


def _humanizar_mensagem_bloqueio(
    mensagem: str,
    alvo_ref: str | None,
    alvo_rotulo: str | None,
) -> str:
    if not mensagem:
        return mensagem
    texto = mensagem
    alvo_id = _extrair_alvo_id_para_agrupamento(alvo_ref)
    if alvo_rotulo and alvo_id and alvo_id in texto:
        texto = texto.replace(alvo_id, f"«{alvo_rotulo}»")
    if alvo_ref and ":alvo:" in alvo_ref and alvo_rotulo and alvo_id:
        texto = re.sub(
            rf"Alvo\s+«{re.escape(alvo_rotulo)}»\s+sem atribuição no cenário\s+\S+\.",
            "Sem atribuição no cenário configurado.",
            texto,
        )
    return texto


def _mensagem_agrupada(codigo: str, quantidade: int, mensagem_base: str) -> str:
    if codigo == "B-06" and quantidade > 1:
        return f"Sem atribuição em {quantidade} cenários."
    if quantidade > 1:
        return f"{mensagem_base} ({quantidade} ocorrências)."
    return mensagem_base


def _detalhe_tecnico_bloqueio(items: list[BloqueioComparativo]) -> str | None:
    """Sempre preserva alvo_ref e mensagem bruta de cada item do grupo."""
    linhas: list[str] = []
    vistos: set[str] = set()
    for item in items:
        if item.alvo_ref and item.alvo_ref not in vistos:
            linhas.append(f"alvo_ref: {item.alvo_ref}")
            vistos.add(item.alvo_ref)
        bruto = item.mensagem_motor or item.mensagem
        if bruto and bruto not in vistos:
            linhas.append(f"motor: {bruto}")
            vistos.add(bruto)
    return "\n".join(linhas) if linhas else None


def _agrupar_bloqueios_comparativo(
    bloqueios: list[BloqueioComparativo],
) -> list[BloqueioComparativo]:
    if not bloqueios:
        return []
    grupos: dict[tuple[str, str | None, str], list[BloqueioComparativo]] = defaultdict(list)
    for bloqueio in bloqueios:
        alvo_chave = _extrair_alvo_id_para_agrupamento(bloqueio.alvo_ref)
        grupos[(bloqueio.codigo, alvo_chave, bloqueio.origem)].append(bloqueio)

    agrupados: list[BloqueioComparativo] = []
    for (_codigo, _alvo, _origem), items in sorted(
        grupos.items(),
        key=lambda par: (par[0][2], par[0][0], par[0][1] or ""),
    ):
        primeiro = items[0]
        quantidade = len(items)
        bruto = primeiro.mensagem_motor or primeiro.mensagem
        mensagem_base = _humanizar_mensagem_bloqueio(
            bruto,
            primeiro.alvo_ref,
            primeiro.alvo_rotulo,
        )
        agrupados.append(
            primeiro.model_copy(
                update={
                    "mensagem": _mensagem_agrupada(
                        primeiro.codigo,
                        quantidade,
                        mensagem_base,
                    ),
                    "mensagem_motor": bruto,
                    "quantidade": quantidade,
                    "detalhe_tecnico": _detalhe_tecnico_bloqueio(items),
                }
            )
        )
    return agrupados


def _extrair_bloqueios_comparativo(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> list[BloqueioComparativo]:
    bloqueios: list[BloqueioComparativo] = []
    for val in resultado.validacoes:
        if val.severidade != SeveridadeValidacao.BLOQUEANTE:
            continue
        trad = _traduzir_validacao(val.codigo, val.mensagem, rascunho, resultado)
        bloqueios.append(
            BloqueioComparativo(
                codigo=val.codigo,
                mensagem=val.mensagem,
                mensagem_motor=val.mensagem,
                severidade=val.severidade.value,
                alvo_ref=val.alvo_ref,
                alvo_rotulo=_resolver_alvo_ref(rascunho, val.alvo_ref),
                etapa_sugerida=_etapa_sugerida_bloqueio(val.codigo, val.alvo_ref),
                acao_sugerida=trad.acao_sugerida,
                origem="motor",
            )
        )
    return _agrupar_bloqueios_comparativo(bloqueios)


def _montar_mensagem_bloqueios(bloqueios: list[BloqueioComparativo]) -> str:
    linhas: list[str] = []
    for bloqueio in bloqueios:
        alvo = f" ({bloqueio.alvo_rotulo})" if bloqueio.alvo_rotulo else ""
        linhas.append(f"{bloqueio.codigo}{alvo}: {bloqueio.mensagem}")
    return "\n".join(linhas)


def _avaliar_consistencia(
    rascunho: RascunhoEstudo,
    propostas: list[ResultadoPropostaComparativo],
    resultado: MotorResult,
    erros_compilacao: list[ErroCompilacao] | None = None,
) -> ConsistenciaComparativo:
    """Consistência do comparativo vs cenários montados (não vs catálogo da etapa 3).

    Após a etapa 4 manual, N propostas selecionadas e M cenários (M≠N) é válido.
    Exige: ao menos um cenário; cada cenário completo produz um resultado no motor.
    Colunas apresentadas = planos usados (grade), não M cenários.
    """
    from newport_app.rascunho.cenarios_sync import opcoes_usadas_nos_cenarios

    erros_compilacao = erros_compilacao or []
    n_propostas = len(rascunho.opcoes_proposta)
    n_cenarios = len(rascunho.cenarios)
    n_resultados_motor = len(resultado.cenarios)
    n_resultados = len([p for p in propostas if p.calculo_realizado])
    n_colunas_esperadas = (
        len(opcoes_usadas_nos_cenarios(rascunho))
        if rascunho.formato != "novo" and resultado.grade_opcao_subgrupo
        else n_cenarios
    )

    mensagem: str | None = None
    consistente = True

    if erros_compilacao:
        consistente = False
        if not mensagem:
            mensagem = (
                "O rascunho não pôde ser compilado — "
                "corrija os campos indicados antes de calcular."
            )

    if n_cenarios == 0:
        consistente = False
        mensagem = (
            "Nenhum cenário configurado. Monte ao menos um na etapa "
            "«Correspondência com os planos atuais»."
        )
    elif n_resultados_motor == 0:
        consistente = False
        if n_cenarios == 1:
            mensagem = (
                "O cenário configurado não produziu resultado — "
                "revise atribuições e pendências bloqueantes."
            )
        else:
            mensagem = (
                f"Os {n_cenarios} cenários configurados não produziram resultado — "
                "revise atribuições e pendências bloqueantes."
            )
    elif n_resultados_motor != n_cenarios:
        consistente = False
        mensagem = (
            f"Configurados {n_cenarios} cenário(s), mas o motor retornou "
            f"{n_resultados_motor} resultado(s)."
        )
    elif n_resultados != n_colunas_esperadas:
        consistente = False
        mensagem = (
            f"Esperados {n_colunas_esperadas} resultado(s) apresentados, "
            f"mas apenas {n_resultados} pôde(m) ser montado(s)."
        )

    bloqueios_compilacao = _agrupar_bloqueios_comparativo(
        bloqueios_comparativo_de_erros(rascunho, erros_compilacao)
    )
    bloqueios_motor = _extrair_bloqueios_comparativo(rascunho, resultado)
    bloqueios = bloqueios_compilacao + bloqueios_motor
    mensagem_contagem: str | None = None
    if n_resultados_motor == 0 and bloqueios:
        mensagem_contagem = mensagem
        mensagem = _montar_mensagem_bloqueios(bloqueios)

    return ConsistenciaComparativo(
        propostas_selecionadas=n_propostas,
        cenarios_configurados=n_cenarios,
        resultados_apresentados=n_resultados,
        consistente=consistente,
        mensagem=mensagem,
        mensagem_contagem=mensagem_contagem,
        bloqueios=bloqueios,
    )


def _validade_proposta(rascunho: RascunhoEstudo) -> str | None:
    for op in rascunho.opcoes_proposta:
        if op.validade_oficial:
            return formatar_data_br(op.validade_oficial)
    return None


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
        if codigo == "B-06":
            acao = (
                "Atribua a proposta a todas as vidas incluídas do estudo."
                if rascunho.formato == "novo"
                else "Atribua a proposta a todos os grupos do estudo."
            )
            descricao = (
                "Nem toda vida incluída está vinculada a uma proposta no cenário."
                if rascunho.formato == "novo"
                else "Nem todo grupo com vidas está vinculado a uma proposta no cenário."
            )
        return PendenciaItem(tipo=tipo, titulo=titulo, descricao=descricao, acao_sugerida=acao)
    return PendenciaItem(
        tipo="bloqueio",
        titulo="Pendência no cálculo",
        descricao=mensagem_motor,
        acao_sugerida="Consulte a auditoria técnica ou corrija os dados do estudo.",
    )


def rascunho_para_resumo(
    rascunho: RascunhoEstudo,
    *,
    ultima_alteracao: str | None = None,
    status: str = "em_andamento",
) -> EstudoResumo:
    from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual

    n = len(rascunho.vidas_incluidas())
    status_map = {
        "em_andamento": "Em andamento",
        "pronto_revisao": "Pronto para revisão",
        "aprovado": "Aprovado",
    }
    empresa = rascunho.empresa_cliente.nome if rascunho.empresa_cliente else None
    # Mesma função da etapa 1 — None em seguro novo / sem reajuste (nunca vigente).
    base = montar_resumo_plano_atual(rascunho)
    return EstudoResumo(
        id=rascunho.id,
        titulo=rascunho.titulo,
        empresa=empresa,
        formato=rascunho.formato,
        formato_exibicao=formatar_tipo_estudo(rascunho.formato),
        beneficiarios_incluidos=n,
        beneficiarios_rotulo=plural_beneficiarios(n),
        descricao=descricao_estudo(rascunho.formato, n),
        status=status,
        status_exibicao=status_map.get(status, "Em andamento"),
        ultima_alteracao=ultima_alteracao,
        total_reajustado_centavos=base.total_reajustado_centavos,
        total_reajustado_reais=base.total_reajustado_reais,
    )


def _motor_result_vazio(rascunho: RascunhoEstudo) -> MotorResult:
    return MotorResult(estudo_id=rascunho.id)


def montar_comparativo(
    rascunho: RascunhoEstudo,
    *,
    motor_result: MotorResult | None = None,
    erros_compilacao: list[ErroCompilacao] | None = None,
) -> ComparativoResponse:
    erros_compilacao = erros_compilacao or []
    resultado = motor_result or _motor_result_vazio(rascunho)

    pendencias: list[PendenciaItem] = []
    if erros_compilacao:
        pendencias.extend(pendencias_compilacao(rascunho))
    else:
        vistos: set[str] = set()
        for val in resultado.validacoes:
            if val.codigo in vistos:
                continue
            vistos.add(val.codigo)
            if val.severidade in (
                SeveridadeValidacao.BLOQUEANTE,
                SeveridadeValidacao.ALERTA,
            ):
                trad = _traduzir_validacao(val.codigo, val.mensagem, rascunho, resultado)
                pendencias.append(
                    PendenciaItem(
                        tipo=trad.tipo,
                        titulo=trad.titulo,
                        descricao=trad.descricao,
                        acao_sugerida=trad.acao_sugerida,
                        codigo=val.codigo,
                        alvo=val.alvo_ref,
                    )
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

    propostas = _montar_propostas(rascunho, resultado) if resultado.cenarios else []
    planos_atuais, pendencias_planos = _montar_planos_atuais(rascunho, resultado)
    faixas_estudo = (
        _montar_faixas_seguro_novo_comparativo(rascunho, resultado)
        if rascunho.formato == "novo" and resultado.cenarios
        else []
    )
    from newport_app.rascunho.acomodacao import (
        pendencias_divergencia_acomodacao,
        pendencias_incompleto_acomodacao,
    )

    consistencia = _avaliar_consistencia(
        rascunho,
        propostas,
        resultado,
        erros_compilacao=erros_compilacao,
    )
    if not erros_compilacao:
        pendencias.extend(pendencias_divergencia_acomodacao(rascunho))
        pendencias.extend(pendencias_incompleto_acomodacao(rascunho))
        from newport_app.services.pendencias import pendencias_propostas_fora_dos_cenarios

        pendencias.extend(pendencias_propostas_fora_dos_cenarios(rascunho))
    pendencias.extend(pendencias_planos)
    if not consistencia.consistente and consistencia.mensagem:
        if not (
            consistencia.bloqueios
            and (len(resultado.cenarios) == 0 or erros_compilacao)
        ):
            pendencias.insert(
                0,
                PendenciaItem(
                    tipo="bloqueio",
                    titulo="Comparativo incompleto",
                    descricao=consistencia.mensagem,
                    acao_sugerida=(
                        "Revise as etapas «Correspondência com os planos atuais» e "
                        "«Cotações» antes de aprovar."
                    ),
                    codigo="APP-CMP-001",
                    etapa=5,
                ),
            )

    primeira = propostas[0] if propostas else None
    totais = primeira.totais if primeira else None
    secoes = primeira.secoes if primeira else []
    beneficiarios_calculados = len(secoes[0].vidas) if secoes and secoes[0].vidas else 0
    if propostas:
        beneficiarios_calculados = max(
            (len(s.vidas) for p in propostas for s in p.secoes if s.vidas),
            default=beneficiarios_calculados,
        )

    calculo_realizado = (
        not erros_compilacao
        and bool(resultado.cenarios)
        and consistencia.consistente
    )

    return ComparativoResponse(
        estudo_id=rascunho.id,
        titulo=rascunho.titulo,
        beneficiarios_calculados=beneficiarios_calculados,
        calculo_realizado=calculo_realizado,
        formato=rascunho.formato,
        totais=totais,
        secoes=secoes,
        propostas=propostas,
        planos_atuais=planos_atuais,
        faixas_estudo=faixas_estudo,
        propostas_apresentacao=ordem_apresentacao_rascunho(rascunho),
        consistencia=consistencia,
        validade_proposta=_validade_proposta(rascunho),
        pendencias=pendencias,
        auditoria=auditoria,
    )


def motor_result_para_comparativo(
    rascunho: RascunhoEstudo,
    resultado: MotorResult,
) -> ComparativoResponse:
    return montar_comparativo(rascunho, motor_result=resultado)
