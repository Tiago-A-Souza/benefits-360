"""Indicadores do resumo executivo — nascem do ViewModel / ComparativoResponse.

Mesma estrutura da matriz (ComparativoExperiencia): linhas de cabeçalho +
validade. O renderer e a paridade leem estes dados; não há lista de nomes
esperados no teste.
"""

from __future__ import annotations

from newport_app.models.presentation import (
    CelulaIndicadorResumo,
    LinhaIndicadorResumo,
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
)
from newport_app.models.responses import ComparativoResponse

_PLANO_SINTETICO = "vidas-incluidas"
AUSENCIA = "—"


def _texto_ou_ausente(valor: str | None) -> CelulaIndicadorResumo:
    texto = (valor or "").strip()
    if not texto:
        return CelulaIndicadorResumo(ausente=True, texto=AUSENCIA)
    return CelulaIndicadorResumo(texto=texto)


def _valor_unico(valores: list[str | None]) -> str | None:
    limpos = sorted({(v or "").strip() for v in valores if (v or "").strip()})
    if len(limpos) == 1:
        return limpos[0]
    return None


def _cel_centavos(
    centavos: int | None, *, bps: int | None = None, referencia_se_zero: bool = False
) -> CelulaIndicadorResumo:
    if centavos is None and bps is None:
        return CelulaIndicadorResumo(ausente=True, texto=AUSENCIA)
    if referencia_se_zero and centavos == 0:
        return CelulaIndicadorResumo(referencia=True, centavos=0, bps=bps)
    return CelulaIndicadorResumo(centavos=centavos, bps=bps)


def _planos_reais(secao: SecaoRegimeApresentacao) -> list[PlanoAtualApresentacao]:
    return [p for p in secao.planos_atuais if p.subgrupo_id != _PLANO_SINTETICO]


