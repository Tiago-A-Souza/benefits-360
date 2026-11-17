"""O card de um plano na tela Planos do cotador da SulAmérica."""
from __future__ import annotations

from dataclasses import dataclass

from nucleo.modelo import PlanoVisto


@dataclass
class PlanoNaTela:
    nome: str
    acomodacao: str
    descricao: str          # ex.: "557 - AHO - Compulsória - 24 meses"
    coparticipacao: str     # ex.: "Com coparticipação"
    preco: object           # Decimal
    pagina: int = 1

    def visto(self) -> PlanoVisto:
        """Para a aba de preços e o catálogo da tela (núcleo)."""
        return PlanoVisto(nome=self.nome, acomodacao=self.acomodacao, preco=self.preco, pagina=self.pagina,
                          descricao=self.descricao, versao=self.coparticipacao)
