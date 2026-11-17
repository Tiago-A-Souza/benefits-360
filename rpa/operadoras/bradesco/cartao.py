"""Um card do carrossel "Grupo 1 - Saúde" no Resultado do cotador SPG."""
from __future__ import annotations

from dataclasses import dataclass

from nucleo.modelo import PlanoVisto
from nucleo.texto import norm

from .extracao import nome_do_plano


@dataclass
class CardPlano:
    nome_card: str          # como o card mostra: "Nacional Plus"
    reembolso: int          # "Reembolso Completo (4x tabela)" -> 4; 0 = sem multiplicador
    preco: object           # Decimal
    acomodacao: str         # a do Grupo 1 (Quarto/Enfermaria)
    pagina: int = 1         # página do carrossel

    @property
    def nome(self) -> str:
        """O nome do plano no robô: "Nacional Plus 4x" (o multiplicador diferencia os três Nacional Plus do vídeo)."""
        return nome_do_plano(self.nome_card, self.reembolso)

    def chave(self) -> tuple:
        return (norm(self.nome_card), self.reembolso, self.preco)

    def visto(self, versao: str = "") -> PlanoVisto:
        return PlanoVisto(nome=self.nome, acomodacao=self.acomodacao, preco=self.preco, pagina=self.pagina,
                          descricao=f"reembolso {self.reembolso}x" if self.reembolso else "", versao=versao)
