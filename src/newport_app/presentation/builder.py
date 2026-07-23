"""Constrói PresentationViewModel a partir de snapshot aprovado."""

from __future__ import annotations

from datetime import datetime, timezone

from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import (
    BeneficiarioApresentacao,
    FaixaApresentacao,
    PlanoAtualApresentacao,
    PresentationViewModel,
    PropostaApresentacao,
    SecaoRegimeApresentacao,
)
from newport_app.models.responses import ComparativoResponse
from newport_app.models.snapshot import SnapshotCalculo


def _formatar_reais(centavos: int | None) -> str | None:
    if centavos is None:
        return None
    sinal = "-" if centavos < 0 else ""
    valor = abs(centavos)
    reais, cents = divmod(valor, 100)
    inteiro = f"{reais:,}".replace(",", ".")
    return f"{sinal}R$ {inteiro},{cents:02d}"


def _parse_reais(texto: str | None) -> int | None:
    if not texto:
        return None
    bruto = texto.replace("R$", "").replace(".", "").replace(",", ".").strip()
    try:
        return int(round(float(bruto) * 100))
    except ValueError:
        return None


def construir_view_model(
    snap: SnapshotCalculo,
    *,
    modo: str,
    propostas_selecionadas: list[str],
    ressalvas: list[str] | None = None,
    titulo: str | None = None,
    renderer_versao: str = "html@2.8.0",
) -> PresentationViewModel:
    rascunho = RascunhoEstudo.model_validate(snap.payload["rascunho"])
    comparativo = ComparativoResponse.model_validate(snap.payload["comparativo"])
    opcoes = {o.id: o for o in rascunho.opcoes_proposta if o.id in propostas_selecionadas}
    secoes_vm: list[SecaoRegimeApresentacao] = []

    for secao in comparativo.secoes:
        propostas_secao: list[PropostaApresentacao] = []
        for op_id in propostas_selecionadas:
            op = opcoes.get(op_id)
            if op is None:
                continue
            regime = next(
                (r for r in rascunho.regimes_copart if r.id == op.regime_copart_id),
                None,
            )
            propostas_secao.append(
                PropostaApresentacao(
                    opcao_id=op.id,
                    operadora=op.operadora,
                    plano_nome=op.plano_nome,
                    regime_rotulo=secao.rotulo,
                    acomodacao=op.acomodacao,
                    modalidade=op.modalidade.value if op.modalidade else None,
                    validade=op.validade_oficial.isoformat() if op.validade_oficial else comparativo.validade_proposta,
                    total_mensal_reais=secao.proposta_mensal_reais,
                    diff_mensal_reais=secao.diferenca_mensal_reais,
                    diff_anual_reais=secao.diferenca_anual_reais,
                )
            )
        planos_atuais = [
            PlanoAtualApresentacao(
                subgrupo_id=sg.id,
                operadora=sg.operadora,
                plano_nome=sg.plano_nome,
                subtotal_reais=_formatar_reais(
                    sg.subtotal_atual_impresso.centavos if sg.subtotal_atual_impresso else None
                ),
            )
            for sg in rascunho.subgrupos_atuais
        ]
        secoes_vm.append(
            SecaoRegimeApresentacao(
                regime_rotulo=secao.rotulo,
                regime_tipo=secao.regime_tipo,
                propostas=propostas_secao,
                planos_atuais=planos_atuais,
                totais_atual_reais=secao.atual_mensal_reais,
                totais_proposta_reais=secao.proposta_mensal_reais,
                diff_mensal_reais=secao.diferenca_mensal_reais,
                diff_anual_reais=secao.diferenca_anual_reais,
            )
        )

    beneficiarios: list[BeneficiarioApresentacao] = []
    if modo == "beneficiario":
        for secao in comparativo.secoes:
            for vida in secao.vidas:
                propostas_map: dict[str, str] = {}
                diff_map: dict[str, str | None] = {}
                for op_id in propostas_selecionadas:
                    propostas_map[op_id] = vida.proposta_reais or "—"
                    diff_map[op_id] = vida.diff_mes_reais
                beneficiarios.append(
                    BeneficiarioApresentacao(
                        vida_id=vida.vida_id,
                        nome=vida.nome,
                        idade=vida.idade,
                        faixa=vida.faixa,
                        faixa_rotulo=ROTULOS_FAIXA[vida.faixa] if vida.faixa is not None and vida.faixa < 10 else None,
                        parentesco=vida.parentesco,
                        plano_atual=vida.plano_atual,
                        atual_vigente_reais=vida.atual_reais,
                        atual_reajustado_reais=vida.atual_reais,
                        propostas=propostas_map,
                        diff_reais=diff_map,
                    )
                )

    if modo == "faixas":
        for secao in comparativo.secoes:
            agregado: dict[int, FaixaApresentacao] = {
                i: FaixaApresentacao(faixa=i, rotulo=ROTULOS_FAIXA[i]) for i in range(10)
            }
            valores_por_faixa: dict[int, set[int]] = {i: set() for i in range(10)}
            for vida in secao.vidas:
                fx = vida.faixa
                if fx is None or fx < 0 or fx > 9:
                    continue
                ag = agregado[fx]
                ag.qtd_total += 1
                if vida.parentesco == "titular":
                    ag.qtd_titulares += 1
                else:
                    ag.qtd_dependentes += 1
                atual_c = _parse_reais(vida.atual_reais)
                if atual_c is not None:
                    valores_por_faixa[fx].add(atual_c)
                for op_id in propostas_selecionadas:
                    propostas_map = ag.propostas
                    propostas_map[op_id] = vida.proposta_reais or "—"
            for fx, ag in agregado.items():
                vals = valores_por_faixa[fx]
                if len(vals) == 1:
                    ag.atual_vigente_reais = _formatar_reais(next(iter(vals)))
                elif len(vals) > 1:
                    total = sum(vals)
                    ag.observacao_valor = (
                        "Valores individuais diferentes nesta faixa — total observado exibido."
                    )
                    ag.atual_vigente_reais = _formatar_reais(total)
            for sec in secoes_vm:
                if sec.regime_tipo == secao.regime_tipo:
                    for pa in sec.planos_atuais:
                        pa.faixas = [agregado[i] for i in range(10) if agregado[i].qtd_total > 0]

    totais_gerais = {}
    if comparativo.totais:
        totais_gerais = comparativo.totais.model_dump()

    return PresentationViewModel(
        titulo=titulo or comparativo.titulo,
        subtitulo=rascunho.empresa_cliente.nome if rascunho.empresa_cliente else None,
        data_apresentacao=datetime.now(timezone.utc).strftime("%d/%m/%Y"),
        estudo_id=snap.estudo_id,
        modo=modo,
        snapshot_id=snap.id,
        snapshot_hash=snap.hash_sha256,
        renderer_versao=renderer_versao,
        gerado_em=datetime.now(timezone.utc).isoformat(),
        propostas_selecionadas=propostas_selecionadas,
        ressalvas=ressalvas or [],
        totais_gerais=totais_gerais,
        secoes_regime=secoes_vm,
        beneficiarios=beneficiarios,
    )
