"""Testes de agregação no resumo do plano atual (SISCOR/vidas)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    ComponenteFinanceiroRascunho,
    EscolhasEstudo,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual

_FIXTURE_ANISTIA = (
    Path(__file__).resolve().parent / "fixtures" / "resumo_plano_atual" / "anistia_sintetica_36.json"
)


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL,
        extrator_versao="teste",
        confirmado=True,
    )


def _nascimento_para_faixa(faixa: int, data_ref: date) -> date:
    idade = {0: 10, 1: 20, 2: 25, 3: 30, 4: 35, 5: 40, 6: 45, 7: 50, 8: 55, 9: 60}[faixa]
    return date(data_ref.year - idade, 6, 15)


def _rascunho_com_vidas(
    vidas_spec: list[dict],
    *,
    data_ref: date = date(2026, 6, 30),
) -> RascunhoEstudo:
    vidas: list[VidaRascunho] = []
    for i, spec in enumerate(vidas_spec):
        fx = spec["faixa"]
        nasc = spec.get("nascimento")
        v = VidaRascunho(
            id=f"v{i}",
            nome=f"Beneficiário fictício {i + 1}",
            nascimento=date.fromisoformat(nasc) if nasc else _nascimento_para_faixa(fx, data_ref),
            incluida=True,
            subgrupo_atual_id="sg-1",
        )
        cent = spec.get("centavos")
        if cent is not None:
            v.valor_fatura = ComponenteFinanceiroRascunho(
                centavos=cent,
                price_basis=PriceBasisRascunho.EXCLUI_IOF,
                proveniencia=_prov(),
            )
        vidas.append(v)
    return RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id="est-teste",
        titulo="Teste resumo",
        formato="renovacao",
        vidas=vidas,
        subgrupos_atuais=[
            SubgrupoAtualRascunho(
                id="sg-1",
                operadora="Operadora Fictícia",
                plano_nome="Plano Fictício",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
                reajuste_bps=0,
                fatura_price_basis=PriceBasisRascunho.EXCLUI_IOF,
                tabela_atual=[
                    TabelaFaixaRascunho(
                        faixa=f,
                        valor_centavos=80_000,
                        quantidade_cotada=None,
                        price_basis=PriceBasisRascunho.EXCLUI_IOF,
                        proveniencia=_prov(),
                    )
                    for f in range(10)
                ],
            )
        ],
        escolhas=EscolhasEstudo(
            data_referencia_idade=data_ref,
            baseline_escolhido=CampoConfirmavelBaseline(valor="vigente", confirmado=True),
            precedencia_atual_vida=CampoConfirmavelPrecedencia(
                valor="valor_fatura",
                confirmado=True,
            ),
        ),
    )


def _soma_direta(vidas_spec: list[dict]) -> int:
    return sum(v["centavos"] for v in vidas_spec if v.get("centavos") is not None)


def test_resumo_faixa_homogenea():
    spec = [{"faixa": 2, "centavos": 10000}] * 3
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos == 30000
    fx = next(f for f in item.faixas if f.faixa == 2)
    assert fx.valor_observado_reais == "R$ 100,00"
    assert fx.alerta_inconsistencia is None


def test_resumo_faixa_heterogenea_inclui_total():
    spec = [
        {"faixa": 1, "centavos": 10000},
        {"faixa": 1, "centavos": 10000},
        {"faixa": 1, "centavos": 12000},
    ]
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos == 32000
    fx = next(f for f in item.faixas if f.faixa == 1)
    assert fx.valor_observado_reais is None
    assert fx.alerta_inconsistencia is not None


def test_resumo_multiplas_faixas_mistas():
    spec = [
        {"faixa": 0, "centavos": 5000},
        {"faixa": 0, "centavos": 5000},
        {"faixa": 1, "centavos": 8000},
        {"faixa": 1, "centavos": 9000},
    ]
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos == _soma_direta(spec)


def test_vida_sem_valor_gera_aviso_cobertura():
    spec = [
        {"faixa": 0, "centavos": 10000},
        {"faixa": 0, "centavos": None},
        {"faixa": 1, "centavos": 20000},
    ]
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos == 30000
    assert item.observacao is not None
    assert "1 de 3 beneficiários sem valor informado" in item.observacao


def test_subgrupo_sem_valores():
    spec = [{"faixa": 0, "centavos": None}, {"faixa": 1, "centavos": None}]
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos is None
    assert item.observacao is not None
    assert "sem valor informado" in item.observacao


@pytest.mark.parametrize(
    "valores",
    [
        [10000, 20000, 30000],
        [40978, 47945, 70192],
        [10000] * 5,
        [10000, 10000, 15000, 20000],
    ],
)
def test_propriedade_total_resumo_igual_soma(valores: list[int]):
    spec = [{"faixa": i % 10, "centavos": c} for i, c in enumerate(valores)]
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.valor_mensal_vigente_centavos == sum(valores)


def test_regressao_anistia_sintetica_36_vidas():
    payload = json.loads(_FIXTURE_ANISTIA.read_text(encoding="utf-8"))
    data_ref = date.fromisoformat(payload["data_referencia"])
    rascunho = _rascunho_com_vidas(payload["vidas"], data_ref=data_ref)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    assert item.quantidade_beneficiarios == 36
    assert item.valor_mensal_vigente_centavos == payload["total_esperado_centavos"]
    assert item.valor_mensal_vigente_centavos == _soma_direta(payload["vidas"])
    assert item.valor_mensal_vigente_centavos != payload["total_bug_centavos"]
    fx1 = next(f for f in item.faixas if f.faixa == 1)
    fx4 = next(f for f in item.faixas if f.faixa == 4)
    assert fx1.valor_observado_reais is None
    assert fx4.valor_observado_reais is None
    assert fx1.alerta_inconsistencia is not None
    assert fx4.alerta_inconsistencia is not None


def test_nao_regressao_subgrupo_homogeneo():
    cent = 340_938
    spec = [{"faixa": 3, "centavos": cent}] * 5
    rascunho = _rascunho_com_vidas(spec)
    item = montar_resumo_plano_atual(rascunho).planos[0]
    esperado = cent * 5
    assert item.valor_mensal_vigente_centavos == esperado
    fx = next(f for f in item.faixas if f.faixa == 3)
    assert fx.valor_observado_reais is not None
    assert fx.alerta_inconsistencia is None
