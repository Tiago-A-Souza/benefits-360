"""Inventário de remoção de planos do comparativo — FASE 0, reusado na FASE 1.

Neutro de propósito: a re-aplicação de um PDF e a seleção por grupo removem
planos por caminhos diferentes, mas o que o operador precisa saber é o mesmo.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AtribuicaoDesfeita(BaseModel):
    cenario_id: str
    cenario_rotulo: str
    alvo_id: str
    alvo_rotulo: str
    plano: str


class CenarioIncompleto(BaseModel):
    cenario_id: str
    cenario_rotulo: str
    alvos_sem_atribuicao: list[str] = Field(default_factory=list)
    ficou_vazio: bool = False


class ImpactoRemocao(BaseModel):
    """Planos que saem do comparativo e o que isso desfaz na etapa 4."""

    planos_removidos: list[str] = Field(default_factory=list)
    atribuicoes_desfeitas: list[AtribuicaoDesfeita] = Field(default_factory=list)
    cenarios_incompletos: list[CenarioIncompleto] = Field(default_factory=list)

    @property
    def houve_remocao(self) -> bool:
        return bool(self.planos_removidos)

    @property
    def exige_confirmacao(self) -> bool:
        """Confirmação só quando a remoção derruba atribuição de cenário.

        Remoção sem dano colateral é relatada e aplicada: pedir confirmação nela
        treinaria o operador a passar direto pelo caso que importa.
        """
        return bool(self.atribuicoes_desfeitas)
