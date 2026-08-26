"""Gerador sintético das células estruturais (fase 2).

Cruzamento: formato × planos vigentes × regimes × propostas.
Buckets (diagnóstico Parte C): planos renovação {1,2,3}, novo {0};
regimes {1,2,3}; propostas {1,2,3,6} (3 representa o bucket 3–5).

Combinações inválidas (não geradas):
- renovação com 0 planos / novo com planos > 0 (fora do cruzamento)
- n_propostas < n_regimes (impossível exercer N regimes distintos com menos
  propostas — cada proposta carrega um único regime)
- restrições Parte B que o próprio formato já evita (baseline/subgrupo em
  renovação; vidas sem subgrupo e catálogo sem planos em novo)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterator, Literal

from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    TabelaFaixaRascunho,
    VidaRascunho,
)
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios

Formato = Literal["renovacao", "novo"]

# Buckets do diagnóstico (proposta: 3 cobre o intervalo 3–5, incl. IVTEC real).
PLANOS_RENOVACAO = (1, 2, 3)
PLANOS_NOVO = (0,)
REGIMES = (1, 2, 3)
PROPOSTAS = (1, 2, 3, 6)

_REGIME_CATALOGO: tuple[tuple[str, str, int | None], ...] = (
    ("regime-sem", "sem", None),
    ("regime-parcial", "parcial", None),
    ("regime-percentual", "percentual", 30),
)

_DATA_REF = date(2026, 6, 30)

# Nascimentos que caem em faixas 0, 2, 4, 6, 8 (vidas reais, faixas distintas).
_NASC_POR_FAIXA = {
    0: date(2015, 6, 15),
    2: date(2000, 6, 15),
    4: date(1990, 6, 15),
    6: date(1980, 6, 15),
    8: date(1970, 6, 15),
}


@dataclass(frozen=True)
class CelulaEstrutural:
    formato: Formato
    n_planos: int
    n_regimes: int
    n_propostas: int

    @property
    def nome(self) -> str:
        return f"{self.formato}_{self.n_planos}_{self.n_regimes}_{self.n_propostas}"

    @property
    def valida(self) -> bool:
        if self.formato == "novo" and self.n_planos != 0:
            return False
        if self.formato == "renovacao" and self.n_planos < 1:
            return False
        # Cada proposta tem um regime: não há como ter mais regimes distintos
        # entre as selecionadas do que propostas.
        if self.n_propostas < self.n_regimes:
            return False
        return True


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL,
        extrator_versao="manual",
        confirmado=True,
    )


def enumerar_celulas_totais() -> list[CelulaEstrutural]:
    """As 48 células do cruzamento (válidas e inválidas por props < regimes)."""
    out: list[CelulaEstrutural] = []
    for n_planos in PLANOS_RENOVACAO:
        for n_regimes in REGIMES:
            for n_propostas in PROPOSTAS:
                out.append(
                    CelulaEstrutural("renovacao", n_planos, n_regimes, n_propostas)
                )
    for n_planos in PLANOS_NOVO:
        for n_regimes in REGIMES:
            for n_propostas in PROPOSTAS:
                out.append(CelulaEstrutural("novo", n_planos, n_regimes, n_propostas))
    return out


def enumerar_celulas_validas() -> list[CelulaEstrutural]:
    return [c for c in enumerar_celulas_totais() if c.valida]


def enumerar_celulas_invalidas() -> list[CelulaEstrutural]:
    return [c for c in enumerar_celulas_totais() if not c.valida]


def _tabela_proposta(indice: int) -> list[TabelaFaixaRascunho]:
    """Valores distintos por proposta (offset) para detectar troca de coluna."""
    base = 90_000 + indice * 17_000
    return [
        TabelaFaixaRascunho(
            faixa=f,
            valor_centavos=base + f * 11_000 + indice * 130,
            quantidade_cotada=0,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            proveniencia=_prov(),
        )
        for f in range(10)
    ]


def _tabela_atual(indice_plano: int) -> list[TabelaFaixaRascunho]:
    base = 70_000 + indice_plano * 9_000
    return [
        TabelaFaixaRascunho(
            faixa=f,
            valor_centavos=base + f * 7_000,
            quantidade_cotada=None,
            price_basis=PriceBasisRascunho.EXCLUI_IOF,
            proveniencia=_prov(),
        )
        for f in range(10)
    ]


def _regimes(n: int) -> list[RegimeCopartRascunho]:
    out: list[RegimeCopartRascunho] = []
    for i in range(n):
        rid, tipo, pct = _REGIME_CATALOGO[i]
        out.append(RegimeCopartRascunho(id=rid, tipo=tipo, percentual=pct))
    return out


def _vidas(
    *,
    n_planos: int,
    formato: Formato,
    n_vidas: int = 12,
) -> list[VidaRascunho]:
    faixas_ciclo = list(_NASC_POR_FAIXA.keys())
    vidas: list[VidaRascunho] = []
    for i in range(n_vidas):
        fx = faixas_ciclo[i % len(faixas_ciclo)]
        sg_id = None
        if formato == "renovacao":
            sg_id = f"sg-{(i % n_planos) + 1}"
        vidas.append(
            VidaRascunho(
                id=f"v{i}",
                nome=f"Beneficiário sintético {i + 1}",
                nascimento=_NASC_POR_FAIXA[fx],
                incluida=True,
                subgrupo_atual_id=sg_id,
            )
        )
    return vidas


def gerar_rascunho(celula: CelulaEstrutural) -> RascunhoEstudo:
    """Rascunho sintético determinístico para a célula. Raises se inválida."""
    if not celula.valida:
        raise ValueError(f"célula inválida: {celula.nome}")

    regimes = _regimes(celula.n_regimes)
    subgrupos: list[SubgrupoAtualRascunho] = []
    if celula.formato == "renovacao":
        for i in range(celula.n_planos):
            subgrupos.append(
                SubgrupoAtualRascunho(
                    id=f"sg-{i + 1}",
                    operadora=f"Operadora {i + 1}",
                    plano_nome=f"Plano vigente {i + 1}",
                    regime_copart_id=regimes[0].id,
                    tipo_fiscal="operadora",
                    acomodacao="Apartamento",
                    reajuste_bps=1200,
                    fatura_price_basis=PriceBasisRascunho.EXCLUI_IOF,
                    tabela_atual=_tabela_atual(i),
                )
            )

    opcoes: list[OpcaoPropostaRascunho] = []
    for i in range(celula.n_propostas):
        regime = regimes[i % celula.n_regimes]
        opcoes.append(
            OpcaoPropostaRascunho(
                id=f"op-{i + 1}",
                operadora=f"Operadora P{i + 1}",
                plano_nome=f"Proposta sintética {i + 1}",
                regime_copart_id=regime.id,
                tipo_fiscal="operadora",
                tabela=_tabela_proposta(i),
                validade_oficial=date(2026, 8, 1),
            )
        )

    if celula.formato == "renovacao":
        escolhas = EscolhasEstudo(
            data_referencia_idade=_DATA_REF,
            baseline_escolhido=CampoConfirmavelBaseline(
                valor="reajustado", confirmado=True
            ),
            precedencia_atual_vida=CampoConfirmavelPrecedencia(
                valor="tabela_atual", confirmado=True
            ),
        )
    else:
        escolhas = EscolhasEstudo(
            data_referencia_idade=_DATA_REF,
            baseline_escolhido=CampoConfirmavelBaseline(),
            precedencia_atual_vida=CampoConfirmavelPrecedencia(),
        )

    rascunho = RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id=f"cel-{celula.nome}",
        titulo=f"Célula estrutural {celula.nome}",
        formato=celula.formato,
        vidas=_vidas(n_planos=max(celula.n_planos, 1), formato=celula.formato),
        subgrupos_atuais=subgrupos,
        opcoes_proposta=opcoes,
        regimes_copart=regimes,
        cenarios=[],
        escolhas=escolhas,
    )
    sincronizar_cenarios(rascunho)
    return rascunho


def iter_celulas_nomeadas() -> Iterator[tuple[str, CelulaEstrutural]]:
    for celula in enumerar_celulas_validas():
        yield celula.nome, celula
