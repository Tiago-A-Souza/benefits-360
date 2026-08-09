"""Mapeamento RascunhoEstudo → EstudoInput + EffectivePolicy."""

from __future__ import annotations

from newport_app.draft_compiler.finance_validation import (
    resolver_basis_fatura_vida,
    validar_componente_financeiro,
    validar_faixa_tabela,
    validar_price_basis_usavel,
    validar_proveniencia_confirmada,
)
from newport_app.models.compilation import ErroCompilacao
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
    TabelaFaixaRascunho,
)
from newport_app.policy.registry import PolicySet
from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    CustoUnico,
    DocumentoCotacao,
    EstudoInput,
    OpcaoPlano,
    RegimeCopart,
    SubgrupoAtual,
    TabelaPrecoFaixa,
    Vida,
)
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    AlvoTipo,
    BaselineEscolhido,
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PrecedenciaAtualVida,
    PriceBasis,
    RegimeCopartTipo,
    TipoFiscal,
)

_ESTADO_EXTRACAO: dict[str, EstadoExtracao] = {
    "manual": EstadoExtracao.MANUAL,
    "pendente": EstadoExtracao.FALHA_EXTRACAO,
    "extraido": EstadoExtracao.EXTRAIDO_OK,
}


def _erro(codigo: str, caminho: str, mensagem: str) -> ErroCompilacao:
    return ErroCompilacao(
        codigo=codigo,
        caminho=caminho,
        mensagem=mensagem,
        severidade="bloqueante",
    )


def mapear_price_basis(
    basis: PriceBasisRascunho,
    tipo_fiscal: str,
    caminho: str,
) -> PriceBasis | ErroCompilacao:
    if basis == PriceBasisRascunho.NAO_APLICA:
        if tipo_fiscal != "operadora":
            return _erro(
                "APP-BAS-001",
                caminho,
                "A opção 'não se aplica' só é permitida para operadoras sem IOF.",
            )
        return PriceBasis.EXCLUI_IOF
    if basis == PriceBasisRascunho.INCLUI_IOF:
        return PriceBasis.INCLUI_IOF
    if basis == PriceBasisRascunho.EXCLUI_IOF:
        return PriceBasis.EXCLUI_IOF
    return PriceBasis.DESCONHECIDO


def _proveniencia_motor(prov: ProvenienciaRascunho) -> ProvenienciaCampo:
    return ProvenienciaCampo(
        origem=OrigemValor(prov.origem.value),
        documento_id=prov.documento_id,
        extrator_versao=prov.extrator_versao,
        confirmado=prov.confirmado,
    )


def _componente_motor(
    comp: ComponenteFinanceiroRascunho,
    tipo_fiscal: str,
    caminho: str,
    erros: list[ErroCompilacao],
) -> ComponenteFinanceiro | None:
    if not validar_componente_financeiro(comp, tipo_fiscal, caminho, erros):
        return None
    basis = mapear_price_basis(comp.price_basis, tipo_fiscal, f"{caminho}/price_basis")
    if isinstance(basis, ErroCompilacao):
        erros.append(basis)
        return None
    return ComponenteFinanceiro(
        centavos=comp.centavos,
        price_basis=basis,
        proveniencia=_proveniencia_motor(comp.proveniencia),
    )


def _quantidade_motor(faixa: TabelaFaixaRascunho) -> int:
    return faixa.quantidade_cotada if faixa.quantidade_cotada is not None else 0


def _tabela_faixa_motor(
    faixa: TabelaFaixaRascunho,
    tipo_fiscal: str,
    caminho: str,
    erros: list[ErroCompilacao],
    *,
    exigir_quantidade: bool,
) -> TabelaPrecoFaixa | None:
    if not validar_faixa_tabela(
        faixa,
        tipo_fiscal,
        caminho,
        erros,
        exigir_quantidade=exigir_quantidade,
    ):
        return None
    basis = mapear_price_basis(faixa.price_basis, tipo_fiscal, f"{caminho}/price_basis")
    if isinstance(basis, ErroCompilacao):
        erros.append(basis)
        return None
    return TabelaPrecoFaixa(
        faixa=faixa.faixa,
        valor_centavos=faixa.valor_centavos,
        quantidade_cotada=_quantidade_motor(faixa),
        price_basis=basis,
        proveniencia=_proveniencia_motor(faixa.proveniencia),
    )


