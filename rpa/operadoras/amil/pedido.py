"""Pedido de cotação da Amil (vendasmil, Cotação PME).

Um pedido (empresa) vira UMA oportunidade (OPP-...) no portal; cada plano vira UMA cotação (COT-...) dentro
dela. Por isso há duas assinaturas (a chave do registro anti-reemissão, nucleo.estado):
- a da oportunidade: o CNPJ (e se há coligação);
- a da cotação: a da oportunidade + a distribuição de vidas, o corretor, o supervisor e o dental (o plano entra na
  chave do registro, ao lado). É a "mesma cotação": mesma empresa, mesmas vidas, mesmo plano.
O apelido (nome curto da empresa) só entra no nome do PDF e NUNCA nas assinaturas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from nucleo.modelo import PlanoAlvo
from nucleo.texto import norm

COLIGACOES = {"nao": "Não", "sim": "Sim"}
# Os planos que a tela oferece antes de o robô ler a lista do portal (nomes como aparecem no vídeo e na lista).
# A "acomodação" da tela é só a família do plano (o portal não tem acomodação separada).
PLANOS_CONHECIDOS = [
    "BRONZE SP COPART", "BRONZE SP MAIS QC COPART", "BRONZE SP MAIS QP COPART",
    "PRATA QC COPART", "PRATA QP COPART", "PRATA II QC COPART", "PRATA II QP COPART",
    "OURO QC R COPART", "OURO QP R COPART", "OURO II QP R COPART",
    "PLATINUM R1 COPART", "PLATINUM R2 COPART",
    "AMIL BLACK I R1 COPART", "AMIL BLACK I R2 COPART", "AMIL BLACK I R3 COPART",
    "AMIL BLACK II R1 COPART", "AMIL BLACK II R2 COPART", "AMIL BLACK II R3 COPART",
    "AMIL S2500 R1 QP COPART", "AMIL S2500 R2 QP COPART",
    "AMIL S6500 BLACK R1 QP COPART", "AMIL S6500 BLACK R2 QP COPART", "AMIL S6500 BLACK R3 QP COPART",
]


def familia(nome: str) -> str:
    """O grupo do plano na tela (BRONZE, PRATA, OURO, PLATINUM, BLACK, S2500...). Só para organizar a lista."""
    n = norm(nome)
    for chave, rotulo in (("bronze", "Bronze"), ("prata", "Prata"), ("ouro", "Ouro"), ("platinum", "Platinum"),
                          ("s6500", "S6500"), ("s2500", "S2500"), ("s750", "S750"), ("s450", "S450"),
                          ("s380", "S380"), ("black", "Black")):
        if chave in n:
            return rotulo
    return "Outros"


@dataclass
class Pedido:
    linha: int
    id: str
    cnpj: str
    vidas: dict[str, int]            # rótulo da faixa (núcleo) -> quantidade
    planos: list[PlanoAlvo]          # "PLATINUM R1 COPART" (sem acomodação: o nome já traz tudo)
    coligacao: str = "Não"           # "Não" | "Sim"
    corretor: str = ""               # como aparece na lista do Vínculo de Vendas
    supervisor: str = ""             # vazio = nenhum
    dental: bool = True              # aderir ao dental que o portal oferece (DENTAL BRONZE PJ PROMO no vídeo)
    apelido: str = ""                # nome curto da empresa, só para o nome do PDF
    pasta_destino: str | None = None
    observacao: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def total_vidas(self) -> int:
        return sum(self.vidas.values())

    def _vidas_texto(self) -> str:
        return ",".join(f"{r}={q}" for r, q in self.vidas.items() if q)

    def assinatura_oportunidade(self) -> str:
        """A chave de registro da oportunidade: a empresa. Os planos, as vidas e o corretor são das cotações."""
        return f"{self.cnpj}|coligacao={norm(self.coligacao)}"

    def assinatura(self) -> str:
        """A cotação: a empresa + vidas + corretor + supervisor + dental. Com o plano (na chave), é "a mesma cotação"."""
        return "|".join([self.assinatura_oportunidade(), self._vidas_texto(), "corretor=" + norm(self.corretor),
                         "supervisor=" + norm(self.supervisor), "dental=" + ("sim" if self.dental else "nao")])


@dataclass
class Oportunidade:
    """A oportunidade do pedido no registro anti-reemissão: a chave usa assinatura_oportunidade()."""
    pedido: Pedido

    @property
    def id(self) -> str:
        return self.pedido.id

    @property
    def cnpj(self) -> str:
        return self.pedido.cnpj

    def assinatura(self) -> str:
        return "oportunidade|" + self.pedido.assinatura_oportunidade()


NOME_OPORTUNIDADE = "Oportunidade"   # o "plano" do item da oportunidade no registro (aparece em Pendências)
