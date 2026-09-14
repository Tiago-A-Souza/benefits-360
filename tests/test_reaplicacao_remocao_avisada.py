"""FASE 0 — a re-aplicação avisa antes de apagar plano em uso na etapa 4.

Desmarcar e reaplicar continua removendo: o defeito era a remoção ser silenciosa
e levar as atribuições de cenário junto. A remoção das opções já era coberta por
``test_cotacao_pdf_regressao.test_apply_remove_deselected``; o que ninguém cobria
era a poda de ``cenario.atribuicoes`` e a ausência de aviso.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.cotacao_pdf.apply import (
    aplicar_extracao_confirmada,
    impacto_remocao_reaplicacao,
)
from newport_app.cotacao_pdf.conferencia import normalizar_opcao
from newport_app.cotacao_pdf.parsers.base import faixa_extraida, novo_campo
from newport_app.cotacao_pdf.reconcile import reconciliar_opcao
from newport_app.models.cotacao_pdf import (
    DocumentoCotacaoPDF,
    ExtracaoCotacaoCandidata,
    OpcaoCotacaoCandidata,
)
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.repository.extracao_cotacao import ExtracaoCotacaoRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.extracao_cotacao import (
    ExtracaoCotacaoService,
    RemocaoExigeConfirmacaoError,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.rascunho.impacto_remocao import montar_impacto_remocao
from newport_app.siscor_mapper.apply import rascunho_vazio

_SG_A = "AMIL S750 - Apto."
_SG_B = "AMIL ONE S2500 - Apto."


def _opcao(opcao_id: str, nome: str, *, selecionada: bool) -> OpcaoCotacaoCandidata:
    op = OpcaoCotacaoCandidata(id=opcao_id)
    normalizar_opcao(op, parser_versao="t", documento_hash="h")
    for campo in (op.operadora, op.plano_nome, op.tipo_fiscal, op.regime_copart):
        assert campo
        if campo.rotulo == "Operadora":
            campo.texto = "Amil"
        if campo.rotulo == "Nome do plano":
            campo.texto = nome
        if campo.rotulo == "Tipo fiscal":
            campo.texto = "seguradora"
        if campo.rotulo == "Regime de coparticipação":
            campo.texto = "sem"
        campo.confirmado = True
        campo.estado = "confirmar"
    op.tabela = [
        faixa_extraida(
            0,
            valor_centavos=10000,
            quantidade=1,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            pagina=1,
            trecho_valor="x",
            trecho_qtd="1",
            parser_versao="t",
            documento_hash="h",
        )
    ]
    op.tabela[0].valor.confirmado = True
    op.tabela[0].quantidade.confirmado = True
    op.premio_saude = novo_campo(
        "Prêmio saúde", centavos=10000, parser_versao="t", documento_hash="h"
    )
    op.premio_saude.confirmado = True
    reconciliar_opcao(op)
    op.selecionada_para_comparativo = selecionada
    return op


def _extracao(estudo_id: str, opcoes: list[OpcaoCotacaoCandidata]) -> ExtracaoCotacaoCandidata:
    return ExtracaoCotacaoCandidata(
        id="ext-1",
        estudo_id=estudo_id,
        versao=1,
        documento=DocumentoCotacaoPDF(
            id="doc-1",
            nome_arquivo="cotacao.pdf",
            hash_sha256="h",
            parser_versao="porto@1",
            template_id="porto-v1",
        ),
        estado="extraido",
        opcoes=opcoes,
        criado_em=datetime.now(timezone.utc),
    )


def _rascunho_dois_subgrupos(estudo_id: str):
    """Dois planos vigentes com vidas nos dois — pré-requisito do B-06."""
    r = rascunho_vazio(estudo_id, "Estudo de teste")
    r.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    r.subgrupos_atuais.extend(
        [
            SubgrupoAtualRascunho(id="sg-1", operadora="Amil", plano_nome=_SG_A),
            SubgrupoAtualRascunho(id="sg-2", operadora="Amil", plano_nome=_SG_B),
        ]
    )
    r.vidas.extend(
        [
            VidaRascunho(
                id="v-1",
                nome="Vida 1",
                nascimento=date(1990, 1, 1),
                subgrupo_atual_id="sg-1",
            ),
            VidaRascunho(
                id="v-2",
                nome="Vida 2",
                nascimento=date(1985, 1, 1),
                subgrupo_atual_id="sg-2",
            ),
        ]
    )
    return r


def _cenario_montado(rascunho, id_a: str, id_b: str) -> None:
    rascunho.cenarios.append(
        CenarioRascunho(
            id="cen-1",
            nome="Cenário",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="atr-1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id=id_a
                ),
                AtribuicaoRascunho(
                    id="atr-2", alvo_tipo="subgrupo", alvo_id="sg-2", opcao_plano_id=id_b
                ),
            ],
        )
    )


def _id_do_rascunho(rascunho, extracao_opcao_id: str) -> str:
    op = next(
        o for o in rascunho.opcoes_proposta if o.extracao_opcao_id == extracao_opcao_id
    )
    return op.id


def _cenario_com_dois_planos(estudo_id: str = "est-fase0"):
    """Estado inicial real: dois planos aplicados e cenário montado com os dois."""
    ops = [
        _opcao("op-a", "Plano A", selecionada=True),
        _opcao("op-b", "Plano B", selecionada=True),
        _opcao("op-c", "Plano C", selecionada=False),
        _opcao("op-d", "Plano D", selecionada=False),
        _opcao("op-e", "Plano E", selecionada=False),
    ]
    extracao = _extracao(estudo_id, ops)
    rascunho = _rascunho_dois_subgrupos(estudo_id)
    rascunho, bloqueios = aplicar_extracao_confirmada(rascunho, extracao)
    assert not bloqueios
    assert len(rascunho.opcoes_proposta) == 2
    _cenario_montado(
        rascunho,
        _id_do_rascunho(rascunho, "op-a"),
        _id_do_rascunho(rascunho, "op-b"),
    )
    return rascunho, extracao, ops


def _trocar_selecao(ops: list[OpcaoCotacaoCandidata], selecionados: set[str]) -> None:
    for op in ops:
        op.selecionada_para_comparativo = op.id in selecionados


def _svc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    estudos_path = tmp_path / "estudos.db"
    cotacoes_path = tmp_path / "cotacoes.db"
    monkeypatch.setattr(
        "newport_app.config.paths.caminho_banco_estudos",
        lambda modo=None: estudos_path,
    )
    monkeypatch.setattr(
        "newport_app.config.paths.caminho_banco_cotacoes",
        lambda modo=None: cotacoes_path,
    )
    estudos = SQLiteStudyRepository(estudos_path)
    extracoes = ExtracaoCotacaoRepository(cotacoes_path)
    return ExtracaoCotacaoService(estudos, extracoes), estudos, extracoes


# ---------------------------------------------------------------------------
# 1. O caminho que não era coberto
# ---------------------------------------------------------------------------


def test_01_reaplicacao_avisa_planos_e_atribuicoes_perdidas():
    """Dois planos aplicados, cenário usando os dois, troca de seleção."""
    rascunho, extracao, ops = _cenario_com_dois_planos()
    _trocar_selecao(ops, {"op-c", "op-d"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)

    assert impacto.planos_removidos == ["Plano A", "Plano B"]
    assert impacto.exige_confirmacao is True
    assert len(impacto.atribuicoes_desfeitas) == 2
    perdidas = {(a.alvo_rotulo, a.plano) for a in impacto.atribuicoes_desfeitas}
    assert perdidas == {(_SG_A, "Plano A"), (_SG_B, "Plano B")}
    assert all(a.cenario_rotulo == "Plano A + Plano B" for a in impacto.atribuicoes_desfeitas)


def test_01b_servico_recusa_sem_confirmacao_e_nao_grava(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    rascunho, extracao, ops = _cenario_com_dois_planos()
    estudos.salvar_rascunho(rascunho)
    _trocar_selecao(ops, {"op-c", "op-d"})
    extracoes.salvar(extracao)

    with pytest.raises(RemocaoExigeConfirmacaoError) as exc:
        svc.aplicar_ao_rascunho("ext-1")

    assert exc.value.impacto.planos_removidos == ["Plano A", "Plano B"]

    # Nada foi gravado: o operador ainda pode desistir sem perder a etapa 4.
    depois = estudos.obter_rascunho("est-fase0")
    assert {op.plano_nome for op in depois.opcoes_proposta} == {"Plano A", "Plano B"}
    assert len(depois.cenarios[0].atribuicoes) == 2


# ---------------------------------------------------------------------------
# 2. Confirmado, a remoção acontece de fato — comportamento não foi revertido
# ---------------------------------------------------------------------------


def test_02_confirmado_remove_planos_e_atribuicoes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    rascunho, extracao, ops = _cenario_com_dois_planos()
    estudos.salvar_rascunho(rascunho)
    _trocar_selecao(ops, {"op-c", "op-d"})
    extracoes.salvar(extracao)

    res = svc.aplicar_ao_rascunho("ext-1", confirmar_remocoes=True)

    assert res.opcoes_adicionadas == 2
    assert res.impacto_remocao is not None
    assert res.impacto_remocao.planos_removidos == ["Plano A", "Plano B"]

    depois = estudos.obter_rascunho("est-fase0")
    assert {op.plano_nome for op in depois.opcoes_proposta} == {"Plano C", "Plano D"}
    atribuicoes = [a for c in depois.cenarios for a in c.atribuicoes]
    assert not [a for a in atribuicoes if a.opcao_plano_id in {"Plano A", "Plano B"}]
    assert len(atribuicoes) == 0


# ---------------------------------------------------------------------------
# 3. Planos de outro documento não são tocados
# ---------------------------------------------------------------------------


def test_03_planos_de_outro_documento_intactos():
    rascunho, extracao, ops = _cenario_com_dois_planos()
    rascunho.opcoes_proposta.append(
        OpcaoPropostaRascunho(
            id="op-outro-doc",
            operadora="SulAmérica",
            plano_nome="Plano de outro PDF",
            regime_copart_id="regime-sem",
            tipo_fiscal="seguradora",
            extracao_id="ext-outra",
            documento_cotacao_id="doc-outro",
        )
    )
    _trocar_selecao(ops, {"op-c", "op-d"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)
    assert "Plano de outro PDF" not in impacto.planos_removidos

    rascunho, _ = aplicar_extracao_confirmada(rascunho, extracao)
    assert "Plano de outro PDF" in {op.plano_nome for op in rascunho.opcoes_proposta}


# ---------------------------------------------------------------------------
# 4. Cenário incompleto é sinalizado na re-aplicação, não só depois no B-06
# ---------------------------------------------------------------------------


def test_04_cenario_incompleto_sinalizado_na_reaplicacao():
    """Sai só o plano do sg-1: o cenário sobrevive, mas sem cobrir os dois grupos."""
    rascunho, extracao, ops = _cenario_com_dois_planos()
    _trocar_selecao(ops, {"op-b", "op-c"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)

    assert impacto.planos_removidos == ["Plano A"]
    assert impacto.exige_confirmacao is True
    assert len(impacto.cenarios_incompletos) == 1
    incompleto = impacto.cenarios_incompletos[0]
    assert incompleto.cenario_rotulo == "Plano A + Plano B"
    assert incompleto.alvos_sem_atribuicao == [_SG_A]
    assert incompleto.ficou_vazio is False


def test_04b_cenario_esvaziado_e_marcado_como_vazio():
    rascunho, extracao, ops = _cenario_com_dois_planos()
    _trocar_selecao(ops, {"op-c", "op-d"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)

    assert len(impacto.cenarios_incompletos) == 1
    incompleto = impacto.cenarios_incompletos[0]
    assert incompleto.ficou_vazio is True
    assert sorted(incompleto.alvos_sem_atribuicao) == sorted([_SG_A, _SG_B])


# ---------------------------------------------------------------------------
# 5. Reaplicar sem desmarcar nada não gera aviso nenhum
# ---------------------------------------------------------------------------


def test_05_reaplicar_sem_mudar_selecao_nao_avisa(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    rascunho, extracao, _ops = _cenario_com_dois_planos()
    estudos.salvar_rascunho(rascunho)
    extracoes.salvar(extracao)

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)
    assert impacto.planos_removidos == []
    assert impacto.houve_remocao is False
    assert impacto.exige_confirmacao is False

    res = svc.aplicar_ao_rascunho("ext-1")
    assert res.impacto_remocao is None

    depois = estudos.obter_rascunho("est-fase0")
    assert len(depois.opcoes_proposta) == 2
    assert len(depois.cenarios[0].atribuicoes) == 2


def test_05b_adicionar_plano_novo_nao_avisa():
    """Marcar um plano a mais não remove nada — não pode pedir confirmação."""
    rascunho, extracao, ops = _cenario_com_dois_planos()
    _trocar_selecao(ops, {"op-a", "op-b", "op-c"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)
    assert impacto.houve_remocao is False
    assert impacto.exige_confirmacao is False


# ---------------------------------------------------------------------------
# 6. Plano fora de cenário: avisa a remoção, sem falar em cenário
# ---------------------------------------------------------------------------


def test_06_plano_fora_de_cenario_avisa_sem_falar_de_cenario(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    ops = [
        _opcao("op-a", "Plano A", selecionada=True),
        _opcao("op-b", "Plano B", selecionada=True),
        _opcao("op-c", "Plano C", selecionada=True),
        _opcao("op-d", "Plano D", selecionada=False),
        _opcao("op-e", "Plano E", selecionada=False),
    ]
    extracao = _extracao("est-fora", ops)
    rascunho = _rascunho_dois_subgrupos("est-fora")
    rascunho, _ = aplicar_extracao_confirmada(rascunho, extracao)
    # Cenário usa A e B; C entrou no comparativo e ficou fora da etapa 4.
    _cenario_montado(
        rascunho,
        _id_do_rascunho(rascunho, "op-a"),
        _id_do_rascunho(rascunho, "op-b"),
    )
    estudos.salvar_rascunho(rascunho)
    _trocar_selecao(ops, {"op-a", "op-b"})
    extracoes.salvar(extracao)

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)
    assert impacto.planos_removidos == ["Plano C"]
    assert impacto.houve_remocao is True
    assert impacto.atribuicoes_desfeitas == []
    assert impacto.cenarios_incompletos == []
    assert impacto.exige_confirmacao is False

    # Sem confirmação e sem exceção: aplica e relata.
    res = svc.aplicar_ao_rascunho("ext-1")
    assert res.impacto_remocao is not None
    assert res.impacto_remocao.planos_removidos == ["Plano C"]

    depois = estudos.obter_rascunho("est-fora")
    assert {op.plano_nome for op in depois.opcoes_proposta} == {"Plano A", "Plano B"}
    assert len(depois.cenarios[0].atribuicoes) == 2


# ---------------------------------------------------------------------------
# Contrato HTTP: 409 com o inventário, 200 quando confirmado
# ---------------------------------------------------------------------------


def test_07_endpoint_409_e_confirmacao(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(tmp_path))
    estudos = SQLiteStudyRepository(tmp_path / "estudos.db")
    extracoes = ExtracaoCotacaoRepository(tmp_path / "cotacoes.db")
    rascunho, extracao, ops = _cenario_com_dois_planos()
    estudos.salvar_rascunho(rascunho)
    _trocar_selecao(ops, {"op-c", "op-d"})
    extracoes.salvar(extracao)

    client = TestClient(
        create_app(repo=estudos, cotacao_repo=extracoes, seed_demos=False)
    )
    url = "/api/estudos/est-fase0/extracao-cotacao/ext-1/aplicar"

    resp = client.post(url)
    assert resp.status_code == 409
    detalhe = resp.json()["detail"]
    assert detalhe["codigo"] == "PDF-REAP-001"
    assert detalhe["impacto_remocao"]["planos_removidos"] == ["Plano A", "Plano B"]
    assert len(detalhe["impacto_remocao"]["atribuicoes_desfeitas"]) == 2

    # A recusa não gravou nada.
    intacto = estudos.obter_rascunho("est-fase0")
    assert len(intacto.cenarios[0].atribuicoes) == 2

    resp_ok = client.post(url, json={"confirmar_remocoes": True})
    assert resp_ok.status_code == 200
    assert resp_ok.json()["impacto_remocao"]["planos_removidos"] == ["Plano A", "Plano B"]


# ---------------------------------------------------------------------------
# 3 (bis). Nada de valor por omissão: nenhuma atribuição é recriada
# ---------------------------------------------------------------------------


def test_08_nao_recria_atribuicao_com_substituto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    svc, estudos, extracoes = _svc(tmp_path, monkeypatch)
    rascunho, extracao, ops = _cenario_com_dois_planos()
    estudos.salvar_rascunho(rascunho)
    _trocar_selecao(ops, {"op-c", "op-d"})
    extracoes.salvar(extracao)

    svc.aplicar_ao_rascunho("ext-1", confirmar_remocoes=True)

    depois = estudos.obter_rascunho("est-fase0")
    ids_novos = {op.id for op in depois.opcoes_proposta}
    atribuicoes = [a for c in depois.cenarios for a in c.atribuicoes]
    assert not [a for a in atribuicoes if a.opcao_plano_id in ids_novos]


# ---------------------------------------------------------------------------
# Seguro novo — FASE 0 com atribuições por vida
# ---------------------------------------------------------------------------


def _rascunho_seguro_novo_base(estudo_id: str, *, com_dois_planos_siscor: bool = False):
    r = rascunho_vazio(estudo_id, "Seguro novo", formato="novo")
    r.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    if com_dois_planos_siscor:
        r.subgrupos_atuais.extend(
            [
                SubgrupoAtualRascunho(id="sg-bas", operadora="Amil", plano_nome="BASICO"),
                SubgrupoAtualRascunho(id="sg-ger", operadora="Amil", plano_nome="GERENCIAL"),
            ]
        )
        r.vidas.extend(
            [
                VidaRascunho(
                    id="v-1",
                    nome="A1",
                    nascimento=date(1990, 1, 1),
                    subgrupo_atual_id="sg-bas",
                ),
                VidaRascunho(
                    id="v-2",
                    nome="A2",
                    nascimento=date(1985, 5, 5),
                    subgrupo_atual_id="sg-bas",
                ),
                VidaRascunho(
                    id="v-3",
                    nome="B1",
                    nascimento=date(1978, 3, 3),
                    subgrupo_atual_id="sg-ger",
                ),
                VidaRascunho(
                    id="v-4",
                    nome="B2",
                    nascimento=date(1992, 11, 11),
                    subgrupo_atual_id="sg-ger",
                ),
            ]
        )
    else:
        r.vidas.extend(
            [
                VidaRascunho(id="v-1", nome="Vida 1", nascimento=date(1990, 1, 1)),
                VidaRascunho(id="v-2", nome="Vida 2", nascimento=date(1985, 1, 1)),
            ]
        )
    return r


def _cenario_seguro_novo_com_dois_planos(
    estudo_id: str = "est-sn-fase0",
    *,
    com_dois_planos_siscor: bool = False,
):
    ops = [
        _opcao("op-a", "Plano A", selecionada=True),
        _opcao("op-b", "Plano B", selecionada=True),
        _opcao("op-c", "Plano C", selecionada=False),
    ]
    extracao = _extracao(estudo_id, ops)
    rascunho = _rascunho_seguro_novo_base(
        estudo_id, com_dois_planos_siscor=com_dois_planos_siscor
    )
    rascunho, bloqueios = aplicar_extracao_confirmada(rascunho, extracao)
    assert not bloqueios
    sincronizar_cenarios(rascunho)
    assert all(
        a.alvo_tipo == "vida"
        for c in rascunho.cenarios
        for a in c.atribuicoes
    )
    return rascunho, extracao, ops


def test_sn_01_remover_plano_um_plano_sem_cenario_incompleto():
    """Seguro novo, um PLANO: avisa remoção, sem falso incompleto."""
    rascunho, extracao, ops = _cenario_seguro_novo_com_dois_planos()
    _trocar_selecao(ops, {"op-c"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)

    assert impacto.planos_removidos == ["Plano A", "Plano B"]
    assert impacto.exige_confirmacao is True
    assert impacto.cenarios_incompletos == []


def test_sn_02_dois_planos_siscor_nao_acusa_incompleto_indevido():
    """Dois PLANO na base: remover uma cotação não gera incompleto falso."""
    rascunho, _, ops = _cenario_seguro_novo_com_dois_planos(
        "est-sn-2plano", com_dois_planos_siscor=True
    )
    id_a = rascunho.opcoes_proposta[0].id
    impacto = montar_impacto_remocao(rascunho, {id_a})

    assert len(impacto.atribuicoes_desfeitas) == 4
    assert impacto.cenarios_incompletos == []


def test_sn_03_cenario_parcialmente_descoberto_e_sinalizado():
    """Vidas sem atribuição num cenário que sobrevive: incompleto real."""
    rascunho, _, _ = _cenario_seguro_novo_com_dois_planos("est-sn-parcial")
    cenario = rascunho.cenarios[0]
    id_b = rascunho.opcoes_proposta[1].id
    cenario.atribuicoes = [
        AtribuicaoRascunho(
            id="atr-1", alvo_tipo="vida", alvo_id="v-1", opcao_plano_id=cenario.atribuicoes[0].opcao_plano_id
        ),
        AtribuicaoRascunho(
            id="atr-2", alvo_tipo="vida", alvo_id="v-2", opcao_plano_id=id_b
        ),
    ]

    impacto = montar_impacto_remocao(rascunho, {id_b})

    assert len(impacto.cenarios_incompletos) == 1
    incompleto = impacto.cenarios_incompletos[0]
    assert incompleto.ficou_vazio is False
    assert incompleto.alvos_sem_atribuicao == ["Vida 2"]


@pytest.mark.parametrize(
    "fabrica",
    [
        _cenario_com_dois_planos,
        lambda: _cenario_seguro_novo_com_dois_planos("est-sn-param"),
    ],
    ids=["renovacao", "seguro_novo"],
)
def test_param_reaplicacao_avisa_planos_e_atribuicoes(fabrica):
    rascunho, extracao, ops = fabrica()
    _trocar_selecao(ops, {"op-c", "op-d"} if len(ops) > 3 else {"op-c"})

    impacto = impacto_remocao_reaplicacao(rascunho, extracao)

    assert "Plano A" in impacto.planos_removidos
    assert impacto.exige_confirmacao is True
    assert impacto.atribuicoes_desfeitas
