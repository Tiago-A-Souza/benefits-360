"""Tipos primitivos do domínio financeiro."""

from __future__ import annotations

from enum import Enum
from typing import NewType

MoneyCents = NewType("MoneyCents", int)
RateBasisPoints = NewType("RateBasisPoints", int)


class PriceBasis(str, Enum):
    INCLUI_IOF = "inclui_iof"
    EXCLUI_IOF = "exclui_iof"
    DESCONHECIDO = "desconhecido"


class TipoFiscal(str, Enum):
    SEGURADORA = "seguradora"
    OPERADORA = "operadora"


class FormatoEstudo(str, Enum):
    NOVO = "novo"
    RENOVACAO = "renovacao"


class BaselineEscolhido(str, Enum):
    VIGENTE = "vigente"
    REAJUSTADO = "reajustado"


class RegimeCopartTipo(str, Enum):
    SEM = "sem"
    PARCIAL = "parcial"
    PERCENTUAL = "percentual"
    CUSTOMIZADA = "customizada"


class RoundingStrategy(str, Enum):
    POR_VIDA_ENTAO_SOMA = "por_vida_entao_soma"
    SOMA_ENTAO_APLICA = "soma_entao_aplica"
    NO_TOTAL = "no_total"


class PrecedenciaAtualVida(str, Enum):
    """Escolha bloqueante quando tabela atual e fatura coexistem (DP-02)."""

    TABELA_ATUAL = "tabela_atual"
    VALOR_FATURA = "valor_fatura"


class OrigemValor(str, Enum):
    EXTRAIDO = "extraido"
    CALCULADO = "calculado"
    MANUAL = "manual"
    IA = "ia"


class EstadoExtracao(str, Enum):
    EXTRAIDO_OK = "extraido_ok"
    EXTRAIDO_COM_ALERTA = "extraido_com_alerta"
    FALHA_EXTRACAO = "falha_extracao"
    MANUAL = "manual"


class SeveridadeValidacao(str, Enum):
    INFO = "info"
    ALERTA = "alerta"
    BLOQUEANTE = "bloqueante"
