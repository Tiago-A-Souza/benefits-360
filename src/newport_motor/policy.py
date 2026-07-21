"""EffectivePolicy — políticas já resolvidas fora do motor."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from newport_motor.types import BaselineEscolhido, RateBasisPoints, RoundingStrategy


class TolerancePolicy(BaseModel):
    por_vida_centavos: int = 1
    subtotal_centavos: int = 2
    total_centavos: int = 5


class EffectivePolicy(BaseModel):
    """Política efetiva recebida pelo motor; nunca resolvida internamente."""

    policy_set_versao: str = "v2026.07-provisoria"
    data_referencia_idade: date | None = None
    baseline_escolhido: BaselineEscolhido | None = None
    iof_bps: RateBasisPoints = RateBasisPoints(238)
    tolerancias: TolerancePolicy = Field(default_factory=TolerancePolicy)
    estrategia_arredondamento: RoundingStrategy = RoundingStrategy.POR_VIDA_ENTAO_SOMA
    politicas_resolvidas: dict[str, object] = Field(default_factory=dict)

    def as_snapshot_dict(self) -> dict[str, object]:
        return {
            "policy_set_versao": self.policy_set_versao,
            "data_referencia_idade": (
                self.data_referencia_idade.isoformat() if self.data_referencia_idade else None
            ),
            "baseline_escolhido": (
                self.baseline_escolhido.value if self.baseline_escolhido else None
            ),
            "iof_bps": int(self.iof_bps),
            "tolerancias": self.tolerancias.model_dump(),
            "estrategia_arredondamento": self.estrategia_arredondamento.value,
            "politicas_resolvidas": self.politicas_resolvidas,
        }
