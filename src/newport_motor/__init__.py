"""Motor financeiro puro — Sistema de Estudos Newport."""

from newport_motor.engine import calcular
from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy
from newport_motor.result import MotorResult
from newport_motor.types import MoneyCents, PriceBasis, RateBasisPoints

__all__ = [
    "calcular",
    "EstudoInput",
    "EffectivePolicy",
    "MotorResult",
    "MoneyCents",
    "PriceBasis",
    "RateBasisPoints",
]
