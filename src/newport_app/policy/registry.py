"""PolicySet versionado — políticas administrativas somente leitura."""

from __future__ import annotations

from dataclasses import dataclass

from newport_motor.policy import EffectivePolicy, TolerancePolicy
from newport_motor.types import RateBasisPoints, RoundingStrategy

POLICY_SET_VERSAO_PADRAO = "v2026.07-provisoria"


@dataclass(frozen=True)
class PolicySet:
    versao: str
    max_vidas_homologadas: int | None
    iof_bps: RateBasisPoints
    tolerancias: TolerancePolicy
    estrategia_arredondamento: RoundingStrategy
    politicas_resolvidas: dict[str, object]


def _policy_v2026_07_provisoria() -> PolicySet:
    return PolicySet(
        versao=POLICY_SET_VERSAO_PADRAO,
        max_vidas_homologadas=29,
        iof_bps=RateBasisPoints(238),
        tolerancias=TolerancePolicy(),
        estrategia_arredondamento=RoundingStrategy.POR_VIDA_ENTAO_SOMA,
        politicas_resolvidas={},
    )


_REGISTRY: dict[str, PolicySet] = {
    POLICY_SET_VERSAO_PADRAO: _policy_v2026_07_provisoria(),
}


class PolicySetRegistry:
    def resolve(self, versao: str) -> PolicySet | None:
        return _REGISTRY.get(versao)


default_registry = PolicySetRegistry()
