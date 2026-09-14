"""Frente 2 — visão por grupo familiar (substitui beneficiário na matriz/documento)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.colisao_coluna import coluna_bate
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.grupos_familiares import montar_grupos_familiares
from newport_app.presentation.html_renderer import render_html, render_html_completo
from newport_app.presentation.paridade_estrutural import assert_paridade_estrutural
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_tmp
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar, _stack
from tests.test_paridade_matriz_html import (
    _aprovar as _aprovar_matriz,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)

_FIXTURE_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)

# Gabarito Anistia (prompt F2 / consolidado + planos).
_GABARITO = {
    "consolidado_atual": 4_761_362,
    "consolidado_proposta": 4_847_931,
    "prata": (2_360_717, 610_061),
    "bronze": (2_135_464, 551_850),
    "ouro_copar_30": (2_751_249, 710_988),
}


def _carimbar_vinculos_por_ordem(rascunho) -> None:
    """Atribui chave de grupo: cada dependente fica sob o titular imediatamente anterior.

    Replica o efeito do vínculo SISCOR (CPF titular) quando a fixture só traz parentesco.
    """
    chave = None
    ti = 0
    for v in rascunho.vidas:
        if v.parentesco and str(v.parentesco.value).lower() == "titular":
            chave = f"cpf:{ti:011d}"
            ti += 1
            v.vinculo_grupo_chave = chave
        else:
            v.vinculo_grupo_chave = chave


def _anistia_com_vinculos():
    rascunho = _rascunho_anistia_seis()
    _carimbar_vinculos_por_ordem(rascunho)
    return rascunho


def _ids_seis() -> list[str]:
    return [p["id"] for p in json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))["propostas"]]


def test_01_anistia_27_grupos_41_vidas(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()
    )
    assert len(vm.grupos_familiares) == 27
    assert sum(len(g.membros) for g in vm.grupos_familiares) == 41
    assert len(rascunho.vidas) == 41


def test_02_subtotal_so_quando_mais_de_uma_vida(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()
    )
    for g in vm.grupos_familiares:
        if len(g.membros) > 1:
            assert g.exibir_subtotal is True
            assert g.subtotal_propostas
        else:
            assert g.exibir_subtotal is False
            assert g.subtotal_propostas == []
            assert g.subtotal_atual_reajustado_centavos is None


def test_03_ordenacao_alfabetica_pelo_titular(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    # Nomes distintos para ordenação estável.
    for i, v in enumerate(rascunho.vidas):
        if v.parentesco and str(v.parentesco.value).lower() == "titular":
            v.nome = f"Titular {chr(65 + (i % 26))}{i:02d}"
        else:
            v.nome = f"Dependente {i:02d}"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()[:1]
    )
    rotulos = [g.rotulo for g in vm.grupos_familiares if not g.sem_vinculo_resolvido]
    assert rotulos == sorted(rotulos, key=str.casefold)


def test_04_dependente_exibe_vinculo_parentesco(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()[:1]
    )
    parentescos = {
        m.parentesco
        for g in vm.grupos_familiares
        for m in g.membros
        if m.parentesco and m.parentesco != "titular"
    }
    assert "conjuge" in parentescos or "cônjuge" in {p.lower() for p in parentescos if p}
    assert any(
        (m.parentesco or "").lower() in {"filho", "filha", "filho(a)"}
        or (m.parentesco or "") == "filho"
        for g in vm.grupos_familiares
        for m in g.membros
    )
    html = render_html(vm)
    assert "conjuge" in html.lower() or "cônjuge" in html.lower()
    assert "filho" in html.lower()


def test_05_subtotal_e_soma_direta_das_vidas(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    for g in vm.grupos_familiares:
        if not g.exibir_subtotal:
            continue
        for op_id in vm.propostas_selecionadas:
            esperado = sum(
                next(c.valor_centavos for c in m.propostas if coluna_bate(c, op_id)) or 0
                for m in g.membros
            )
            col = next(c for c in g.subtotal_propostas if coluna_bate(c, op_id))
            assert col.valor_centavos == esperado
        atual_esp = sum(m.atual_reajustado_centavos or 0 for m in g.membros)
        assert g.subtotal_atual_reajustado_centavos == atual_esp


def test_06_soma_grupos_igual_totais_faixas(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    vm_g = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    for op_id in vm_g.propostas_selecionadas:
        soma_g = 0
        for g in vm_g.grupos_familiares:
            for m in g.membros:
                col = next(c for c in m.propostas if coluna_bate(c, op_id))
                soma_g += col.valor_centavos or 0
        assert soma_g == vm_f.totais_gerais.propostas[op_id]
        assert soma_g == vm_g.totais_gerais.propostas[op_id]


def test_07_exibir_nomes_desligado_ainda_identificavel(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    for i, v in enumerate(rascunho.vidas):
        v.nome = f"Pessoa Segredo {i}"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=_ids_seis()[:1],
        beneficiarios_agregados=True,
    )
    html = render_html(vm)
    for v in rascunho.vidas:
        assert v.nome not in html
    assert vm.grupos_familiares[0].rotulo == "Grupo 1"
    assert vm.grupos_familiares[-1].rotulo == f"Grupo {len(vm.grupos_familiares)}"
    assert "Grupo 1" in html
    assert " · titular" in html or " · cônjuge" in html
    assert len(vm.grupos_familiares) == 27


def test_08_vida_sem_vinculo_aparece_grupo_proprio(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    solo = rascunho.vidas[-1]
    solo.vinculo_grupo_chave = None
    solo.nome = "Vida Orfa Sem Vinculo"
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="grupo_familiar", propostas_selecionadas=_ids_seis()[:1]
    )
    assert sum(len(g.membros) for g in vm.grupos_familiares) == 41
    orfaos = [g for g in vm.grupos_familiares if g.sem_vinculo_resolvido]
    assert len(orfaos) == 1
    assert orfaos[0].membros[0].nome == "Vida Orfa Sem Vinculo"
    assert vm.grupos_familiares[-1].sem_vinculo_resolvido
    html = render_html(vm)
    assert "sem vínculo resolvido" not in html
    assert "Sem vínculo familiar na base" not in html
    assert "Vida Orfa Sem Vinculo" in html


def test_09_beneficiario_sai_da_matriz_e_documento(tmp_path: Path):
    matriz_src = Path("web/src/comparativo/ComparativoExperiencia.jsx").read_text(
        encoding="utf-8"
    )
    assert "Por grupo familiar" in matriz_src
    assert "Por beneficiário" not in matriz_src
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    ids = _ids_seis()
    html = render_html_completo(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids),
        construir_view_model(snap, modo="faixas", propostas_selecionadas=ids),
        construir_view_model(
            snap,
            modo="grupo_familiar",
            propostas_selecionadas=ids,
            beneficiarios_agregados=True,
        ),
    )
    assert "Por grupo familiar" in html
    assert "Por beneficiário" not in html


def test_10_entregavel_legado_beneficiario_continua_legivel(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    snap = _aprovar_tmp(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="beneficiario", propostas_selecionadas=_ids_seis()[:1]
    )
    html = render_html(vm)
    assert len(vm.beneficiarios) == 41
    assert "Beneficiário" in html or vm.beneficiarios[0].nome in html
    # Documento completo ainda aceita VM legado na terceira aba.
    html_leg = render_html_completo(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=_ids_seis()[:1]),
        construir_view_model(snap, modo="faixas", propostas_selecionadas=_ids_seis()[:1]),
        vm,
    )
    assert "Por beneficiário" in html_leg


def test_11_seguro_novo_aplica_visao(tmp_path: Path):
    """Seguro novo: cada vida (titular) é um grupo; a visão se aplica sem coluna atual."""
    rascunho = _rascunho_ivtec_novo()
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert vm.formato == "novo"
    assert sum(len(g.membros) for g in vm.grupos_familiares) == len(
        [v for v in rascunho.vidas if v.incluida]
    )
    html = render_html(vm)
    assert "grupo familiar" in html.lower()


def test_12_estudo_plano_vigente_funciona(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado][:2]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert vm.formato == "renovacao"
    assert vm.grupos_familiares
    assert sum(len(g.membros) for g in vm.grupos_familiares) == len(
        [v for v in rascunho.vidas if v.incluida]
    )


def test_13_paridade_estrutural_com_grupos(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert_paridade_estrutural(matriz, vm, rascunho=rascunho)
    assert len(vm.grupos_familiares) == 27


def test_14_gabarito_anistia_intacto(tmp_path: Path):
    """Gabarito dos dois planos (Prata/Ouro + consolidado) — valores do prompt F2 intactos."""
    gab_path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "paridade_matriz"
        / "gabarito_dois_planos.json"
    )
    gab = json.loads(gab_path.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _carimbar_vinculos_por_ordem(rascunho)
    snap = _aprovar_matriz(tmp_path, rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    ids = [p.opcao_id for p in matriz.propostas if p.calculo_realizado]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(snap, modo="grupo_familiar", propostas_selecionadas=ids)
    assert vm.totais_gerais.propostas == vm_g.totais_gerais.propostas
    prata = next(s for s in gab["propostas"] if s["chave"] == "prata")
    ouro = next(s for s in gab["propostas"] if s["chave"] == "ouro")
    assert prata["plano_a_centavos"] == _GABARITO["prata"][0]
    assert prata["plano_b_centavos"] == _GABARITO["prata"][1]
    assert ouro["plano_a_centavos"] == _GABARITO["ouro_copar_30"][0]
    assert ouro["plano_b_centavos"] == _GABARITO["ouro_copar_30"][1]
    # Consolidado vigente (reajuste 10%) e reajustado 12% do fixture.
    assert gab["reajuste"]["1000"]["consolidado_centavos"] == _GABARITO["consolidado_atual"]
    assert gab["reajuste"]["1200"]["consolidado_centavos"] == _GABARITO["consolidado_proposta"]
    html_r = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    assert "48.479,31" in html_r
    assert "23.607,17" in html_r
    assert "6.100,61" in html_r
    assert "27.512,49" in html_r
    assert "7.109,88" in html_r
    # Bronze (plano B reajustado / diff) aparece no estudo Anistia seis — conferido à parte.
    r6 = _anistia_com_vinculos()
    snap6 = _aprovar_tmp(tmp_path / "seis", r6)
    html6 = render_html(
        construir_view_model(snap6, modo="resumo", propostas_selecionadas=_ids_seis())
    )
    assert "21.354,64" in html6
    assert "5.518,50" in html6
    assert formatar_reais(_GABARITO["consolidado_atual"]) == "R$ 47.613,62"
    assert formatar_reais(_GABARITO["consolidado_proposta"]) == "R$ 48.479,31"


def test_15_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _anistia_com_vinculos()
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-f2")
    snap = _aprovar(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(modo="completo", propostas_selecionadas=_ids_seis()[:2]),
    )
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="grupo_familiar", propostas_selecionadas=_ids_seis()[:2]
        ),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_montar_grupos_cobertura_sem_perda():
    rascunho = _anistia_com_vinculos()
    from newport_app.models.responses import DetalheVidaComparativo

    detalhes = {
        v.id: DetalheVidaComparativo(
            vida_id=v.id,
            nome=v.nome,
            parentesco=v.parentesco.value if v.parentesco else None,
            vinculo_grupo_chave=v.vinculo_grupo_chave,
        )
        for v in rascunho.vidas
    }
    grupos, aviso = montar_grupos_familiares(detalhes, rascunho)
    assert aviso is None
    ids = {m.vida_id for g in grupos for m in g.membros}
    assert ids == {v.id for v in rascunho.vidas}
