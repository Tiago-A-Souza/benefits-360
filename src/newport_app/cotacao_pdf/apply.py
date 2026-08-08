"""Aplicação de extrações confirmadas ao RascunhoEstudo."""

from __future__ import annotations

import uuid

from newport_app.cotacao_pdf.maturidade import exige_selecao_consciente, opcoes_ativas
from newport_app.cotacao_pdf.validation import pendencias_opcao
from newport_app.models.cotacao_pdf import ExtracaoCotacaoCandidata, OpcaoCotacaoCandidata, ValorExtraido
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    CustoUnicoRascunho,
    DocumentoCotacaoRascunho,
    ModalidadeRascunho,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
    RegimeCopartRascunho,
    TabelaFaixaRascunho,
)


def _validade_documento(extracao: ExtracaoCotacaoCandidata):
    if extracao.validade_oficial and extracao.validade_oficial.data:
        return extracao.validade_oficial.data
    for op in extracao.opcoes:
        if op.validade_oficial and op.validade_oficial.data:
            return op.validade_oficial.data
    return None


def _prov_extraida(
    campo: ValorExtraido | None,
    documento_id: str,
    parser_versao: str,
    documento_hash: str | None,
) -> ProvenienciaRascunho:
    ev = campo.evidencia if campo else None
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.EXTRAIDO,
        documento_id=documento_id,
        extrator_versao=parser_versao or "cotacao-pdf",
        pagina=ev.pagina if ev else None,
        evidencia=ev.trecho if ev else None,
        coordenadas=ev.coordenadas if ev else None,
        confirmado=bool(campo and campo.confirmado),
        confirmado_por=campo.confirmado_por if campo else None,
        confirmado_em=campo.confirmado_em if campo else None,
        documento_hash=(campo.documento_hash if campo else None) or documento_hash,
    )


def _comp(
    campo: ValorExtraido | None,
    documento_id: str,
    parser_versao: str,
    documento_hash: str | None,
) -> ComponenteFinanceiroRascunho | None:
    if campo is None or campo.centavos is None or not campo.confirmado:
        return None
    return ComponenteFinanceiroRascunho(
        centavos=campo.centavos,
        price_basis=campo.price_basis or PriceBasisRascunho.DESCONHECIDO,
        proveniencia=_prov_extraida(campo, documento_id, parser_versao, documento_hash),
    )


def _copart_percentual_opcao(op: OpcaoCotacaoCandidata) -> int | None:
    if op.copart_percentual is None or op.copart_percentual.inteiro is None:
        return None
    return int(op.copart_percentual.inteiro)


def _tipo_regime_canonico(campo: ValorExtraido | None, percentual: int | None) -> str | None:
    """Normaliza tipo comercial: % explícito nunca vira «parcial»."""
    if campo is None or not campo.confirmado or not campo.texto:
        return None
    chave = campo.texto.lower().strip()
    if chave == "parcial" and percentual is not None:
        return "percentual"
    return chave


def _regime_id(campo: ValorExtraido | None, percentual: int | None = None) -> str | None:
    chave = _tipo_regime_canonico(campo, percentual)
    if chave is None:
        return None
    if chave == "percentual":
        if percentual is not None:
            return f"regime-percentual-{percentual}"
        return "regime-percentual"
    mapa = {
        "sem": "regime-sem",
        "parcial": "regime-parcial",
        "customizada": "regime-customizada",
    }
    return mapa.get(chave, f"regime-{chave}")


def _tipo_de_regime_id(regime_id: str) -> str:
    resto = regime_id.removeprefix("regime-")
    for tipo in ("sem", "parcial", "percentual", "customizada"):
        if resto == tipo or resto.startswith(f"{tipo}-"):
            return tipo
    return resto


def _ensure_regime(
    rascunho: RascunhoEstudo,
    regime_id: str | None,
    *,
    percentual: int | None = None,
) -> None:
    if not regime_id:
        return
    if any(r.id == regime_id for r in rascunho.regimes_copart):
        return
    tipo = _tipo_de_regime_id(regime_id)
    rascunho.regimes_copart.append(
        RegimeCopartRascunho(
            id=regime_id,
            tipo=tipo,  # type: ignore[arg-type]
            percentual=percentual if tipo == "percentual" else None,
        )
    )


