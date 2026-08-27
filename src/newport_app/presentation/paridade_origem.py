"""Paridade contra a origem — coluna ↔ grade e grade ↔ recálculo puro.

Fecha a cegueira do caminho compartilhado: matriz/VM/HTML todos vêm de
``_montar_propostas``. Comparar camadas entre si não detecta erro simétrico.
Aqui a referência é a ``grade_opcao_subgrupo`` (e, para a grade em si, o
recálculo via ``_calcular_subgrupo_renovacao``).
"""

from __future__ import annotations

from typing import Any

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import PresentationViewModel
from newport_app.models.responses import ComparativoResponse
from newport_app.presentation.formatacao import formatar_data_br, formatar_reais
from newport_app.rascunho.cenarios_sync import (
    opcoes_usadas_nos_cenarios,
    subgrupos_com_vidas,
)
from newport_motor.calculation import _calcular_subgrupo_renovacao
from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy
from newport_motor.result import MotorResult


def _centavos(valor: Any) -> int | None:
    if valor is None:
        return None
    if isinstance(valor, int):
        return valor
    return getattr(valor, "centavos", None)


def mapa_grade_proposta(
    motor: MotorResult,
) -> dict[tuple[str, str], int]:
    """(opcao_plano_id, subgrupo_id) → subtotal_proposta_centavos."""
    out: dict[tuple[str, str], int] = {}
    for cel in motor.grade_opcao_subgrupo:
        if not cel.opcao_plano_id:
            continue
        prop = _centavos(cel.subtotal_proposta_centavos)
        if prop is None:
            continue
        out[(cel.opcao_plano_id, cel.subgrupo_id)] = prop
    return out


def divergencias_coluna_vs_grade(
    matriz: ComparativoResponse,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
) -> list[str]:
    """Cada célula exibida na coluna = célula da grade na mesma chave."""
    if rascunho.formato == "novo":
        return []
    if not motor.grade_opcao_subgrupo:
        return []

    grade = mapa_grade_proposta(motor)
    sgs = subgrupos_com_vidas(rascunho)
    usadas = opcoes_usadas_nos_cenarios(rascunho)
    divs: list[str] = []

    colunas = [p for p in matriz.propostas if p.calculo_realizado]
    ids_col = [p.opcao_id for p in colunas]
    if set(ids_col) != set(usadas):
        divs.append(
            f"conjunto_colunas: matriz={sorted(ids_col)} usadas={usadas}"
        )

    for prop in colunas:
        por_sg = {
            s.subgrupo_id: s.proposta_centavos
            for s in prop.subgrupos
            if s.proposta_centavos is not None
        }
        soma = 0
        for sg_id in sgs:
            chave = (prop.opcao_id, sg_id)
            esperado = grade.get(chave)
            obtido = por_sg.get(sg_id)
            if esperado is None:
                divs.append(f"grade_ausente {chave}")
                continue
            if obtido != esperado:
                divs.append(
                    f"coluna_vs_grade {chave}: coluna={obtido} grade={esperado}"
                )
            else:
                soma += esperado
        consolidado = (
            prop.numerico.proposta_mensal_centavos if prop.numerico else None
        )
        if consolidado is not None and consolidado != soma:
            divs.append(
                f"consolidado {prop.opcao_id}: coluna={consolidado} "
                f"soma_grade={soma}"
            )
    return divs


