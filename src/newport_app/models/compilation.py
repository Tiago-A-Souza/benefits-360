"""Resultado tipado da compilação de rascunho — ETAPA 2.2."""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from newport_motor.models import EstudoInput
from newport_motor.policy import EffectivePolicy

COMPILER_VERSAO = "2.2.6"


class ErroCompilacao(BaseModel):
    codigo: str
    caminho: str
    mensagem: str
    severidade: str = "bloqueante"


class AvisoCompilacao(BaseModel):
    codigo: str
    caminho: str
    mensagem: str
    severidade: str = "alerta"


class Compilado(BaseModel):
    estudo_input: EstudoInput
    effective_policy: EffectivePolicy


class ResultadoCompilacao(BaseModel):
    compilado: Compilado | None = None
    erros: list[ErroCompilacao] = Field(default_factory=list)
    avisos: list[AvisoCompilacao] = Field(default_factory=list)
    compiler_versao: str = COMPILER_VERSAO

    @model_validator(mode="after")
    def invariante_compilado(self) -> ResultadoCompilacao:
        if self.erros and self.compilado is not None:
            raise ValueError("compilado deve ser None quando há erros")
        if not self.erros and self.compilado is None:
            raise ValueError("compilado é obrigatório quando não há erros")
        return self

    @property
    def compilavel(self) -> bool:
        return self.compilado is not None and not self.erros