def _modalidade(campo: ValorExtraido | None) -> ModalidadeRascunho | None:
    if campo is None or not campo.confirmado or not campo.texto:
        return None
    try:
        return ModalidadeRascunho(campo.texto.lower())
    except ValueError:
        return None


def _quantidade_cotada_faixa(fx) -> int | None:
    """Quantidade explícita para o motor — None só se a faixa não entra na tabela."""
    if fx.quantidade.confirmado and fx.quantidade.inteiro is not None:
        return fx.quantidade.inteiro
    if fx.quantidade.inteiro is not None:
        return fx.quantidade.inteiro
    return 0


def opcao_candidata_para_rascunho(
    op: OpcaoCotacaoCandidata,
    *,
    extracao_id: str,
    documento_id: str,
    documento_hash: str | None,
    parser_versao: str,
    opcao_existente_id: str | None = None,
) -> OpcaoPropostaRascunho | None:
    if op.excluida or pendencias_opcao(op):
        return None
    if not op.plano_nome or not op.plano_nome.texto:
        return None

    percentual = _copart_percentual_opcao(op)
    regime_id = _regime_id(op.regime_copart, percentual)
    tipo_fiscal = op.tipo_fiscal.texto if op.tipo_fiscal and op.tipo_fiscal.texto else None
    if regime_id is None or tipo_fiscal is None:
        return None

    tabela: list[TabelaFaixaRascunho] = []
    for fx in op.tabela:
        if fx.valor.centavos is None or not fx.valor.confirmado:
            continue
        tabela.append(
            TabelaFaixaRascunho(
                faixa=fx.faixa,
                valor_centavos=fx.valor.centavos,
                quantidade_cotada=_quantidade_cotada_faixa(fx),
                price_basis=fx.valor.price_basis or PriceBasisRascunho.DESCONHECIDO,
                proveniencia=_prov_extraida(fx.valor, documento_id, parser_versao, documento_hash),
            )
        )
    if not tabela:
        return None

    custos: list[CustoUnicoRascunho] = []
    for idx, custo in enumerate(op.custos_unicos):
        comp = _comp(custo, documento_id, parser_versao, documento_hash)
        if comp is None:
            continue
        custos.append(
            CustoUnicoRascunho(
                id=f"custo-{op.id}-{idx}",
                descricao=custo.rotulo,
                valor=comp,
            )
        )

    return OpcaoPropostaRascunho(
        id=opcao_existente_id or str(uuid.uuid4()),
        operadora=op.operadora.texto if op.operadora and op.operadora.texto else "",
        plano_nome=op.plano_nome.texto or "",
        regime_copart_id=regime_id,
        tipo_fiscal=tipo_fiscal,  # type: ignore[arg-type]
        acomodacao=op.acomodacao.texto if op.acomodacao and op.acomodacao.texto else None,
        modalidade=_modalidade(op.modalidade),
        tabela=tabela,
        premio_saude=_comp(op.premio_saude, documento_id, parser_versao, documento_hash),
        iof=_comp(op.iof, documento_id, parser_versao, documento_hash),
        total_recorrente=_comp(op.total_recorrente, documento_id, parser_versao, documento_hash),
        total_primeira_parcela=_comp(
            op.total_primeira_parcela, documento_id, parser_versao, documento_hash
        ),
        subtotal_impresso=_comp(op.subtotal_impresso, documento_id, parser_versao, documento_hash),
        custos_unicos=custos,
        documento_cotacao_id=documento_id,
        extracao_id=extracao_id,
        extracao_opcao_id=op.id,
        validade_oficial=(
            op.validade_oficial.data if op.validade_oficial and op.validade_oficial.data else None
        ),
        observacoes=op.observacoes.texto if op.observacoes and op.observacoes.texto else None,
    )