def montar_indicadores_resumo(
    model: PresentationViewModel,
    secao: SecaoRegimeApresentacao,
    op_ids: list[str],
) -> list[LinhaIndicadorResumo]:
    """Monta as linhas de indicador a partir dos campos já no VM."""
    seguro_novo = model.formato == "novo"
    props = {
        p.opcao_id: p
        for p in secao.propostas
        if p.opcao_id in op_ids
    }
    planos = _planos_reais(secao)
    linhas: list[LinhaIndicadorResumo] = []

    # --- Cabeçalho fixo (espelha DetalhesFixosMatriz) -----------------------
    acomod_atual = (
        None
        if seguro_novo
        else _texto_ou_ausente(_valor_unico([p.acomodacao for p in planos]))
    )
    linhas.append(
        LinhaIndicadorResumo(
            rotulo="Acomodação",
            atual=acomod_atual,
            propostas={
                oid: _texto_ou_ausente(props[oid].acomodacao if oid in props else None)
                for oid in op_ids
            },
        )
    )

    copart_atual = (
        None
        if seguro_novo
        else _texto_ou_ausente(_valor_unico([p.copart_descricao for p in planos]))
    )
    linhas.append(
        LinhaIndicadorResumo(
            rotulo="Coparticipação",
            atual=copart_atual,
            propostas={
                oid: _texto_ou_ausente(
                    props[oid].copart_descricao if oid in props else None
                )
                for oid in op_ids
            },
        )
    )

    custo_atual_centavos: int | None = None
    if not seguro_novo:
        custo_atual_centavos = secao.totais.atual_centavos
        if custo_atual_centavos is None:
            vals = [p.subtotal_reajustado_centavos for p in planos]
            if any(v is not None for v in vals):
                custo_atual_centavos = sum(v or 0 for v in vals)
    linhas.append(
        LinhaIndicadorResumo(
            rotulo="Custo total mensal",
            atual=(
                None
                if seguro_novo
                else _cel_centavos(custo_atual_centavos)
            ),
            propostas={
                oid: _cel_centavos(
                    (props[oid].total_mensal_centavos if oid in props else None)
                    if oid in props
                    else secao.totais.propostas.get(oid)
                )
                for oid in op_ids
            },
            destaque=True,
        )
    )

    rotulo_variacao = (
        "Diferença vs menor proposta" if seguro_novo else "Variação do custo"
    )
    linhas.append(
        LinhaIndicadorResumo(
            rotulo=rotulo_variacao,
            atual=(
                None
                if seguro_novo
                else CelulaIndicadorResumo(texto="Referência", referencia=True)
            ),
            propostas={
                oid: _cel_centavos(
                    props[oid].diff_mensal_centavos if oid in props else None,
                    bps=(
                        None
                        if seguro_novo
                        else (props[oid].diff_bps if oid in props else None)
                    ),
                    referencia_se_zero=seguro_novo,
                )
                for oid in op_ids
            },
        )
    )

    # --- Rodapé do resumo (espelha o tbody de dados da matriz) --------------
    if seguro_novo:
        linhas.append(
            LinhaIndicadorResumo(
                rotulo="Diferença vs menor (mês)",
                atual=None,
                grupo="rodape",
                propostas={
                    oid: _cel_centavos(
                        secao.totais.diff_mensal.get(oid)
                        if secao.totais.diff_mensal.get(oid) is not None
                        else (props[oid].diff_mensal_centavos if oid in props else None),
                        referencia_se_zero=True,
                    )
                    for oid in op_ids
                },
            )
        )
        linhas.append(
            LinhaIndicadorResumo(
                rotulo="Diferença vs menor (ano)",
                atual=None,
                grupo="rodape",
                propostas={
                    oid: _cel_centavos(
                        secao.totais.diff_anual.get(oid)
                        if secao.totais.diff_anual.get(oid) is not None
                        else (props[oid].diff_anual_centavos if oid in props else None),
                        referencia_se_zero=True,
                    )
                    for oid in op_ids
                },
            )
        )
    else:
        linhas.append(
            LinhaIndicadorResumo(
                rotulo="Diferença mensal",
                atual=CelulaIndicadorResumo(texto="referência", referencia=True),
                grupo="rodape",
                propostas={
                    oid: _cel_centavos(
                        model.totais_gerais.diff_mensal.get(oid)
                        if model.totais_gerais.diff_mensal.get(oid) is not None
                        else secao.totais.diff_mensal.get(oid)
                    )
                    for oid in op_ids
                },
            )
        )
        linhas.append(
            LinhaIndicadorResumo(
                rotulo="Diferença anual",
                atual=CelulaIndicadorResumo(ausente=True, texto=""),
                grupo="rodape",
                propostas={
                    oid: _cel_centavos(
                        model.totais_gerais.diff_anual.get(oid)
                        if model.totais_gerais.diff_anual.get(oid) is not None
                        else secao.totais.diff_anual.get(oid)
                    )
                    for oid in op_ids
                },
            )
        )

    linhas.append(
        LinhaIndicadorResumo(
            rotulo="Validade da cotação",
            atual=(
                None
                if seguro_novo
                else CelulaIndicadorResumo(ausente=True, texto=AUSENCIA)
            ),
            grupo="rodape",
            propostas={
                oid: _texto_ou_ausente(props[oid].validade if oid in props else None)
                for oid in op_ids
            },
        )
    )
    return linhas


def rotulos_indicadores_matriz(matriz: ComparativoResponse) -> frozenset[str]:
    """Conjunto de indicadores que a matriz exibe no resumo — derivado do payload."""
    seguro_novo = matriz.formato == "novo"
    rotulos: set[str] = {
        "Acomodação",
        "Coparticipação",
        "Custo total mensal",
        "Diferença vs menor proposta" if seguro_novo else "Variação do custo",
        "Validade da cotação",
    }
    if seguro_novo:
        rotulos.add("Diferença vs menor (mês)")
        rotulos.add("Diferença vs menor (ano)")
    else:
        for pl in matriz.planos_atuais:
            if pl.plano_nome:
                rotulos.add(pl.plano_nome)
        if matriz.planos_atuais:
            rotulos.add("Consolidado")
        rotulos.add("Diferença mensal")
        rotulos.add("Diferença anual")
    return frozenset(rotulos)


