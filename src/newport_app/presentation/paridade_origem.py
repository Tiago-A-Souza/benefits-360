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


def opcao_atribuida_por_cenario(
    rascunho: RascunhoEstudo,
) -> dict[tuple[str, str], str]:
    """(cenario_id, subgrupo_id) → opção que aquele cenário dá àquele grupo."""
    return {
        (c.id, a.alvo_id): a.opcao_plano_id
        for c in rascunho.cenarios
        for a in c.atribuicoes
        if a.opcao_plano_id and a.alvo_tipo == "subgrupo"
    }


def cenario_por_chave_de_coluna(rascunho: RascunhoEstudo) -> dict[str, str]:
    """Chave de coluna (opção de referência) → cenário.

    Ambíguo exatamente nos casos que `APP-COL-001` sinaliza; aqui fica a
    primeira, igual ao que `builder.py` faz, para que a paridade meça o que o
    documento realmente mostra.
    """
    from newport_app.rascunho.cenarios_sync import opcao_referencia_cenario

    out: dict[str, str] = {}
    for cenario in rascunho.cenarios:
        chave = opcao_referencia_cenario(cenario)
        if chave and chave not in out:
            out[chave] = cenario.id
    return out


def mapa_esperado_por_coluna(
    motor: MotorResult,
    rascunho: RascunhoEstudo,
) -> dict[tuple[str, str], int]:
    """(chave de coluna, subgrupo_id) → subtotal que a coluna deve exibir.

    A ponte entre a grade, indexada por `(opção, subgrupo)`, e a coluna, que
    desde a FASE 3 é um cenário: para cada grupo, a célula da grade do plano que
    aquele cenário atribui àquele grupo.
    """
    grade = mapa_grade_proposta(motor)
    atribuido = opcao_atribuida_por_cenario(rascunho)
    por_chave = cenario_por_chave_de_coluna(rascunho)
    out: dict[tuple[str, str], int] = {}
    for chave, cenario_id in por_chave.items():
        for sg_id in subgrupos_com_vidas(rascunho):
            opcao = atribuido.get((cenario_id, sg_id))
            if opcao is None:
                continue
            valor = grade.get((opcao, sg_id))
            if valor is not None:
                out[(chave, sg_id)] = valor
    return out


def divergencias_coluna_vs_grade(
    matriz: ComparativoResponse,
    motor: MotorResult,
    rascunho: RascunhoEstudo,
) -> list[str]:
    """Cada célula exibida na coluna = célula da grade do plano que o cenário dá àquele grupo.

    Mudou de critério na FASE 3, e ficou mais estrita. Antes, coluna = plano, e a
    chave da célula era `(opcao_id da coluna, subgrupo)` — a mesma opção para
    todos os grupos. Agora, coluna = cenário, e a chave é
    `(opção que o cenário atribui a este subgrupo, subgrupo)`.

    A asserção deixou de aceitar o que era o defeito: sob o critério antigo, uma
    coluna que aplicasse o plano errado a um grupo passava, porque a grade tinha
    aquela célula. Agora a atribuição do cenário é quem escolhe a célula, então
    trocar o plano de um grupo dentro da coluna divergiu.
    """
    if rascunho.formato == "novo":
        return []
    if not motor.grade_opcao_subgrupo:
        return []

    grade = mapa_grade_proposta(motor)
    sgs = subgrupos_com_vidas(rascunho)
    divs: list[str] = []

    colunas = [p for p in matriz.propostas if p.calculo_realizado]
    cenarios_esperados = [
        c.id for c in rascunho.cenarios if any(a.opcao_plano_id for a in c.atribuicoes)
    ]
    ids_col = [p.cenario_id for p in colunas]
    if set(ids_col) != set(cenarios_esperados):
        divs.append(
            f"conjunto_colunas: matriz={sorted(ids_col)} "
            f"cenarios={sorted(cenarios_esperados)}"
        )

    atribuido = {
        (c.id, a.alvo_id): a.opcao_plano_id
        for c in rascunho.cenarios
        for a in c.atribuicoes
        if a.opcao_plano_id and a.alvo_tipo == "subgrupo"
    }

    for prop in colunas:
        por_sg = {
            s.subgrupo_id: s.proposta_centavos
            for s in prop.subgrupos
            if s.proposta_centavos is not None
        }
        soma = 0
        for sg_id in sgs:
            opcao_do_grupo = atribuido.get((prop.cenario_id, sg_id))
            if opcao_do_grupo is None:
                divs.append(f"atribuicao_ausente ({prop.cenario_id}, {sg_id})")
                continue
            chave = (opcao_do_grupo, sg_id)
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
                f"consolidado {prop.cenario_id}: coluna={consolidado} "
                f"soma_grade={soma}"
            )
    return divs


