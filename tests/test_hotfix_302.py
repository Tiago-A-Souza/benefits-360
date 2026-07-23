"""Testes HOTFIX 3.0.2 — herança IOF SISCOR e pendências por etapa."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RegimeCopartRascunho,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.siscor_mapper.apply import aplicar_candidata_ao_rascunho, rascunho_vazio
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.fixtures.siscor.xlsx_builder import planilha_41_vidas_2_planos


def _confirmar_candidata(candidata):
    for linha in candidata.linhas:
        if linha.excluida or not linha.confirmavel:
            continue
        linha.registro_confirmado = True
        linha.valor_confirmado = linha.valor_fatura is not None


def _valor_fatura_desconhecido(centavos: int = 85_000) -> ComponenteFinanceiroRascunho:
    return ComponenteFinanceiroRascunho(
        centavos=centavos,
        price_basis=PriceBasisRascunho.DESCONHECIDO,
        proveniencia=ProvenienciaRascunho(
            origem=OrigemValorRascunho.EXTRAIDO,
            confirmado=True,
        ),
    )


def _aplicar_valor_fatura_desconhecido(rascunho):
    for v in rascunho.vidas:
        v.valor_fatura = _valor_fatura_desconhecido()


def _rascunho_duas_operadoras_41_vidas():
    resultado = parse_planilha_siscor(
        planilha_41_vidas_2_planos(),
        estudo_id="est-41-iof",
        documento_id="doc-41",
        versao=1,
        criado_por="teste",
    )
    assert resultado.candidata is not None
    _confirmar_candidata(resultado.candidata)
    rascunho = aplicar_candidata_ao_rascunho(
        rascunho_vazio("est-41-iof", "41 vidas IOF"),
        resultado.candidata,
    )
    rascunho.regimes_copart = [RegimeCopartRascunho(id="regime-sem", tipo="sem")]
    for sg in rascunho.subgrupos_atuais:
        sg.tipo_fiscal = "operadora"
        sg.regime_copart_id = "regime-sem"
        sg.fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    rascunho.escolhas.data_referencia_idade = "2026-01-01"
    rascunho.escolhas.baseline_escolhido.confirmado = True
    rascunho.escolhas.precedencia_atual_vida.confirmado = True
    return rascunho


def test_herda_nao_aplica_do_subgrupo_41_vidas_sem_app_fin_001():
    rascunho = _rascunho_duas_operadoras_41_vidas()
    assert len(rascunho.vidas) == 41
    assert len(rascunho.subgrupos_atuais) == 2
    for v in rascunho.vidas:
        assert v.valor_fatura is not None
        assert v.valor_fatura.price_basis == PriceBasisRascunho.DESCONHECIDO

    resultado = compile(rascunho)
    assert not any(e.codigo == "APP-FIN-001" for e in resultado.erros)


def test_preserva_base_individual_conhecida():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    rascunho.subgrupos_atuais[0].tipo_fiscal = "operadora"
    for v in rascunho.vidas:
        if v.valor_fatura:
            v.valor_fatura.price_basis = PriceBasisRascunho.INCLUI_IOF

    resultado = compile(rascunho)
    assert resultado.compilavel
    for vida in resultado.compilado.estudo_input.vidas:  # type: ignore[union-attr]
        if vida.valor_fatura_centavos is not None:
            assert vida.fatura_price_basis.value == "inclui_iof"


def test_bloqueia_quando_grupo_e_vida_desconhecidos():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    _aplicar_valor_fatura_desconhecido(rascunho)

    resultado = compile(rascunho)
    assert any(e.codigo == "APP-FIN-001" for e in resultado.erros)


def test_seguradora_com_nao_aplica_bloqueia():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.NAO_APLICA
    _aplicar_valor_fatura_desconhecido(rascunho)

    resultado = compile(rascunho)
    assert any(e.codigo == "APP-BAS-001" for e in resultado.erros)


def test_ausencia_propostas_nao_bloqueia_etapa_2():
    rascunho = rascunho_demo_12_vidas()
    rascunho.opcoes_proposta = []
    rascunho.cenarios = []

    itens = pendencias_compilacao(rascunho)
    etapa2 = [p for p in itens if p.etapa == 2 and p.tipo == "bloqueio"]
    assert not any(p.codigo == "APP-ET3-001" for p in etapa2)
    assert any(p.codigo == "APP-ET3-001" and p.etapa == 3 for p in itens)


def test_pendencias_repetidas_agrupadas():
    rascunho = rascunho_demo_12_vidas()
    rascunho.subgrupos_atuais[0].fatura_price_basis = PriceBasisRascunho.DESCONHECIDO
    _aplicar_valor_fatura_desconhecido(rascunho)

    itens = pendencias_compilacao(rascunho)
    fin = [p for p in itens if p.codigo == "APP-FIN-001"]
    assert len(fin) == 1
    assert fin[0].quantidade >= 12
    assert str(fin[0].quantidade) in fin[0].titulo


def test_estudo_real_sem_pendencia_iof_etapa_2():
    origem = Path(".data/newport_app.db")
    if not origem.is_file():
        pytest.skip("Banco real indisponível")

    tmp = Path(tempfile.mkdtemp())
    db = tmp / "newport_app.db"
    shutil.copy2(origem, db)
    repo = SQLiteStudyRepository(db)
    rascunho = repo.obter_rascunho("est-6ec6d7945a")
    if rascunho is None:
        pytest.skip("Estudo real não encontrado na cópia")

    itens = pendencias_compilacao(rascunho)
    etapa2_iof = [p for p in itens if p.etapa == 2 and p.codigo == "APP-FIN-001"]
    assert etapa2_iof == []
    assert len(rascunho.vidas) == 41
    assert len(rascunho.subgrupos_atuais) == 2

    resultado = compile(rascunho)
    assert not any(e.codigo == "APP-FIN-001" for e in resultado.erros)
