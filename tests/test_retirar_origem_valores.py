"""Retirada da caixa «Origem dos valores atuais» — campo permanece explícito."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

from newport_app.adapters.motor_out import montar_comparativo
from newport_app.config.paths import caminho_banco_estudos
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    CampoConfirmavelPrecedencia,
    ComponenteFinanceiroRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RascunhoEstudo,
)
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import default_registry
from newport_app.rascunho.precedencia import (
    aplicar_precedencia_explicita,
    descricao_origem_valores,
    precedencia_ambigua,
    resolver_precedencia_unica,
)
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.calculo import CalculoService
from newport_app.services.snapshot import SnapshotService
from newport_motor.engine import calcular
from newport_motor.policy import EffectivePolicy
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.EXTRAIDO, extrator_versao="siscor@test", confirmado=True
    )


def _totais_proposta(rascunho: RascunhoEstudo) -> dict[str, int | None]:
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel, compilado.erros
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    assert not motor.tem_bloqueio
    matriz = montar_comparativo(rascunho, motor_result=motor)
    return {
        p.opcao_id: (p.numerico.proposta_mensal_centavos if p.numerico else None)
        for p in matriz.propostas
        if p.calculo_realizado
    }


def test_01_renovacao_com_fatura_grava_precedencia_explicita(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "prec-fatura.db")
    calc = CalculoService(repo)
    r = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    r.escolhas.precedencia_atual_vida = CampoConfirmavelPrecedencia(
        valor=None, confirmado=False
    )
    assert not precedencia_ambigua(r)
    assert resolver_precedencia_unica(r) == "valor_fatura"
    calc.salvar_rascunho(r)
    carregado = repo.obter_rascunho(r.id)
    assert carregado is not None
    prec = carregado.escolhas.precedencia_atual_vida
    assert prec.valor == "valor_fatura"
    assert prec.confirmado is True
    assert "fatura" in descricao_origem_valores(carregado).lower()
    assert "SISCOR" in descricao_origem_valores(carregado) or "fatura" in descricao_origem_valores(
        carregado
    ).lower()
    compilado = compile(carregado, policy_registry=default_registry)
    assert compilado.compilavel
    assert compilado.compilado.effective_policy.precedencia_atual_vida is not None
    assert compilado.compilado.effective_policy.precedencia_atual_vida.value == "valor_fatura"


def test_02_numeros_inalterados_amostra_banco():
    """Recalcula estudos do banco; totais de proposta não podem mudar."""
    con = sqlite3.connect(caminho_banco_estudos())
    ids = [
        r[0]
        for r in con.execute(
            "SELECT id FROM rascunhos WHERE json_extract(payload, '$.formato') = 'renovacao'"
        ).fetchall()
    ]
    # Amostra: demos + anistia 16 + atef4 se existir
    preferidos = {"demo-12", "demo-41", "est-0755b92d7a", "est-38ef3ce8af", "est-2d0a7f4c40"}
    amostra = [i for i in ids if i in preferidos] or ids[:5]
    for rid in amostra:
        row = con.execute("SELECT payload FROM rascunhos WHERE id=?", (rid,)).fetchone()
        if not row:
            continue
        original = RascunhoEstudo.model_validate(json.loads(row[0]))
        if not original.escolhas.data_referencia_idade:
            continue
        if not original.escolhas.baseline_escolhido.confirmado:
            continue
        antes = _totais_proposta(original)
        clone = original.model_copy(deep=True)
        aplicar_precedencia_explicita(clone)
        depois = _totais_proposta(clone)
        assert depois == antes, rid


def test_03_gabarito_anistia_dois_planos(tmp_path: Path):
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    aplicar_precedencia_explicita(rascunho)
    assert rascunho.escolhas.precedencia_atual_vida.valor == "valor_fatura"
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    matriz = montar_comparativo(rascunho, motor_result=motor)
    db = tmp_path / "gab.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    snap = snap_svc.obter_snapshot(g.snapshot_id)
    from newport_app.presentation.builder import construir_view_model

    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert_gabarito_propostas(matriz, vm, gab)
    prata = next(p for p in gab["propostas"] if p["chave"] == "prata")
    ouro = next(p for p in gab["propostas"] if p["chave"] == "ouro")
    assert prata["plano_a_centavos"] == 2_360_717
    assert prata["plano_b_centavos"] == 610_061
    assert ouro["plano_a_centavos"] == 2_751_249
    assert ouro["plano_b_centavos"] == 710_988


def test_04_ivtec_e_atef_policy_inalterada_em_numeros():
    ivtec = _rascunho_ivtec_novo()
    assert ivtec.formato == "novo"
    c = compile(ivtec, policy_registry=default_registry)
    assert c.compilavel
    assert c.compilado.effective_policy.baseline_escolhido is None
    assert c.compilado.effective_policy.precedencia_atual_vida is None

    con = sqlite3.connect(caminho_banco_estudos())
    row = con.execute(
        "SELECT payload FROM rascunhos WHERE id=?", ("est-38ef3ce8af",)
    ).fetchone()
    if row is None:
        return
    atef = RascunhoEstudo.model_validate(json.loads(row[0]))
    prec_antes = atef.escolhas.precedencia_atual_vida.model_dump()
    totais_antes = _totais_proposta(atef)
    clone = atef.model_copy(deep=True)
    aplicar_precedencia_explicita(clone)
    # Não sobrescreve escolha já confirmada
    assert clone.escolhas.precedencia_atual_vida.model_dump() == prec_antes
    assert _totais_proposta(clone) == totais_antes


def test_05_duas_fontes_exige_escolha_sem_sorteio():
    r = rascunho_demo_12_vidas()
    for v in r.vidas:
        v.valor_fatura = ComponenteFinanceiroRascunho(
            centavos=40_000,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            proveniencia=_prov(),
        )
    r.escolhas.precedencia_atual_vida = CampoConfirmavelPrecedencia(
        valor=None, confirmado=False
    )
    assert precedencia_ambigua(r)
    assert resolver_precedencia_unica(r) is None
    assert aplicar_precedencia_explicita(r) is None
    assert r.escolhas.precedencia_atual_vida.valor is None
    assert not r.escolhas.precedencia_atual_vida.confirmado
    resultado = compile(r, policy_registry=default_registry)
    assert any(e.codigo == "APP-ESC-003" for e in resultado.erros)
    assert "coexistem" in descricao_origem_valores(r).lower()


def test_06_snapshot_com_tabela_atual_continua_legivel():
    con = sqlite3.connect(caminho_banco_estudos())
    row = con.execute(
        """
        SELECT s.id, s.payload
        FROM snapshots s
        JOIN aprovacoes a ON a.snapshot_id = s.id
        WHERE s.estado = 'aprovado' AND a.invalidada_em IS NULL
          AND json_extract(s.payload, '$.effective_policy.precedencia_atual_vida') = 'tabela_atual'
        LIMIT 1
        """
    ).fetchone()
    assert row is not None, "precisa existir snapshot vivo com precedencia=tabela_atual"
    snap_id, payload_s = row
    payload = json.loads(payload_s)
    assert payload["effective_policy"]["precedencia_atual_vida"] == "tabela_atual"
    pol = EffectivePolicy.model_validate(payload["effective_policy"])
    assert pol.precedencia_atual_vida is not None
    assert pol.precedencia_atual_vida.value == "tabela_atual"
    assert "precedencia_atual_vida" in EffectivePolicy.model_fields
    from newport_app.models.draft import EscolhasEstudo

    assert "precedencia_atual_vida" in EscolhasEstudo.model_fields


def test_07_seguro_novo_sem_caixas_policy_none():
    r = _rascunho_ivtec_novo()
    assert aplicar_precedencia_explicita(r) is None
    assert r.escolhas.precedencia_atual_vida.valor is None
    c = compile(r, policy_registry=default_registry)
    assert c.compilavel
    assert c.compilado.effective_policy.baseline_escolhido is None
    assert c.compilado.effective_policy.precedencia_atual_vida is None


def test_08_baseline_continua_exigido_e_gravavel(tmp_path: Path):
    repo = SQLiteStudyRepository(tmp_path / "base.db")
    calc = CalculoService(repo)
    r = rascunho_demo_12_vidas()
    r.escolhas.baseline_escolhido.valor = "vigente"
    r.escolhas.baseline_escolhido.confirmado = True
    calc.salvar_rascunho(r)
    carregado = repo.obter_rascunho(r.id)
    assert carregado.escolhas.baseline_escolhido.valor == "vigente"
    c = compile(carregado, policy_registry=default_registry)
    assert c.compilavel
    assert c.compilado.effective_policy.baseline_escolhido.value == "vigente"

    r2 = rascunho_demo_12_vidas()
    r2.id = "base-reaj"
    r2.escolhas.baseline_escolhido.valor = "reajustado"
    r2.escolhas.baseline_escolhido.confirmado = True
    calc.salvar_rascunho(r2)
    c2 = compile(repo.obter_rascunho(r2.id), policy_registry=default_registry)
    assert c2.compilado.effective_policy.baseline_escolhido.value == "reajustado"
