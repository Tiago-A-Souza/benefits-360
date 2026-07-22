"""Adaptação legada — use draft_compiler.compile()."""

from __future__ import annotations

from newport_app.draft_compiler import compile
from newport_app.models.draft import RascunhoEstudo
from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy


def rascunho_para_estudo_input(rascunho: RascunhoEstudo) -> EstudoInput:
    resultado = compile(rascunho)
    if not resultado.compilavel or resultado.compilado is None:
        raise ValueError("rascunho não compilável")
    return resultado.compilado.estudo_input


def rascunho_para_policy(rascunho: RascunhoEstudo) -> EffectivePolicy:
    resultado = compile(rascunho)
    if not resultado.compilavel or resultado.compilado is None:
        raise ValueError("rascunho não compilável")
    return resultado.compilado.effective_policy
