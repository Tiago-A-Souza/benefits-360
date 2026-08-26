"""Estruturas de resultado do motor."""

from __future__ import annotations

from pydantic import BaseModel, Field

from newport_motor.provenance import LinhagemReferencia, ProvenienciaCampo
from newport_motor.types import RegimeCopartTipo, SeveridadeValidacao


class Validacao(BaseModel):
    codigo: str
    severidade: SeveridadeValidacao
    mensagem: str
    alvo_ref: str | None = None


class ValorCalculado(BaseModel):
    centavos: int
    proveniencia: ProvenienciaCampo
    fontes: list[LinhagemReferencia] = Field(default_factory=list)


class ResultadoVida(BaseModel):
    vida_id: str
    idade: int | None = None
    faixa: int | None = None
    atual_vigente_centavos: ValorCalculado | None = None
    atual_reajustado_centavos: ValorCalculado | None = None
    proposta_centavos: ValorCalculado | None = None
    diff_mes_centavos: ValorCalculado | None = None
    diff_ano_centavos: ValorCalculado | None = None


class ResultadoSubgrupo(BaseModel):
    subgrupo_id: str
    opcao_plano_id: str | None = None
    subtotal_proposta_centavos: ValorCalculado | None = None
    subtotal_atual_vigente_centavos: ValorCalculado | None = None
    subtotal_atual_reajustado_centavos: ValorCalculado | None = None
    vidas: list[ResultadoVida] = Field(default_factory=list)


class ScenarioSectionResult(BaseModel):
    """Bloco disjunto por regime de coparticipação (P6)."""

    regime_tipo: RegimeCopartTipo
    rotulo_derivado: str
    subgrupos: list[ResultadoSubgrupo] = Field(default_factory=list)
    total_proposta_centavos: ValorCalculado | None = None
    total_atual_baseline_centavos: ValorCalculado | None = None
    diff_mes_centavos: ValorCalculado | None = None
    diff_ano_centavos: ValorCalculado | None = None


class ScenarioResult(BaseModel):
    cenario_id: str
    baseline_apresentado: str
    secoes: list[ScenarioSectionResult] = Field(default_factory=list)
    total_proposta_centavos: ValorCalculado | None = None
    total_atual_baseline_centavos: ValorCalculado | None = None
    diff_mes_centavos: ValorCalculado | None = None
    diff_ano_centavos: ValorCalculado | None = None


class MotorResult(BaseModel):
    estudo_id: str
    cenarios: list[ScenarioResult] = Field(default_factory=list)
    # Grade completa: cada opção usada × cada subgrupo com vidas (renovação).
    # Irmã de `cenarios` — não altera significado dos ScenarioResult.
    # Seguro novo: lista vazia (não há subgrupo atual).
    grade_opcao_subgrupo: list[ResultadoSubgrupo] = Field(default_factory=list)
    validacoes: list[Validacao] = Field(default_factory=list)
    politicas_efetivas: dict[str, object] = Field(default_factory=dict)
    bloqueios_abertos: list[str] = Field(default_factory=list)

    @property
    def tem_bloqueio(self) -> bool:
        return any(v.severidade == SeveridadeValidacao.BLOQUEANTE for v in self.validacoes)

    def codigos_bloqueio(self) -> list[str]:
        return [v.codigo for v in self.validacoes if v.severidade == SeveridadeValidacao.BLOQUEANTE]
