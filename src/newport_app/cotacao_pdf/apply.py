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


def _regime_id(campo: ValorExtraido | None) -> str | None:
    if campo is None or not campo.confirmado or not campo.texto:
        return None
    mapa = {
        "sem": "regime-sem",
        "parcial": "regime-parcial",
        "percentual": "regime-percentual",
        "customizada": "regime-customizada",
    }
    chave = campo.texto.lower().strip()
    return mapa.get(chave, f"regime-{chave}")


def _ensure_regime(rascunho: RascunhoEstudo, regime_id: str | None) -> None:
    if not regime_id:
        return
    tipo = regime_id.replace("regime-", "")
    if not any(r.id == regime_id for r in rascunho.regimes_copart):
        rascunho.regimes_copart.append(RegimeCopartRascunho(id=regime_id, tipo=tipo))  # type: ignore[arg-type]


def _modalidade(campo: ValorExtraido | None) -> ModalidadeRascunho | None:
    if campo is None or not campo.confirmado or not campo.texto:
        return None
    try:
        return ModalidadeRascunho(campo.texto.lower())
    except ValueError:
        return None


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

    regime_id = _regime_id(op.regime_copart)
    tipo_fiscal = (
        op.tipo_fiscal.texto if op.tipo_fiscal and op.tipo_fiscal.confirmado else None
    )
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
                quantidade_cotada=(
                    fx.quantidade.inteiro if fx.quantidade.confirmado else None
                ),
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
        operadora=op.operadora.texto if op.operadora and op.operadora.confirmado else "",
        plano_nome=op.plano_nome.texto or "",
        regime_copart_id=regime_id,
        tipo_fiscal=tipo_fiscal,  # type: ignore[arg-type]
        acomodacao=op.acomodacao.texto if op.acomodacao and op.acomodacao.confirmado else None,
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
            op.validade_oficial.data
            if op.validade_oficial and op.validade_oficial.confirmado
            else None
        ),
        observacoes=op.observacoes.texto if op.observacoes and op.observacoes.confirmado else None,
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
                validade_oficial=(
                    extracao.validade_oficial.data
                    if extracao.validade_oficial and extracao.validade_oficial.confirmado
                    else None
                ),
                data_emissao=(
                    extracao.data_emissao.data
                    if extracao.data_emissao and extracao.data_emissao.confirmado
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
    if exige_selecao_consciente(extracao):
        selecionadas = [o for o in ativas if o.selecionada_para_comparativo]
        if not selecionadas:
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
        ids_aplicaveis = {o.id for o in selecionadas}
    else:
        ids_aplicaveis = {o.id for o in ativas}

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

        regime_id = _regime_id(op_c.regime_copart)
        _ensure_regime(rascunho, regime_id)

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
