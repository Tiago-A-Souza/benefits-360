"""Helpers compartilhados para fixtures e testes."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from newport_motor.models import (
    AtribuicaoPlano,
    Cenario,
    CustoUnico,
    DocumentoCotacao,
    EstudoInput,
    OpcaoPlano,
    RegimeCopart,
    SubgrupoAtual,
    TabelaPrecoFaixa,
    Vida,
)
from newport_motor.policy import EffectivePolicy
from newport_motor.provenance import ComponenteFinanceiro, ProvenienciaCampo
from newport_motor.types import (
    BaselineEscolhido,
    EstadoExtracao,
    FormatoEstudo,
    OrigemValor,
    PrecedenciaAtualVida,
    PriceBasis,
    RegimeCopartTipo,
    RoundingStrategy,
    TipoFiscal,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def tabela_padrao(
    base_centavos: int = 100_000,
    incremento: int = 10_000,
    basis: PriceBasis = PriceBasis.EXCLUI_IOF,
) -> list[TabelaPrecoFaixa]:
    return [
        TabelaPrecoFaixa(
            faixa=f,
            valor_centavos=base_centavos + f * incremento,
            quantidade_cotada=0,
            price_basis=basis,
        )
        for f in range(10)
    ]


def regime(tipo: RegimeCopartTipo, suffix: str = "1") -> RegimeCopart:
    return RegimeCopart(id=f"regime-{tipo.value}-{suffix}", tipo=tipo)


def opcao_plano(
    opcao_id: str,
    operadora: str = "Bradesco",
    regime_id: str = "regime-sem-1",
    tipo_fiscal: TipoFiscal = TipoFiscal.SEGURADORA,
    base: int = 100_000,
    incremento: int = 10_000,
    tabela_basis: PriceBasis = PriceBasis.EXCLUI_IOF,
    total_recorrente: int | None = None,
    total_recorrente_basis: PriceBasis | None = None,
    total_primeira: int | None = None,
    custos_unicos: list[CustoUnico] | None = None,
    doc_id: str | None = None,
) -> OpcaoPlano:
    tabela = tabela_padrao(base, incremento, tabela_basis)
    tr_basis = total_recorrente_basis or (
        PriceBasis.INCLUI_IOF if tipo_fiscal == TipoFiscal.SEGURADORA else PriceBasis.EXCLUI_IOF
    )
    return OpcaoPlano(
        id=opcao_id,
        operadora=operadora,
        plano_nome=f"Plano {opcao_id}",
        regime_copart_id=regime_id,
        tipo_fiscal=tipo_fiscal,
        tabela=tabela,
        premio_saude=ComponenteFinanceiro(centavos=None, price_basis=tabela_basis),
        total_recorrente=(
            ComponenteFinanceiro(
                centavos=total_recorrente,
                price_basis=tr_basis,
                proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
            )
            if total_recorrente is not None
            else None
        ),
        total_primeira_parcela=(
            ComponenteFinanceiro(
                centavos=total_primeira,
                price_basis=PriceBasis.INCLUI_IOF,
                proveniencia=ProvenienciaCampo(origem=OrigemValor.MANUAL),
            )
            if total_primeira is not None
            else None
        ),
        custos_unicos=custos_unicos or [],
        documento_id=doc_id,
    )


def vida_ficticia(
    vida_id: str,
    nascimento: date,
    subgrupo_id: str | None = None,
    valor_fatura: int | None = None,
    fatura_basis: PriceBasis | None = None,
    incluida: bool = True,
    conferencia: int | None = None,
    conferencia_basis: PriceBasis | None = None,
) -> Vida:
    return Vida(
        id=vida_id,
        nome=f"Beneficiário {vida_id}",
        nascimento=nascimento,
        incluida=incluida,
        subgrupo_atual_id=subgrupo_id,
        valor_fatura_centavos=valor_fatura,
        fatura_price_basis=fatura_basis,
        valor_conferencia_centavos=conferencia,
        conferencia_price_basis=conferencia_basis,
    )


def policy_completa(
    data_ref: date | None = date(2026, 6, 30),
    baseline: BaselineEscolhido | None = BaselineEscolhido.REAJUSTADO,
    precedencia: PrecedenciaAtualVida | None = PrecedenciaAtualVida.TABELA_ATUAL,
    estrategia: RoundingStrategy = RoundingStrategy.POR_VIDA_ENTAO_SOMA,
) -> EffectivePolicy:
    return EffectivePolicy(
        data_referencia_idade=data_ref,
        baseline_escolhido=baseline,
        precedencia_atual_vida=precedencia,
        estrategia_arredondamento=estrategia,
    )


def subgrupo_atual(
    sg_id: str = "sg-1",
    operadora: str = "Bradesco",
    reajuste_bps: int = 1198,
    base_tabela: int = 80_000,
    incremento: int = 8_000,
    tabela_basis: PriceBasis = PriceBasis.EXCLUI_IOF,
    **kwargs,
) -> SubgrupoAtual:
    defaults = dict(
        id=sg_id,
        operadora=operadora,
        tipo_fiscal=TipoFiscal.SEGURADORA,
        plano_nome=f"Plano {sg_id}",
        regime_copart_id="regime-sem-1",
        reajuste_bps=reajuste_bps,
        fatura_price_basis=PriceBasis.EXCLUI_IOF,
        tabela_atual=tabela_padrao(base_tabela, incremento, tabela_basis),
    )
    defaults.update(kwargs)
    return SubgrupoAtual(**defaults)


def load_fixture_case(case_name: str) -> tuple[EstudoInput, EffectivePolicy, dict]:
    case_dir = FIXTURES_DIR / case_name
    with open(case_dir / "input.json", encoding="utf-8") as f:
        input_data = json.load(f)
    with open(case_dir / "effective_policy.json", encoding="utf-8") as f:
        policy_data = json.load(f)
    with open(case_dir / "expected.json", encoding="utf-8") as f:
        expected = json.load(f)
    estudo = EstudoInput.model_validate(input_data)
    policy = EffectivePolicy.model_validate(policy_data)
    return estudo, policy, expected
