"""Uma linha da grade de planos da Porto (passo 3)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class PlanoNaTela:
    nome: str
    familia: str
    acomodacao: str
    coparticipacao: str
    preco: Decimal
