"""Ajuste 2 (ata 16/08): campo IOF sai da UI; basis explícito via tipo fiscal."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from newport_app.draft_compiler import compile
from newport_app.models.draft import PriceBasisRascunho
from newport_app.rascunho.fatura_basis import (
    aplicar_fatura_price_basis_explicito,
    basis_explicito_para_tipo_fiscal,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_motor.engine import calcular


def test_basis_explicito_por_tipo_fiscal():
    assert basis_explicito_para_tipo_fiscal("operadora") == PriceBasisRascunho.NAO_APLICA
    assert basis_explicito_para_tipo_fiscal("seguradora") == PriceBasisRascunho.EXCLUI_IOF
    assert basis_explicito_para_tipo_fiscal(None) is None


def test_preenche_desconhecido_sem_sobrescrever_legado():
    rascunho = rascunho_demo_12_vidas()
    sg = rascunho.subgrupos_atuais[0]
    sg.tipo_fiscal = "operadora"
    sg.fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    assert aplicar_fatura_price_basis_explicito(rascunho) == 1
    assert sg.fatura_price_basis == PriceBasisRascunho.NAO_APLICA

    sg.fatura_price_basis = PriceBasisRascunho.INCLUI_IOF
    assert aplicar_fatura_price_basis_explicito(rascunho) == 0
    assert sg.fatura_price_basis == PriceBasisRascunho.INCLUI_IOF


def test_seguradora_desconhecido_vira_exclui_iof():
    rascunho = rascunho_demo_12_vidas()
    sg = rascunho.subgrupos_atuais[0]
    sg.tipo_fiscal = "seguradora"
    sg.fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    assert aplicar_fatura_price_basis_explicito(rascunho) == 1
    assert sg.fatura_price_basis == PriceBasisRascunho.EXCLUI_IOF


def test_salvar_grava_basis_explicito(tmp_path: Path):
    db = tmp_path / "t.db"
    repo = SQLiteStudyRepository(db)
    svc = CalculoService(repo)
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].tipo_fiscal = "operadora"
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    svc.garantir_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert salvo.subgrupos_atuais[0].fatura_price_basis == PriceBasisRascunho.NAO_APLICA


def test_desconhecido_sem_tipo_nao_escolhe_sozinho():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].tipo_fiscal = None
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    assert aplicar_fatura_price_basis_explicito(rascunho) == 0
    assert rascunho.subgrupos_atuais[0].fatura_price_basis == PriceBasisRascunho.DESCONHECIDO


def test_cotacao_price_basis_desconhecido_continua_bloqueando():
    """Cotação (faixa) desconhecida bloqueia — não há auto-escolha a partir do tipo."""
    rascunho = rascunho_demo_12_vidas()
    for fx in rascunho.opcoes_proposta[0].tabela:
        fx.price_basis = PriceBasisRascunho.DESCONHECIDO
    resultado = compile(rascunho)
    assert any(e.codigo == "APP-FIN-001" for e in resultado.erros)


def test_operadora_sem_iof_seguradora_com_iof():
    base = rascunho_demo_12_vidas()

    out_seg = compile(deepcopy(base))
    assert out_seg.compilavel
    res_seg = calcular(
        out_seg.compilado.estudo_input,  # type: ignore[union-attr]
        out_seg.compilado.effective_policy,  # type: ignore[union-attr]
    )
    prop_seg = res_seg.cenarios[0].total_proposta_centavos.centavos

    r_op = deepcopy(base)
    r_op.subgrupos_atuais[0].tipo_fiscal = "operadora"
    r_op.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    r_op.opcoes_proposta[0].tipo_fiscal = "operadora"
    out_op = compile(r_op)
    assert out_op.compilavel
    res_op = calcular(
        out_op.compilado.estudo_input,  # type: ignore[union-attr]
        out_op.compilado.effective_policy,  # type: ignore[union-attr]
    )
    prop_op = res_op.cenarios[0].total_proposta_centavos.centavos

    assert prop_seg > prop_op
    razao = prop_seg / prop_op
    assert 1.023 < razao < 1.024


def test_snapshot_com_price_basis_desconhecido_continua_legivel():
    """DESCONHECIDO permanece no modelo — snapshot legado ainda desserializa."""
    import json
    import sqlite3

    from newport_app.config.paths import caminho_banco_estudos
    from newport_app.models.draft import RascunhoEstudo
    from newport_motor.types import PriceBasis

    assert PriceBasis.DESCONHECIDO.value == "desconhecido"
    assert PriceBasisRascunho.DESCONHECIDO.value == "desconhecido"

    con = sqlite3.connect(caminho_banco_estudos())
    row = con.execute(
        """
        SELECT s.id, s.payload
        FROM snapshots s
        WHERE s.payload LIKE '%"desconhecido"%'
        LIMIT 1
        """
    ).fetchone()
    assert row is not None
    payload = json.loads(row[1])
    rascunho = RascunhoEstudo.model_validate(payload["rascunho"])
    bases = [
        v.valor_fatura.price_basis
        for v in rascunho.vidas
        if v.valor_fatura is not None
    ]
    assert PriceBasisRascunho.DESCONHECIDO in bases
