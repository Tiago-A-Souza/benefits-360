"""Aplica linhas confirmadas da candidata ao RascunhoEstudo."""

from __future__ import annotations

from datetime import date

from newport_app.models.draft import (
    DocumentoSiscorRascunho,
    EmpresaCliente,
    PriceBasisRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.models.siscor_import import ImportacaoSiscorCandidata, LinhaSiscorCandidata
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO


def rascunho_vazio(
    estudo_id: str,
    titulo: str,
    *,
    nome_empresa: str | None = None,
) -> RascunhoEstudo:
    return RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id=estudo_id,
        titulo=titulo,
        formato="renovacao",
        vidas=[],
        empresa_cliente=EmpresaCliente(nome=nome_empresa) if nome_empresa else None,
    )


def _linha_aplicavel(linha: LinhaSiscorCandidata) -> bool:
    if linha.excluida or not linha.registro_confirmado or linha.tem_excecao:
        return False
    if not linha.segurado or not linha.plano or not linha.operadora:
        return False
    if not linha.nascimento:
        return False
    try:
        date.fromisoformat(linha.nascimento)
    except ValueError:
        return False
    return True


def _registrar_documento_siscor(
    rascunho: RascunhoEstudo,
    candidata: ImportacaoSiscorCandidata,
) -> None:
    operadora = "SISCOR"
    if candidata.subgrupos_sugeridos:
        operadora = candidata.subgrupos_sugeridos[0].operadora
    existente = next(
        (d for d in rascunho.documentos_siscor if d.id == candidata.documento_id),
        None,
    )
    if existente is None:
        rascunho.documentos_siscor.append(
            DocumentoSiscorRascunho(
                id=candidata.documento_id,
                hash_sha256=candidata.documento_hash_sha256,
                importador_versao=candidata.importador_versao,
                operadora=operadora,
                versao_importacao=candidata.versao,
            )
        )


def aplicar_candidata_ao_rascunho(
    rascunho: RascunhoEstudo,
    candidata: ImportacaoSiscorCandidata,
) -> RascunhoEstudo:
    if candidata.empresa_sugerida:
        rascunho.empresa_cliente = EmpresaCliente(nome=candidata.empresa_sugerida)

    _registrar_documento_siscor(rascunho, candidata)

    subgrupos_por_id = {sg.id: sg for sg in candidata.subgrupos_sugeridos}
    subgrupos_rascunho: dict[str, SubgrupoAtualRascunho] = {}

    vidas: list[VidaRascunho] = []
    for linha in candidata.linhas:
        if not _linha_aplicavel(linha):
            continue
        sg_id = linha.subgrupo_sugerido_id
        if sg_id and sg_id not in subgrupos_rascunho and sg_id in subgrupos_por_id:
            sugerido = subgrupos_por_id[sg_id]
            existente = next(
                (s for s in rascunho.subgrupos_atuais if s.id == sg_id),
                None,
            )
            subgrupos_rascunho[sg_id] = SubgrupoAtualRascunho(
                id=sg_id,
                operadora=sugerido.operadora,
                plano_nome=sugerido.plano_nome,
                regime_copart_id=existente.regime_copart_id if existente else None,
                tipo_fiscal=existente.tipo_fiscal if existente else None,
                fatura_price_basis=(
                    existente.fatura_price_basis if existente else PriceBasisRascunho.DESCONHECIDO
                ),
            )
        valor = None
        if linha.valor_fatura and linha.valor_confirmado:
            valor = linha.valor_fatura.model_copy(deep=True)
            valor.proveniencia = valor.proveniencia.model_copy(update={"confirmado": True})
        vidas.append(
            VidaRascunho(
                id=linha.id,
                nome=linha.segurado or "",
                nascimento=date.fromisoformat(linha.nascimento),  # type: ignore[arg-type]
                parentesco=linha.parentesco,
                incluida=linha.incluida_sugerida,
                motivo_exclusao=linha.motivo_exclusao,
                subgrupo_atual_id=sg_id,
                valor_fatura=valor,
            )
        )

    rascunho.vidas = vidas
    rascunho.subgrupos_atuais = list(subgrupos_rascunho.values())
    candidata.estatisticas.vidas_no_rascunho = len(vidas)
    return rascunho


def estudo_possui_dados(estudo: RascunhoEstudo) -> bool:
    return bool(estudo.vidas) or bool(estudo.subgrupos_atuais)