def _validar_documentos_vinculados(
    rascunho: RascunhoEstudo,
    erros: list[ErroCompilacao],
) -> None:
    documentos = {d.id: d for d in rascunho.documentos_cotacao}
    for idx, op in enumerate(rascunho.opcoes_proposta):
        if op.documento_cotacao_id is None:
            continue
        doc = documentos.get(op.documento_cotacao_id)
        if doc is None:
            continue
        if doc.estado_extracao == "pendente":
            erros.append(
                _erro(
                    "APP-DOC-001",
                    f"/opcoes_proposta/{idx}/documento_cotacao_id",
                    "A proposta está vinculada a um documento ainda pendente de extração. "
                    "Conclua ou confirme o documento antes de calcular.",
                )
            )


def _mapear_documentos(rascunho: RascunhoEstudo) -> list[DocumentoCotacao]:
    docs = [
        DocumentoCotacao(
            id=doc.id,
            operadora=doc.operadora,
            estado_extracao=_ESTADO_EXTRACAO[doc.estado_extracao],
            parser_versao=doc.parser_versao,
        )
        for doc in rascunho.documentos_cotacao
    ]
    for siscor in rascunho.documentos_siscor:
        docs.append(
            DocumentoCotacao(
                id=siscor.id,
                operadora=siscor.operadora,
                estado_extracao=EstadoExtracao.EXTRAIDO_OK,
                parser_versao=siscor.importador_versao,
            )
        )
    return docs