def divergencias_metadado_vs_opcao(
    matriz: ComparativoResponse,
    rascunho: RascunhoEstudo,
) -> list[str]:
    """Acomodação, operadora, regime, nome e validade vêm da própria opção."""
    from newport_app.adapters.motor_out import (
        _regime_label_rascunho,
        _regime_tipo_opcao,
        _rotulo_regime,
    )

    divs: list[str] = []
    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    for prop in matriz.propostas:
        if not prop.calculo_realizado:
            continue
        op = por_id.get(prop.opcao_id)
        if op is None:
            divs.append(f"metadado: opção ausente {prop.opcao_id}")
            continue
        nome_esp = op.plano_nome or op.id
        if (prop.plano_nome or "").strip() != (nome_esp or "").strip():
            divs.append(
                f"nome {prop.opcao_id}: coluna={prop.plano_nome!r} "
                f"opcao={nome_esp!r}"
            )
        if (prop.operadora or "") != (op.operadora or ""):
            divs.append(
                f"operadora {prop.opcao_id}: coluna={prop.operadora!r} "
                f"opcao={op.operadora!r}"
            )
        if (prop.acomodacao or None) != (op.acomodacao or None):
            divs.append(
                f"acomodacao {prop.opcao_id}: coluna={prop.acomodacao!r} "
                f"opcao={op.acomodacao!r}"
            )
        validade_esp = (
            formatar_data_br(op.validade_oficial) if op.validade_oficial else None
        )
        if (prop.validade_oficial or None) != (validade_esp or None):
            divs.append(
                f"validade {prop.opcao_id}: coluna={prop.validade_oficial!r} "
                f"opcao={validade_esp!r}"
            )
        regime_tipo = _regime_tipo_opcao(rascunho, prop.opcao_id)
        if prop.regime_tipo != regime_tipo:
            divs.append(
                f"regime_tipo {prop.opcao_id}: coluna={prop.regime_tipo!r} "
                f"opcao={regime_tipo!r}"
            )
        rotulo_esp = (
            _regime_label_rascunho(rascunho, op.regime_copart_id)
            or _rotulo_regime(regime_tipo)
        )
        if prop.regime_coparticipacao != rotulo_esp:
            divs.append(
                f"regime_rotulo {prop.opcao_id}: "
                f"coluna={prop.regime_coparticipacao!r} opcao={rotulo_esp!r}"
            )
    return divs


def divergencias_grade_vs_recalculo(
    motor: MotorResult,
    estudo: EstudoInput,
    policy: EffectivePolicy,
) -> list[str]:
    """Cada célula da grade = recálculo puro do mesmo (opção, subgrupo)."""
    if estudo.formato.value == "novo" if hasattr(estudo.formato, "value") else estudo.formato == "novo":
        return []
    divs: list[str] = []
    for cel in motor.grade_opcao_subgrupo:
        if not cel.opcao_plano_id:
            continue
        opcao = estudo.opcao_por_id(cel.opcao_plano_id)
        subgrupo = estudo.subgrupo_por_id(cel.subgrupo_id)
        if opcao is None or subgrupo is None:
            divs.append(
                f"recalculo_refs_ausentes ({cel.opcao_plano_id}, {cel.subgrupo_id})"
            )
            continue
        fresco = _calcular_subgrupo_renovacao(estudo, subgrupo, opcao, policy)
        esp = _centavos(fresco.subtotal_proposta_centavos)
        obt = _centavos(cel.subtotal_proposta_centavos)
        if esp != obt:
            divs.append(
                f"grade_vs_recalculo ({cel.opcao_plano_id}, {cel.subgrupo_id}): "
                f"grade={obt} recalculo={esp}"
            )
    return divs


def mapa_vm_proposta_por_subgrupo(
    vm: PresentationViewModel,
) -> dict[tuple[str, str], int]:
    """Agrega subtotais de faixa por (opcao_id, subgrupo_id) no VM."""
    acc: dict[tuple[str, str], int] = {}
    for secao in vm.secoes_regime:
        for plano in secao.planos_atuais:
            if plano.subgrupo_id == "vidas-incluidas":
                continue
            for fx in plano.faixas:
                for col in fx.propostas:
                    if col.subtotal_centavos is None:
                        continue
                    chave = (col.opcao_id, plano.subgrupo_id)
                    acc[chave] = acc.get(chave, 0) + col.subtotal_centavos
    if acc:
        return acc
    # Fallback beneficiário: soma por vida → subgrupo
    for ben in vm.beneficiarios:
        if not ben.subgrupo_id:
            continue
        for col in ben.propostas:
            if col.valor_centavos is None:
                continue
            chave = (col.opcao_id, ben.subgrupo_id)
            acc[chave] = acc.get(chave, 0) + col.valor_centavos
    return acc


