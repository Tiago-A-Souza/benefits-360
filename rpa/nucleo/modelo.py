"""Tipos e constantes comuns a todas as operadoras (faixas ANS, planos, resultados)."""
from __future__ import annotations

from dataclasses import dataclass, field

from .texto import norm

# As 10 faixas etárias da ANS (RN 63/2003), com o rótulo usado nas telas.
FAIXAS = [
    # chave na planilha, rótulo na tela, idade mínima, idade máxima
    ("0_18", "0 - 18", 0, 18),
    ("19_23", "19 - 23", 19, 23),
    ("24_28", "24 - 28", 24, 28),
    ("29_33", "29 - 33", 29, 33),
    ("34_38", "34 - 38", 34, 38),
    ("39_43", "39 - 43", 39, 43),
    ("44_48", "44 - 48", 44, 48),
    ("49_53", "49 - 53", 49, 53),
    ("54_58", "54 - 58", 54, 58),
    ("59_mais", "59+", 59, 130),
]
ROTULOS = [f[1] for f in FAIXAS]
CHAVE_POR_ROTULO = {f[1]: f[0] for f in FAIXAS}
ROTULO_POR_CHAVE = {f[0]: f[1] for f in FAIXAS}
LIMITES_POR_ROTULO = {f[1]: (f[2], f[3]) for f in FAIXAS}

ACOMODACOES = {"enfermaria": "Enfermaria", "apartamento": "Apartamento"}


@dataclass(frozen=True)
class PlanoAlvo:
    nome: str
    acomodacao: str | None = None  # "Enfermaria" / "Apartamento" / None (se o nome for único)
    # Versão da cotação deste plano quando o pedido pede mais de uma do mesmo plano (a operadora define: código
    # e texto). Vazio = a do pedido. Não entra em rotulo() (que é o nome do plano, gravado no registro).
    versao: str = ""
    versao_texto: str = ""

    def rotulo(self) -> str:
        return f"{self.nome} | {self.acomodacao}" if self.acomodacao else self.nome

    def rotulo_completo(self) -> str:
        """Para o log e a tela: o plano e, se houver, o texto da versão ("Plano | Acomodação | versão")."""
        return self.rotulo() + (f" | {self.versao_texto or self.versao}" if self.versao else "")

    def casa_com(self, nome: str, acomodacao: str | None) -> bool:
        if norm(nome) != norm(self.nome):
            return False
        if self.acomodacao is None:
            return True
        return norm(acomodacao) == norm(self.acomodacao)


@dataclass
class PlanoVisto:
    """Um plano visto na lista do portal (para a aba de preços e o catálogo da tela). O card de cada portal é
    da operadora; ela entrega isto."""
    nome: str
    acomodacao: str
    preco: object           # Decimal
    pagina: int = 1
    descricao: str = ""     # o que o card diz além do nome (produto, contratação, vigência...)
    versao: str = ""        # texto da versão que o card mostra


@dataclass
class ResultadoPlano:
    pedido_id: str
    linha: int
    cnpj: str
    plano: str
    acomodacao: str = ""
    razao_social: str = ""
    status: str = ""                 # OK | ENSAIO_OK | ERRO | PULADO | VERIFICAR
    protocolo: str = ""
    preco_mensal: object = None      # Decimal do card
    total_sem_iof: object = None
    iof: object = None
    total_com_iof: object = None
    valores_por_vida: dict = field(default_factory=dict)  # rótulo -> Decimal
    pdf_arquivo: str = ""
    pdf_destino: str = ""
    pdf_nome: str = ""          # nome "de corretor" do PDF (SULAMERICA <PLANO>.pdf), usado também no download da tela
    versao: str = ""            # a versão desta cotação (código da operadora); a tela agrupa as do mesmo plano
    erro: str = ""
    etapa_erro: str = ""