def mapear_estudo_input(
    rascunho: RascunhoEstudo,
) -> tuple[EstudoInput | None, list[ErroCompilacao]]:
    erros: list[ErroCompilacao] = []
    _validar_documentos_vinculados(rascunho, erros)

    renovacao = rascunho.formato == "renovacao"

    vidas: list[Vida] = []
    for idx, v in enumerate(rascunho.vidas):
        fatura_basis: PriceBasis | None = None
        if v.valor_fatura is not None and renovacao:
            sg_tipo = "seguradora"
            sg = None
            if v.subgrupo_atual_id:
                sg = next(
                    (s for s in rascunho.subgrupos_atuais if s.id == v.subgrupo_atual_id),
                    None,
                )
                if sg is not None:
                    if sg.tipo_fiscal is None:
                        erros.append(
                            _erro(
                                "APP-IMP-001",
                                f"/subgrupos_atuais/{sg.id}/tipo_fiscal",
                                "Informe o tipo fiscal do plano atual antes de calcular.",
                            )
                        )
                        continue
                    sg_tipo = sg.tipo_fiscal
            caminho = f"/vidas/{idx}/valor_fatura"
            basis_efetivo = resolver_basis_fatura_vida(
                v.valor_fatura.price_basis,
                sg.fatura_price_basis if sg is not None else None,
            )
            if not validar_componente_financeiro(
                v.valor_fatura,
                sg_tipo,
                caminho,
                erros,
                price_basis_efetivo=basis_efetivo,
            ):
                continue
            mapped = mapear_price_basis(
                basis_efetivo,
                sg_tipo,
                f"{caminho}/price_basis",
            )
            if isinstance(mapped, ErroCompilacao):
                erros.append(mapped)
                continue
            fatura_basis = mapped
        vidas.append(
            Vida(
                id=v.id,
                nome=v.nome,
                nascimento=v.nascimento,
                incluida=v.incluida,
                subgrupo_atual_id=v.subgrupo_atual_id if renovacao else None,
                valor_fatura_centavos=(
                    v.valor_fatura.centavos
                    if v.valor_fatura and renovacao
                    else None
                ),
                fatura_price_basis=fatura_basis,
                fatura_proveniencia=(
                    _proveniencia_motor(v.valor_fatura.proveniencia)
                    if v.valor_fatura and renovacao
                    else None
                ),
            )
        )

    subgrupos: list[SubgrupoAtual] = []
    for idx, sg in enumerate(rascunho.subgrupos_atuais if renovacao else []):
        if sg.tipo_fiscal is None:
            erros.append(
                _erro(
                    "APP-IMP-001",
                    f"/subgrupos_atuais/{idx}/tipo_fiscal",
                    "Informe o tipo fiscal do plano atual antes de calcular.",
                )
            )
            continue
        if sg.regime_copart_id is None:
            erros.append(
                _erro(
                    "APP-IMP-002",
                    f"/subgrupos_atuais/{idx}/regime_copart_id",
                    "Informe o regime de coparticipação do plano atual antes de calcular.",
                )
            )
            continue
        sg_tipo = sg.tipo_fiscal
        basis = PriceBasis.DESCONHECIDO
        if sg.fatura_price_basis != PriceBasisRascunho.DESCONHECIDO:
            if not validar_price_basis_usavel(
                sg.fatura_price_basis,
                sg_tipo,
                f"/subgrupos_atuais/{idx}/fatura_price_basis",
                erros,
            ):
                continue
            mapped = mapear_price_basis(
                sg.fatura_price_basis,
                sg_tipo,
                f"/subgrupos_atuais/{idx}/fatura_price_basis",
            )
            if isinstance(mapped, ErroCompilacao):
                erros.append(mapped)
                continue
            basis = mapped
        tabela: list[TabelaPrecoFaixa] = []
        for f_idx, faixa in enumerate(sg.tabela_atual):
            item = _tabela_faixa_motor(
                faixa,
                sg_tipo,
                f"/subgrupos_atuais/{idx}/tabela_atual/{f_idx}",
                erros,
                exigir_quantidade=False,
            )
            if item is not None:
                tabela.append(item)
        subtotal = None
        if sg.subtotal_atual_impresso is not None:
            subtotal = _componente_motor(
                sg.subtotal_atual_impresso,
                sg_tipo,
                f"/subgrupos_atuais/{idx}/subtotal_atual_impresso",
                erros,
            )
        subgrupos.append(
            SubgrupoAtual(
                id=sg.id,
                operadora=sg.operadora,
                tipo_fiscal=TipoFiscal(sg_tipo),
                plano_nome=sg.plano_nome,
                regime_copart_id=sg.regime_copart_id,
                reajuste_bps=sg.reajuste_bps,
                fatura_price_basis=basis,
                subtotal_impresso=subtotal,
                tabela_atual=tabela,
            )
        )

    opcoes: list[OpcaoPlano] = []
    for idx, op in enumerate(rascunho.opcoes_proposta):
        if op.tipo_fiscal is None:
            erros.append(
                _erro(
                    "APP-IMP-001",
                    f"/opcoes_proposta/{idx}/tipo_fiscal",
                    "Informe se a proposta é contrato da seguradora ou da operadora.",
                )
            )
            continue
        if op.regime_copart_id is None:
            erros.append(
                _erro(
                    "APP-IMP-002",
                    f"/opcoes_proposta/{idx}/regime_copart_id",
                    "Selecione o regime de coparticipação da proposta.",
                )
            )
            continue
        tabela: list[TabelaPrecoFaixa] = []
        for f_idx, faixa in enumerate(op.tabela):
            item = _tabela_faixa_motor(
                faixa,
                op.tipo_fiscal,
                f"/opcoes_proposta/{idx}/tabela/{f_idx}",
                erros,
                exigir_quantidade=True,
            )
            if item is not None:
                tabela.append(item)
        custos: list[CustoUnico] = []
        for cu_idx, cu in enumerate(op.custos_unicos):
            caminho = f"/opcoes_proposta/{idx}/custos_unicos/{cu_idx}/valor"
            if not validar_componente_financeiro(cu.valor, op.tipo_fiscal, caminho, erros):
                continue
            custos.append(
                CustoUnico(
                    id=cu.id,
                    descricao=cu.descricao,
                    valor_centavos=cu.valor.centavos,  # type: ignore[arg-type]
                    proveniencia=_proveniencia_motor(cu.valor.proveniencia),
                )
            )
        opcoes.append(
            OpcaoPlano(
                id=op.id,
                operadora=op.operadora,
                plano_nome=op.plano_nome,
                regime_copart_id=op.regime_copart_id,
                tipo_fiscal=TipoFiscal(op.tipo_fiscal),
                tabela=tabela,
                premio_saude=(
                    _componente_motor(
                        op.premio_saude,
                        op.tipo_fiscal,
                        f"/opcoes_proposta/{idx}/premio_saude",
                        erros,
                    )
                    if op.premio_saude
                    else None
                ),
                iof=(
                    _componente_motor(
                        op.iof,
                        op.tipo_fiscal,
                        f"/opcoes_proposta/{idx}/iof",
                        erros,
                    )
                    if op.iof
                    else None
                ),
                total_recorrente=(
                    _componente_motor(
                        op.total_recorrente,
                        op.tipo_fiscal,
                        f"/opcoes_proposta/{idx}/total_recorrente",
                        erros,
                    )
                    if op.total_recorrente
                    else None
                ),
                total_primeira_parcela=(
                    _componente_motor(
                        op.total_primeira_parcela,
                        op.tipo_fiscal,
                        f"/opcoes_proposta/{idx}/total_primeira_parcela",
                        erros,
                    )
                    if op.total_primeira_parcela
                    else None
                ),
                subtotal_impresso=(
                    _componente_motor(
                        op.subtotal_impresso,
                        op.tipo_fiscal,
                        f"/opcoes_proposta/{idx}/subtotal_impresso",
                        erros,
                    )
                    if op.subtotal_impresso
                    else None
                ),
                custos_unicos=custos,
                documento_id=op.documento_cotacao_id,
            )
        )

    regimes = [
        RegimeCopart(
            id=r.id,
            tipo=RegimeCopartTipo(r.tipo),
            percentual_bps=(r.percentual * 100 if r.percentual is not None else None),
        )
        for r in rascunho.regimes_copart
    ]
    cenarios = [
        Cenario(
            id=c.id,
            rotulo=c.rotulo,
            atribuicoes=[
                AtribuicaoPlano(
                    id=a.id,
                    alvo_tipo=AlvoTipo(a.alvo_tipo),
                    alvo_id=a.alvo_id,
                    opcao_plano_id=a.opcao_plano_id,
                )
                for a in c.atribuicoes
            ],
        )
        for c in rascunho.cenarios
    ]
    documentos = _mapear_documentos(rascunho)

    if erros:
        return None, erros

    return (
        EstudoInput(
            id=rascunho.id,
            formato=FormatoEstudo(rascunho.formato),
            vidas=vidas,
            subgrupos_atuais=subgrupos,
            opcoes_plano=opcoes,
            regimes_copart=regimes,
            cenarios=cenarios,
            documentos=documentos,
        ),
        [],
    )


