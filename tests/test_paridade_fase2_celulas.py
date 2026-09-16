"""Fase 2 — paridade estrutural nas células geradas (48 − inválidas).

Duas camadas × quatro modos. Defeitos de produto: xfail(strict), sem correção.

Preparação (rascunho → matriz → snapshot aprovado) é **uma vez por célula**
(fixture module-scoped). Os quatro modos só leem o estado compartilhado.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from newport_app.models.draft import RascunhoEstudo
from newport_app.models.responses import ComparativoResponse
from newport_app.models.snapshot import SnapshotCalculo
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import render_html, render_html_completo
from newport_app.presentation.paridade_estrutural import divergencias_estruturais
from newport_app.presentation.paridade_html import (
    divergencias_celulas_pos,
    divergencias_html_vm,
    inventariar_html,
    inventariar_vm,
    valores_principais_vm,
)
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from tests.gerador_celulas_estruturais import (
    CelulaEstrutural,
    enumerar_celulas_invalidas,
    enumerar_celulas_totais,
    enumerar_celulas_validas,
    gerar_rascunho,
)
from tests.test_paridade_matriz_html import _aprovar, _calcular_matriz

_APROV = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc)
_MODOS = ("resumo", "faixas", "grupo_familiar", "completo")
_CELULAS_VALIDAS = enumerar_celulas_validas()

# Defeitos de produto conhecidos nesta grade:
# - beneficiario: html_renderer._render_beneficiarios chama
#   `_th_proposta(op_id, [], rotulos)` — lista vazia, então o TH não recebe o
#   objeto PropostaApresentacao (operadora via .od). O nome ainda vem de
#   `rotulos` (mapa do VM), então a paridade de rótulo HTML↔VM não quebra.
#   NÃO corrigido nesta entrega (sem autorização de produto). Sem xfail:
#   baseline verde; o defeito é de apresentação (operadora), não de inventário.
_XFAIL_POR_ID: dict[str, str] = {}


@dataclass(frozen=True)
class CelulaPreparada:
    """Estado compartilhado entre modos — somente leitura."""

    celula: CelulaEstrutural
    rascunho: RascunhoEstudo
    matriz: ComparativoResponse
    snap: SnapshotCalculo
    ids: tuple[str, ...]


def test_contagem_celulas_gerador():
    totais = enumerar_celulas_totais()
    validas = enumerar_celulas_validas()
    invalidas = enumerar_celulas_invalidas()
    assert len(totais) == 48
    assert len(validas) + len(invalidas) == 48
    assert len(validas) == 36
    assert len(invalidas) == 12
    nomes = {c.nome for c in validas}
    assert "renovacao_3_3_3" in nomes or "renovacao_3_3_6" in nomes
    assert "novo_0_2_3" in nomes
    assert "novo_0_1_6" in nomes
    assert "renovacao_3_2_3" in nomes
    assert "novo_0_1_3" in nomes


def _preparar(tmp_path: Path, celula: CelulaEstrutural) -> CelulaPreparada:
    rascunho = gerar_rascunho(celula)
    sincronizar_cenarios(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = tuple(p.opcao_id for p in matriz.propostas if p.calculo_realizado)
    assert ids, f"{celula.nome}: nenhuma proposta calculada"
    assert len(ids) == celula.n_propostas
    return CelulaPreparada(
        celula=celula,
        rascunho=rascunho,
        matriz=matriz,
        snap=snap,
        ids=ids,
    )


def _assinatura_compartilhada(prep: CelulaPreparada) -> dict[str, Any]:
    """Retrato do estado compartilhado — modos não podem alterá-lo."""
    return {
        "ids": prep.ids,
        "matriz_id": id(prep.matriz),
        "snap_id": id(prep.snap),
        "rascunho_id": id(prep.rascunho),
        "rotulos_prop": tuple(
            (p.opcao_id, p.plano_nome) for p in prep.matriz.propostas
        ),
        "rotulos_planos": tuple(
            (p.subgrupo_id, p.plano_nome) for p in prep.matriz.planos_atuais
        ),
        "snap_hash": prep.snap.hash_sha256,
        "n_planos_payload": len(
            (prep.snap.payload.get("comparativo") or {}).get("planos_atuais") or []
        ),
        "rascunho_subgrupos": tuple(
            (sg.id, sg.plano_nome) for sg in prep.rascunho.subgrupos_atuais
        ),
    }


def _vm(snap: SnapshotCalculo, modo: str, ids: tuple[str, ...]):
    # list(ids) — cópia rasa; não reutiliza buffer mutável entre modos.
    return construir_view_model(
        snap,
        modo=modo,
        propostas_selecionadas=list(ids),
        beneficiarios_agregados=False,
        aprovado_em=_APROV,
    )


def divergencias_html_completo(vm_r, vm_f, vm_b, html: str) -> list[str]:
    """Inventário do documento completo contra os três VMs (sem lista à mão)."""
    ih = inventariar_html(html)
    ih_r = inventariar_html(html, secao_id="visao-resumo")
    ih_f = inventariar_html(html, secao_id="visao-faixas")
    ih_b = inventariar_html(html, secao_id="visao-benef")
    divs: list[str] = []
    iv_r, iv_f, iv_b = inventariar_vm(vm_r), inventariar_vm(vm_f), inventariar_vm(vm_b)

    falta_prop = sorted(iv_r.propostas - ih.propostas)
    if falta_prop:
        divs.append(f"completo: propostas ausentes no HTML: {falta_prop}")

    falta_fx = sorted(iv_f.faixas - ih_f.faixas)
    if falta_fx:
        divs.append(f"completo: faixas ausentes no HTML: {falta_fx}")

    if iv_r.planos:
        falta_pl_r = sorted(iv_r.planos - ih_r.planos_linha_resumo)
        if falta_pl_r:
            divs.append(
                f"completo/resumo: planos ausentes nas linhas: {falta_pl_r}"
            )

    # Faixas: vigentes não são mais colunas. Nomes ficam nas linhas do resumo.

    if iv_b.vidas:
        falta_v = sorted(iv_b.vidas - ih_b.vidas)
        if falta_v:
            divs.append(
                f"completo: vidas ausentes no HTML ({len(falta_v)}): {falta_v[:8]}"
                + ("…" if len(falta_v) > 8 else "")
            )

    principais = valores_principais_vm(vm_r) | valores_principais_vm(vm_f)
    ausentes = sorted(principais - ih.valores_centavos)
    if ausentes:
        divs.append(
            "completo: valores principais ausentes: "
            + ", ".join(formatar_reais(c) for c in ausentes[:8])
            + ("…" if len(ausentes) > 8 else "")
        )

    divs.extend(
        divergencias_celulas_pos(
            iv_r.celulas_pos, ih_r.celulas_pos, prefixo="completo/resumo: "
        )
    )
    divs.extend(
        divergencias_celulas_pos(
            iv_f.celulas_pos, ih_f.celulas_pos, prefixo="completo/faixas: "
        )
    )
    divs.extend(
        divergencias_celulas_pos(
            iv_b.celulas_pos, ih_b.celulas_pos, prefixo="completo/benef: "
        )
    )

    modelo_vals = (
        set(iv_r.valores_centavos)
        | set(iv_f.valores_centavos)
        | set(iv_b.valores_centavos)
        | {0}
    )
    inventados = sorted(ih.valores_centavos - modelo_vals)
    if inventados:
        divs.append(
            "completo: valores no HTML ausentes do modelo: "
            + ", ".join(formatar_reais(c) for c in inventados[:8])
            + ("…" if len(inventados) > 8 else "")
        )
    return divs


def _rodar_modo(prep: CelulaPreparada, modo: str) -> list[str]:
    """Só lê prep; VM/HTML são locais ao modo."""
    antes = _assinatura_compartilhada(prep)
    divs: list[str] = []
    if modo == "completo":
        vm_r = _vm(prep.snap, "resumo", prep.ids)
        vm_f = _vm(prep.snap, "faixas", prep.ids)
        vm_g = construir_view_model(
            prep.snap,
            modo="grupo_familiar",
            propostas_selecionadas=list(prep.ids),
            beneficiarios_agregados=False,
            aprovado_em=_APROV,
        )
        for rotulo, vm in (("resumo", vm_r), ("faixas", vm_f), ("grupo_familiar", vm_g)):
            d = divergencias_estruturais(prep.matriz, vm, rascunho=prep.rascunho)
            divs.extend(f"camada1/{rotulo}: {x}" for x in d)
        html = render_html_completo(vm_r, vm_f, vm_g)
        divs.extend(
            f"camada2/completo: {x}"
            for x in divergencias_html_completo(vm_r, vm_f, vm_g, html)
        )
    else:
        vm = _vm(prep.snap, modo, prep.ids)
        d1 = divergencias_estruturais(prep.matriz, vm, rascunho=prep.rascunho)
        divs.extend(f"camada1: {x}" for x in d1)
        html = render_html(vm)
        d2 = divergencias_html_vm(vm, html)
        divs.extend(f"camada2: {x}" for x in d2)

    depois = _assinatura_compartilhada(prep)
    assert antes == depois, (
        f"modo={modo} mutou estado compartilhado da célula {prep.celula.nome}: "
        f"antes={antes!r} depois={depois!r}"
    )
    return divs


@pytest.fixture(scope="module", params=_CELULAS_VALIDAS, ids=lambda c: c.nome)
def celula_preparada(request, tmp_path_factory) -> CelulaPreparada:
    """Calcula e aprova uma vez por célula; modos compartilham só leitura."""
    celula: CelulaEstrutural = request.param
    path = tmp_path_factory.mktemp(f"fase2-{celula.nome}")
    return _preparar(path, celula)


@pytest.mark.parametrize("modo", list(_MODOS))
def test_paridade_celula_estrutural(celula_preparada: CelulaPreparada, modo: str):
    tid = f"{modo}-{celula_preparada.celula.nome}"
    motivo = _XFAIL_POR_ID.get(tid)
    if motivo:
        pytest.xfail(motivo)

    divs = _rodar_modo(celula_preparada, modo)
    assert not divs, (
        f"{celula_preparada.celula.nome}/{modo} falhou:\n- " + "\n- ".join(divs)
    )


def test_coleta_divergencias_fase2(tmp_path: Path):
    """Inventário de falhas da grade 36×modos; falha se qualquer combinação divergir."""
    relatorio: list[str] = []
    n_falha = 0
    for celula in enumerar_celulas_validas():
        prep = _preparar(tmp_path / celula.nome, celula)
        for modo in _MODOS:
            divs = _rodar_modo(prep, modo)
            if divs:
                n_falha += 1
                relatorio.append(f"### {celula.nome} / modo={modo}")
                relatorio.extend(f"  - {d}" for d in divs)
    print(f"CELULAS_VALIDAS={len(enumerar_celulas_validas())}")
    print(f"CELULAS_INVALIDAS={len(enumerar_celulas_invalidas())}")
    print(f"CASOS_MODO_COM_FALHA={n_falha}")
    print("\n".join(relatorio) if relatorio else "NENHUMA_FALHA")
    assert n_falha == 0, (
        f"coleta fase2: {n_falha} casos com falha\n" + "\n".join(relatorio)
    )


def test_modos_nao_escrevem_estado_compartilhado(celula_preparada: CelulaPreparada):
    """Trava explícita: os quatro modos só leem matriz/snap/rascunho."""
    base = _assinatura_compartilhada(celula_preparada)
    for modo in _MODOS:
        _rodar_modo(celula_preparada, modo)
        assert _assinatura_compartilhada(celula_preparada) == base, (
            f"após modo={modo} o estado compartilhado divergiu"
        )
