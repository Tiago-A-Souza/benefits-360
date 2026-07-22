"""EffectivePolicy — políticas já resolvidas fora do motor."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field, field_validator

from newport_motor.types import (
    BaselineEscolhido,
    PrecedenciaAtualVida,
    RateBasisPoints,
    RoundingStrategy,
)


class TolerancePolicy(BaseModel):
    por_vida_centavos: int = 1
    subtotal_centavos: int = 2
    total_centavos: int = 5

    @field_validator("por_vida_centavos", "subtotal_centavos", "total_centavos")
    @classmethod
    def tolerancia_nao_negativa(cls, v: int) -> int:
        if v < 0:
            raise ValueError("tolerância não pode ser negativa")
        return v


class EffectivePolicy(BaseModel):
    """Política efetiva recebida pelo motor; nunca resolvida internamente."""

    policy_set_versao: str = "v2026.07-provisoria"
    data_referencia_idade: date | None = None
    baseline_escolhido: BaselineEscolhido | None = None
    precedencia_atual_vida: PrecedenciaAtualVida | None = None
    iof_bps: RateBasisPoints = RateBasisPoints(238)
    tolerancias: TolerancePolicy = Field(default_factory=TolerancePolicy)
    estrategia_arredondamento: RoundingStrategy = RoundingStrategy.POR_VIDA_ENTAO_SOMA
    politicas_resolvidas: dict[str, object] = Field(default_factory=dict)

    @field_validator("iof_bps")
    @classmethod
    def iof_bps_nao_negativo(cls, v: RateBasisPoints) -> RateBasisPoints:
        if int(v) < 0:
            raise ValueError("iof_bps não pode ser negativo")
        return v

    def as_snapshot_dict(self) -> dict[str, object]:
        return {
            "policy_set_versao": self.policy_set_versao,
            "data_referencia_idade": (
                self.data_referencia_idade.isoformat() if self.data_referencia_idade else None
            ),
            "baseline_escolhido": (
                self.baseline_escolhido.value if self.baseline_escolhido else None
            ),
            "precedencia_atual_vida": (
                self.precedencia_atual_vida.value if self.precedencia_atual_vida else None
            ),
            "iof_bps": int(self.iof_bps),
            "tolerancias": self.tolerancias.model_dump(),
            "estrategia_arredondamento": self.estrategia_arredondamento.value,
            "politicas_resolvidas": self.politicas_resolvidas,
        }