def rotulos_indicadores_vm(vm: PresentationViewModel) -> frozenset[str]:
    """Rótulos de indicador no VM (linhas montadas + planos/consolidado)."""
    rotulos: set[str] = set()
    seguro_novo = vm.formato == "novo"
    for secao in vm.secoes_regime:
        for lin in secao.indicadores_resumo:
            rotulos.add(lin.rotulo)
        if not seguro_novo:
            for pl in _planos_reais(secao):
                if pl.plano_nome:
                    rotulos.add(pl.plano_nome)
            if _planos_reais(secao):
                rotulos.add("Consolidado")
    return frozenset(rotulos)


def rotulos_indicadores_html(html_doc: str) -> frozenset[str]:
    """Primeira coluna das tabelas de resumo executivo no documento."""
    import re

    rotulos: set[str] = set()
    # Escopo: seções de resumo (modo resumo ou aba visao-resumo).
    blocos = re.findall(
        r"<section class='secao-regime'>(.*?)</section>",
        html_doc,
        flags=re.DOTALL,
    )
    if not blocos:
        blocos = re.findall(
            r'id="visao-resumo"[^>]*>(.*?)</section>\s*<section class="visao',
            html_doc,
            flags=re.DOTALL,
        ) or [html_doc]
    for bloco in blocos:
        if "Resumo executivo" not in bloco and "Indicador" not in bloco:
            # Seguro novo / tabela única ainda conta.
            pass
        for m in re.finditer(
            r"<tr[^>]*>\s*<t[dh][^>]*>\s*(?:<strong>)?(.*?)(?:</strong>)?\s*</t[dh]>",
            bloco,
            flags=re.DOTALL | re.IGNORECASE,
        ):
            if 'linha-topo-extra' in m.group(0) or 'bloco-plano' in m.group(0) or 'bloco-regime' in m.group(0):
                continue
            bruto = re.sub(r"<[^>]+>", "", m.group(1))
            texto = re.sub(r"\s+", " ", bruto).strip()
            if texto and texto not in {"Indicador", "Proposta"}:
                rotulos.add(texto)
    return frozenset(rotulos)


def divergencias_indicadores_resumo(
    *,
    matriz: ComparativoResponse | None = None,
    vm: PresentationViewModel | None = None,
    html: str | None = None,
) -> list[str]:
    """Compara conjuntos de indicadores — um lado contra o outro, sem lista fixa."""
    divs: list[str] = []
    lados: list[tuple[str, frozenset[str]]] = []
    if matriz is not None:
        lados.append(("matriz", rotulos_indicadores_matriz(matriz)))
    if vm is not None and vm.modo in {"resumo", "completo"}:
        # VM de faixas/beneficiario não monta indicadores_resumo na seção.
        if any(s.indicadores_resumo for s in vm.secoes_regime) or vm.modo == "resumo":
            lados.append(("vm", rotulos_indicadores_vm(vm)))
    if html is not None and vm is not None and vm.modo == "resumo":
        lados.append(("html", rotulos_indicadores_html(html)))
    elif html is not None and matriz is not None:
        lados.append(("html", rotulos_indicadores_html(html)))

    if len(lados) < 2:
        return divs
    ref_nome, ref = lados[0]
    for nome, conj in lados[1:]:
        if conj == ref:
            continue
        so_ref = sorted(ref - conj)
        so_outro = sorted(conj - ref)
        divs.append(
            f"indicadores_resumo {ref_nome}↔{nome}: "
            f"{ref_nome}={sorted(ref)} {nome}={sorted(conj)}"
            + (f" só_{ref_nome}={so_ref}" if so_ref else "")
            + (f" só_{nome}={so_outro}" if so_outro else "")
        )
    return divs