def divergencias_vm_vs_grade(
    vm: PresentationViewModel,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
) -> list[str]:
    if rascunho.formato == "novo" or not motor.grade_opcao_subgrupo:
        return []
    grade = mapa_grade_proposta(motor)
    vm_map = mapa_vm_proposta_por_subgrupo(vm)
    divs: list[str] = []
    if not vm_map:
        # Modo resumo: só consolidado
        for secao in vm.secoes_regime:
            for prop in secao.propostas:
                if prop.opcao_id not in vm.propostas_selecionadas:
                    continue
                sgs = subgrupos_com_vidas(rascunho)
                soma = sum(grade.get((prop.opcao_id, sg), 0) for sg in sgs)
                total = prop.total_mensal_centavos
                if total is None:
                    total = secao.totais.propostas.get(prop.opcao_id)
                if total is not None and total != soma:
                    divs.append(
                        f"vm_consolidado {prop.opcao_id}: vm={total} "
                        f"soma_grade={soma}"
                    )
        return divs

    for chave, esp in grade.items():
        if chave[0] not in vm.propostas_selecionadas:
            continue
        obt = vm_map.get(chave)
        if obt != esp:
            divs.append(f"vm_vs_grade {chave}: vm={obt} grade={esp}")
    return divs


def divergencias_html_vs_grade(
    html: str,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
    opcao_ids: list[str],
) -> list[str]:
    """Confere que os valores da grade das opções selecionadas aparecem no HTML."""
    if rascunho.formato == "novo" or not motor.grade_opcao_subgrupo:
        return []
    grade = mapa_grade_proposta(motor)
    divs: list[str] = []
    for (oid, sg_id), centavos in grade.items():
        if oid not in opcao_ids:
            continue
        texto = formatar_reais(centavos)
        if texto not in html:
            divs.append(
                f"html_vs_grade ({oid}, {sg_id}): valor {texto} ausente no HTML"
            )
    return divs


def divergencias_planos_atuais_vs_fonte(
    matriz: ComparativoResponse,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
) -> list[str]:
    """Planos vigentes da matriz = subgrupos com vidas; valores = motor."""
    if rascunho.formato == "novo":
        return []
    divs: list[str] = []
    sgs = subgrupos_com_vidas(rascunho)
    ids_matriz = [p.subgrupo_id for p in matriz.planos_atuais]
    if set(ids_matriz) != set(sgs):
        divs.append(
            f"planos_atuais_conjunto: matriz={sorted(ids_matriz)} "
            f"esperados={sgs}"
        )
    # Valores vigentes/reajustados: qualquer cenário (ou grade) do subgrupo
    ref: dict[str, tuple[int | None, int | None]] = {}
    fonte = motor.cenarios[0] if motor.cenarios else None
    if fonte is not None:
        for secao in fonte.secoes:
            for sg in secao.subgrupos:
                ref[sg.subgrupo_id] = (
                    _centavos(sg.subtotal_atual_vigente_centavos),
                    _centavos(sg.subtotal_atual_reajustado_centavos),
                )
    for pl in matriz.planos_atuais:
        esp = ref.get(pl.subgrupo_id)
        if esp is None:
            continue
        vig_e, reaj_e = esp
        if pl.vigente_centavos is not None and vig_e is not None and pl.vigente_centavos != vig_e:
            divs.append(
                f"plano_vigente {pl.subgrupo_id}: matriz={pl.vigente_centavos} "
                f"motor={vig_e}"
            )
        if (
            pl.reajustado_centavos is not None
            and reaj_e is not None
            and pl.reajustado_centavos != reaj_e
        ):
            divs.append(
                f"plano_reajustado {pl.subgrupo_id}: matriz={pl.reajustado_centavos} "
                f"motor={reaj_e}"
            )
    return divs


def divergencias_origem_completas(
    *,
    matriz: ComparativoResponse,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
    estudo: EstudoInput | None = None,
    policy: EffectivePolicy | None = None,
    vm: PresentationViewModel | None = None,
    html: str | None = None,
    opcao_ids: list[str] | None = None,
) -> list[str]:
    """Todas as asserções de origem aplicáveis."""
    divs: list[str] = []
    divs.extend(divergencias_coluna_vs_grade(matriz, motor, rascunho))
    divs.extend(divergencias_metadado_vs_opcao(matriz, rascunho))
    divs.extend(divergencias_planos_atuais_vs_fonte(matriz, motor, rascunho))
    if estudo is not None and policy is not None:
        divs.extend(divergencias_grade_vs_recalculo(motor, estudo, policy))
    if vm is not None:
        divs.extend(divergencias_vm_vs_grade(vm, motor, rascunho))
    if html is not None and opcao_ids is not None:
        divs.extend(divergencias_html_vs_grade(html, motor, rascunho, opcao_ids))
    return divs