def divergencias_metadado_vs_opcao(
    matriz: ComparativoResponse,
    rascunho: RascunhoEstudo,
) -> list[str]:
    """Nome, acomodação e regime da coluna vêm do cenário; operadora e validade, da opção.

    Adaptada na FASE 3. Com coluna = plano, tudo saía da própria opção. Com
    coluna = cenário, o que descreve a coluna inteira passa a ser agregado sobre
    as atribuições — nome é o rótulo composto, acomodação e regime devolvem
    «misto» quando os grupos divergem. Operadora e validade continuam vindo da
    opção de referência, porque é dela que a montagem as tira.

    A asserção continua sendo contra a origem, não contra outra camada: os
    valores esperados são recalculados aqui a partir do rascunho.
    """
    from newport_app.adapters.motor_out import (
        _acomodacao_cenario,
        _regime_label_rascunho,
        _regime_tipo_cenario,
        _regime_tipo_opcao,
        _rotulo_regime,
    )
    from newport_app.rascunho.cenarios_sync import rotulo_cenario

    divs: list[str] = []
    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    cenarios = {c.id: c for c in rascunho.cenarios}
    for prop in matriz.propostas:
        if not prop.calculo_realizado:
            continue
        op = por_id.get(prop.opcao_id)
        if op is None:
            divs.append(f"metadado: opção ausente {prop.opcao_id}")
            continue
        cenario = cenarios.get(prop.cenario_id)
        if cenario is None:
            divs.append(f"metadado: cenário ausente {prop.cenario_id}")
            continue
        chave = prop.cenario_id
        nome_esp = rotulo_cenario(rascunho, cenario)
        if (prop.plano_nome or "").strip() != (nome_esp or "").strip():
            divs.append(
                f"nome {chave}: coluna={prop.plano_nome!r} cenario={nome_esp!r}"
            )
        if (prop.operadora or "") != (op.operadora or ""):
            divs.append(
                f"operadora {chave}: coluna={prop.operadora!r} "
                f"opcao={op.operadora!r}"
            )
        acomodacao_esp = _acomodacao_cenario(rascunho, prop.cenario_id)
        if (prop.acomodacao or None) != (acomodacao_esp or None):
            divs.append(
                f"acomodacao {chave}: coluna={prop.acomodacao!r} "
                f"cenario={acomodacao_esp!r}"
            )
        validade_esp = (
            formatar_data_br(op.validade_oficial) if op.validade_oficial else None
        )
        if (prop.validade_oficial or None) != (validade_esp or None):
            divs.append(
                f"validade {chave}: coluna={prop.validade_oficial!r} "
                f"opcao={validade_esp!r}"
            )
        regime_tipo = _regime_tipo_cenario(rascunho, prop.cenario_id)
        if prop.regime_tipo != regime_tipo:
            divs.append(
                f"regime_tipo {chave}: coluna={prop.regime_tipo!r} "
                f"cenario={regime_tipo!r}"
            )
        if regime_tipo == "misto":
            rotulo_esp = _rotulo_regime(regime_tipo)
        else:
            rotulo_esp = (
                _regime_label_rascunho(rascunho, op.regime_copart_id)
                or _rotulo_regime(_regime_tipo_opcao(rascunho, prop.opcao_id))
            )
        if prop.regime_coparticipacao != rotulo_esp:
            divs.append(
                f"regime_rotulo {chave}: "
                f"coluna={prop.regime_coparticipacao!r} esperado={rotulo_esp!r}"
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
    esperado = mapa_esperado_por_coluna(motor, rascunho)
    vm_map = mapa_vm_proposta_por_subgrupo(vm)
    divs: list[str] = []
    if not vm_map:
        # Modo resumo: só consolidado
        for secao in vm.secoes_regime:
            for prop in secao.propostas:
                if prop.opcao_id not in vm.propostas_selecionadas:
                    continue
                sgs = subgrupos_com_vidas(rascunho)
                soma = sum(esperado.get((prop.opcao_id, sg), 0) for sg in sgs)
                total = prop.total_mensal_centavos
                if total is None:
                    total = secao.totais.propostas.get(prop.opcao_id)
                if total is not None and total != soma:
                    divs.append(
                        f"vm_consolidado {prop.opcao_id}: vm={total} "
                        f"soma_grade={soma}"
                    )
        return divs

    for chave, esp in esperado.items():
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
    """Confere que os valores que as colunas selecionadas exibem aparecem no HTML.

    Passou a percorrer o esperado por coluna, não a grade crua: com a grade
    restrita aos pares atribuídos, varrer a grade deixaria de fora o valor que a
    coluna de um cenário misto mostra para o segundo grupo.
    """
    if rascunho.formato == "novo" or not motor.grade_opcao_subgrupo:
        return []
    esperado = mapa_esperado_por_coluna(motor, rascunho)
    divs: list[str] = []
    for (oid, sg_id), centavos in esperado.items():
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