def mapear_effective_policy(
    rascunho: RascunhoEstudo,
    policy_set: PolicySet,
    erros: list[ErroCompilacao],
) -> EffectivePolicy | None:
    esc = rascunho.escolhas

    if esc.data_referencia_idade is None:
        erros.append(
            _erro(
                "APP-ESC-001",
                "/escolhas/data_referencia_idade",
                "Informe a data de referência para calcular as idades do estudo.",
            )
        )

    renovacao = rascunho.formato == "renovacao"
    baseline = esc.baseline_escolhido
    precedencia = esc.precedencia_atual_vida

    if renovacao:
        if not baseline.confirmado or baseline.valor is None:
            erros.append(
                _erro(
                    "APP-ESC-002",
                    "/escolhas/baseline_escolhido/confirmado",
                    "Confirme qual valor considerar como situação atual: "
                    "contrato vigente ou reajustado.",
                )
            )

        if not precedencia.confirmado or precedencia.valor is None:
            erros.append(
                _erro(
                    "APP-ESC-003",
                    "/escolhas/precedencia_atual_vida/confirmado",
                    "Confirme qual fonte prevalece em caso de diferença: "
                    "tabela do plano atual ou valor da fatura.",
                )
            )

    if erros:
        return None

    baseline_map = {
        "vigente": BaselineEscolhido.VIGENTE,
        "reajustado": BaselineEscolhido.REAJUSTADO,
    }
    precedencia_map = {
        "tabela_atual": PrecedenciaAtualVida.TABELA_ATUAL,
        "valor_fatura": PrecedenciaAtualVida.VALOR_FATURA,
    }

    return EffectivePolicy(
        policy_set_versao=policy_set.versao,
        data_referencia_idade=esc.data_referencia_idade,
        baseline_escolhido=(
            baseline_map[baseline.valor] if renovacao and baseline.valor else None  # type: ignore[index]
        ),
        precedencia_atual_vida=(
            precedencia_map[precedencia.valor]
            if renovacao and precedencia.valor
            else None  # type: ignore[index]
        ),
        iof_bps=policy_set.iof_bps,
        tolerancias=policy_set.tolerancias,
        estrategia_arredondamento=policy_set.estrategia_arredondamento,
        max_vidas_homologadas=policy_set.max_vidas_homologadas,
        politicas_resolvidas=policy_set.politicas_resolvidas,
    )