def aplicar_extracao_confirmada(
    rascunho: RascunhoEstudo,
    extracao: ExtracaoCotacaoCandidata,
) -> tuple[RascunhoEstudo, list[dict[str, str | list[str]]]]:
    doc = extracao.documento
    bloqueios: list[dict[str, str | list[str]]] = []
    parser_versao = doc.parser_versao or "cotacao-pdf"

    if not any(d.id == doc.id for d in rascunho.documentos_cotacao):
        rascunho.documentos_cotacao.append(
            DocumentoCotacaoRascunho(
                id=doc.id,
                operadora=doc.operadora_detectada or "Desconhecida",
                hash=doc.hash_sha256,
                parser_versao=parser_versao,
                estado_extracao="extraido",
                validade_oficial=_validade_documento(extracao),
                data_emissao=(
                    extracao.data_emissao.data
                    if extracao.data_emissao and extracao.data_emissao.data
                    else None
                ),
            )
        )

    ids_excluidos = {op.id for op in extracao.opcoes if op.excluida}
    rascunho.opcoes_proposta = [
        op
        for op in rascunho.opcoes_proposta
        if not (
            op.extracao_id == extracao.id
            and op.extracao_opcao_id
            and op.extracao_opcao_id in ids_excluidos
        )
    ]

    ativas = opcoes_ativas(extracao)
    ja_no_rascunho = any(op.extracao_id == extracao.id for op in rascunho.opcoes_proposta)
    selecionadas_explicitas = [o for o in ativas if o.selecionada_para_comparativo]

    if exige_selecao_consciente(extracao):
        if not selecionadas_explicitas:
            if ja_no_rascunho:
                ids_aplicaveis: set[str] = set()
            else:
                bloqueios.append(
                    {
                        "opcao_id": "",
                        "plano": "Seleção de planos",
                        "motivos": [
                            "Selecione conscientemente quais planos levar ao comparativo "
                            "(documento com tabela geral extensa)."
                        ],
                    }
                )
                return rascunho, bloqueios
        else:
            ids_aplicaveis = {o.id for o in selecionadas_explicitas}
    elif selecionadas_explicitas:
        ids_aplicaveis = {o.id for o in selecionadas_explicitas}
    else:
        ids_aplicaveis = {o.id for o in ativas}

    ids_removidos = {
        op.id
        for op in rascunho.opcoes_proposta
        if op.extracao_id == extracao.id
        and op.extracao_opcao_id
        and op.extracao_opcao_id not in ids_aplicaveis
    }
    if ids_removidos:
        rascunho.opcoes_proposta = [
            op for op in rascunho.opcoes_proposta if op.id not in ids_removidos
        ]
        opcoes_validas = {op.id for op in rascunho.opcoes_proposta}
        for cenario in rascunho.cenarios:
            cenario.atribuicoes = [
                atr for atr in cenario.atribuicoes if atr.opcao_plano_id in opcoes_validas
            ]

    for op_c in extracao.opcoes:
        if op_c.excluida or op_c.id not in ids_aplicaveis:
            continue
        pendencias = pendencias_opcao(op_c)
        if pendencias:
            bloqueios.append(
                {
                    "opcao_id": op_c.id,
                    "plano": (op_c.plano_nome.texto if op_c.plano_nome else "Proposta"),
                    "motivos": pendencias,
                }
            )
            continue

        percentual = _copart_percentual_opcao(op_c)
        regime_id = _regime_id(op_c.regime_copart, percentual)
        _ensure_regime(rascunho, regime_id, percentual=percentual)

        existente = next(
            (
                o
                for o in rascunho.opcoes_proposta
                if o.extracao_id == extracao.id and o.extracao_opcao_id == op_c.id
            ),
            None,
        )
        opcao = opcao_candidata_para_rascunho(
            op_c,
            extracao_id=extracao.id,
            documento_id=doc.id,
            documento_hash=doc.hash_sha256,
            parser_versao=parser_versao,
            opcao_existente_id=existente.id if existente else None,
        )
        if opcao is None:
            bloqueios.append(
                {
                    "opcao_id": op_c.id,
                    "plano": (op_c.plano_nome.texto if op_c.plano_nome else "Proposta"),
                    "motivos": ["Não foi possível montar a proposta — revise os campos."],
                }
            )
            continue

        if existente is not None:
            idx = rascunho.opcoes_proposta.index(existente)
            rascunho.opcoes_proposta[idx] = opcao
        else:
            rascunho.opcoes_proposta.append(opcao)

    return rascunho, bloqueios
