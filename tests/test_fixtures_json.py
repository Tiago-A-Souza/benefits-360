"""Suíte de fixtures JSON determinísticas (expected via oráculo independente)."""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_motor.engine import calcular
from newport_motor.types import SeveridadeValidacao
from tests.conftest import FIXTURES_DIR, load_fixture_case


FIXTURE_CASES = sorted(
    d.name
    for d in FIXTURES_DIR.iterdir()
    if d.is_dir() and (d / "expected.json").exists() and d.name != "renovacao_1plano_12vidas"
)
# incluir renovacao_1plano_12vidas se tiver expected
if (FIXTURES_DIR / "renovacao_1plano_12vidas" / "expected.json").exists():
    if "renovacao_1plano_12vidas" not in FIXTURE_CASES:
        FIXTURE_CASES.append("renovacao_1plano_12vidas")
FIXTURE_CASES = sorted(set(FIXTURE_CASES))


def _proposta_total(result) -> int:
    if not result.cenarios:
        return 0
    c = result.cenarios[0]
    if c.total_proposta_centavos:
        return c.total_proposta_centavos.centavos
    if c.secoes and c.secoes[0].total_proposta_centavos:
        return c.secoes[0].total_proposta_centavos.centavos
    total = 0
    for sec in c.secoes:
        for sg in sec.subgrupos:
            if sg.subtotal_proposta_centavos:
                total += sg.subtotal_proposta_centavos.centavos
    return total


@pytest.mark.parametrize("case_name", FIXTURE_CASES)
def test_fixture_case(case_name: str):
    estudo, policy, expected = load_fixture_case(case_name)
    result = calcular(estudo, policy)

    if expected.get("tem_bloqueio"):
        assert result.tem_bloqueio
    else:
        assert not result.tem_bloqueio

    for codigo in expected.get("bloqueios", []):
        assert codigo in result.codigos_bloqueio(), f"{case_name}: esperava bloqueio {codigo}"

    if "proposta_total_centavos" in expected:
        assert _proposta_total(result) == expected["proposta_total_centavos"], case_name

    if expected.get("tem_cenarios") is True:
        assert result.cenarios

    if expected.get("tem_cenarios") is False:
        assert not result.cenarios

    if "vidas_count" in expected and result.cenarios:
        count = sum(
            len(sg.vidas)
            for c in result.cenarios
            for s in c.secoes
            for sg in s.subgrupos
        )
        assert count == expected["vidas_count"], case_name

    if "secoes_count" in expected and result.cenarios:
        assert len(result.cenarios[0].secoes) == expected["secoes_count"]

    if "subgrupos" in expected and result.cenarios:
        sg_count = sum(len(s.subgrupos) for s in result.cenarios[0].secoes)
        assert sg_count == expected["subgrupos"]

    if "regime" in expected and result.cenarios:
        assert result.cenarios[0].secoes[0].regime_tipo.value == expected["regime"]

    if "estrategia" in expected:
        assert policy.estrategia_arredondamento.value == expected["estrategia"]


def test_fixtures_minimo_exigido():
    """Cobertura mínima de diretórios de fixture."""
    required = {
        "novo_1vida_sem_copart",
        "renovacao_1plano_12vidas",
        "renovacao_2planos_20vidas",
        "renovacao_29vidas",
        "copart_parcial_1vida",
        "copart_percentual_1vida",
        "seguradora_tabela_inclui_iof",
        "total_recorrente_ausente",
        "primeira_parcela_custos_unicos",
        "mesma_opcao_dois_subgrupos",
        "divergencia_por_vida",
        "divergencia_subtotal",
        "divergencia_total",
        "price_basis_desconhecido",
        "arredondamento_soma_entao_aplica",
    }
    present = {d.name for d in FIXTURES_DIR.iterdir() if d.is_dir()}
    missing = required - present
    assert not missing, f"Fixtures ausentes: {missing}"
