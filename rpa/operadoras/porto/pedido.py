"""Pedido de cotação da Porto Seguro Saúde PME.

1 plano = 1 cotação = 1 PDF. Não há processo nem oportunidade que agrupe as cotações:
cada plano começa em "Criar nova cotação". A chave anti-reemissão (nucleo.estado) junta
CNPJ + vidas e idades + plano anterior + comissão + acomodação + coparticipação + extras
(+ o plano, na chave do registro). O apelido só entra no nome do PDF.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from nucleo.modelo import PlanoAlvo
from nucleo.texto import norm

COMISSAO_K001 = "K001 | ag1(100%) | ag2(100%) | ag3(0%) | Corretagem(5%)"
ACOMODACOES = ("Apartamento", "Enfermaria")
COPARTS = ("com", "sem", "as_duas")
# Nomes como a grade da Porto mostra (vídeo, passo 3). Acomodação é escolhida à parte.
PLANOS_CONHECIDOS = [
    ("Ouro Pro", "Apartamento"), ("Diamante Pro", "Apartamento"),
    ("P220", "Apartamento"), ("P320", "Apartamento"), ("P420", "Apartamento"), ("P470", "Apartamento"),
    ("Bronze Brasil I", "Apartamento"), ("Prata Mais I", "Apartamento"),
    ("Ouro Mais I", "Apartamento"), ("Ouro Max I", "Apartamento"),
]
FAMILIA = {
    "ouro pro": "Pro", "diamante pro": "Pro",
    "p220": "Porto Saúde", "p320": "Porto Saúde", "p420": "Porto Saúde", "p470": "Porto Saúde",
    "bronze brasil i": "Tradicional", "prata mais i": "Tradicional",
    "ouro mais i": "Tradicional", "ouro max i": "Tradicional",
}


def familia(nome: str) -> str:
    return FAMILIA.get(norm(nome), "Outros")


@dataclass
class Pedido:
    linha: int
    id: str
    cnpj: str
    vidas: dict[str, int]
    idades: dict[str, list[int]]
    planos: list[PlanoAlvo]
    seguro_novo: bool = False
    congenere: str | None = None
    congenere_digitada: str | None = None
    coparticipacao: str = "com"          # "com" (30%) | "sem" (0%) | "as_duas"
    acomodacao: str = "Apartamento"
    comissao: str = COMISSAO_K001
    aceitar_agenciamento: bool = True
    apelido: str = ""
    pasta_destino: str | None = None
    observacao: str = ""
    extra: dict = field(default_factory=dict)

    def congeneres_para_tentar(self) -> list[str]:
        nomes = []
        for nome in (self.congenere_digitada, self.congenere):
            if nome and norm(nome) not in {norm(x) for x in nomes}:
                nomes.append(nome)
        return nomes

    @property
    def total_vidas(self) -> int:
        return sum(self.vidas.values())

    @property
    def versoes_copart(self) -> list[str]:
        return ["com", "sem"] if self.coparticipacao == "as_duas" else [self.coparticipacao]

    def na_versao(self, copart: str) -> "Pedido":
        return self if copart == self.coparticipacao else replace(self, coparticipacao=copart)

    def _vidas_texto(self) -> str:
        return ",".join(f"{r}={q}" for r, q in self.vidas.items() if q)

    def _idades_texto(self) -> str:
        return ",".join(f"{r}={sorted(v)}" for r, v in sorted(self.idades.items()) if v)

    def assinatura(self) -> str:
        """Parâmetros que mudam o preço. Plano e acomodação entram na chave do registro, ao lado."""
        anterior = "novo" if self.seguro_novo else norm(self.congenere or "")
        return "|".join([
            self.cnpj, self._vidas_texto(), self._idades_texto(), anterior,
            "comissao=" + norm(self.comissao), "copart=" + self.coparticipacao,
            "acomod=" + norm(self.acomodacao), "med=nao", "remissao=nao",
        ])
