"""Pedido de cotação da Bradesco (Cotação SPG, Saúde PME de 3 a 29 vidas).

Um pedido (empresa) vira UM processo no portal ("Gerar processo"); cada plano × versão (com/sem coparticipação)
é um cálculo dentro desse processo. Por isso há duas assinaturas:
- a do processo (o que o "Gerar processo" leva): CNPJ, grupo, vidas e idades, contrato, corretora, comissionamento;
- a do cálculo: a do processo + coparticipação e dental (o plano e a acomodação entram na chave do registro).
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

from nucleo.modelo import PlanoAlvo
from nucleo.texto import norm

ADESOES = {"compulsoria": "Compulsória", "opcional": "Opcional"}
COBERTURAS = {"top": "Top", "hospitalar": "Hospitalar"}
DENTAL_ANTIGO = "Padrão Doc 1"   # o dental de todos os processos gravados antes da chave levar o dental
DENTAIS = ["Sem plano dental", "Padrão Doc 1", "Padrão Doc White", "Premium Top 1"]
COMISSOES = {"nenhum": "", "2,5": "2,5%", "5": "5%", "7,5": "7,5%", "10": "10%"}
PAPEIS = {"corretor": "Corretor", "produtor": "Produtor", "angariador": "Angariador"}
CATEGORIAS = ["Sócios e Diretores", "Funcionários", "Estagiários", "Administradores", "Sócios, Diretores e Funcionários"]
ACOMODACOES = {"quarto": "Quarto", "enfermaria": "Enfermaria"}


@dataclass
class Pedido:
    linha: int
    id: str
    cnpj: str
    vidas: dict[str, int]            # rótulo da faixa (núcleo) -> quantidade
    idades: dict[str, list[int]]     # "0 - 18" e "59+": a idade de cada vida (0 = menor de 1 ano)
    planos: list[PlanoAlvo]          # "Nacional Plus 4x | Quarto"
    coparticipacao: str              # "com" | "sem" | "as_duas"
    dental: str                      # "Padrão Doc 1" ...
    adesao: str                      # "Compulsória" | "Opcional"
    cobertura: str                   # "Top" | "Hospitalar"
    categoria: str = "Sócios e Diretores"
    mais_de_um_titular: bool = False
    desconto_folha: bool = False
    desconto_comissao: str = ""      # "" | "2,5%" | "5%" | "7,5%" | "10%"
    sucursal: str = "978"
    codigo_corretor: str = "438451"
    angariacao: str = "3 Primeiras Parcelas 100%"
    corretagem: str = "2% vitalício a partir da 4ª parcela"
    email_corretora: str = ""
    celular_corretora: str = ""
    intermediario_papel: str = "Corretor"
    intermediario_email: str = ""
    intermediario_celular: str = ""
    transferencia: bool = False
    ramo: str = "OUTROS"
    pasta_destino: str | None = None
    observacao: str = ""
    criterio_quantidade: int | None = None
    extra: dict = field(default_factory=dict)

    @property
    def total_vidas(self) -> int:
        return sum(self.vidas.values())

    @property
    def versoes_copart(self) -> list[str]:
        """"as_duas" vira dois cálculos por plano, nesta ordem: com e sem coparticipação."""
        return ["com", "sem"] if self.coparticipacao == "as_duas" else [self.coparticipacao]

    def na_versao(self, copart: str) -> "Pedido":
        """O mesmo pedido com uma coparticipação só: é o cálculo real (chave do registro, conferências)."""
        return self if copart == self.coparticipacao else replace(self, coparticipacao=copart)

    def _base_do_processo(self) -> str:
        vidas = ",".join(f"{r}={q}" for r, q in self.vidas.items() if q)
        idades = ",".join(f"{r}={sorted(v)}" for r, v in sorted(self.idades.items()) if v)
        return "|".join([
            self.cnpj, norm(self.categoria), vidas, idades, norm(self.adesao), norm(self.cobertura),
            "titulares" if self.mais_de_um_titular else "1titular", "folha" if self.desconto_folha else "semfolha",
            "comissao=" + (self.desconto_comissao or "0"), "suc=" + self.sucursal, "cor=" + self.codigo_corretor,
            "ang=" + norm(self.angariacao), "corr=" + norm(self.corretagem),
            "transf" if self.transferencia else "semtransf", "ramo=" + norm(self.ramo),
        ])

    def assinatura_processo(self) -> str:
        """A CHAVE DE REGISTRO do processo (nucleo.estado). Mesma assinatura (com o CNPJ) = o mesmo processo: não gera outro.
        O dental entra só quando não é o "Padrão Doc 1": as chaves gravadas antes (todas com o Padrão Doc 1) continuam
        valendo. É só a chave do registro: o dental do pedido não é "o dental do processo" no portal, onde o robô escolhe
        o dental no Resultado (padrão do vídeo: "Sem plano dental"). Como o robô ainda não reabre um processo para
        acrescentar cálculo, um pedido com outro dental (outro preço) precisa de um processo novo, sem travar."""
        base = self._base_do_processo()
        if norm(self.dental) == norm(DENTAL_ANTIGO):
            return base
        return base + "|dentalproc=" + norm(self.dental)

    def assinatura(self) -> str:
        """O cálculo: o processo + coparticipação e dental. Com plano e acomodação (na chave), é "o mesmo cálculo".
        Não repete o dental da chave do processo: a chave do cálculo continua como foi gravada."""
        return "|".join([self._base_do_processo(), "copart=" + self.coparticipacao, "dental=" + norm(self.dental)])


@dataclass
class Processo:
    """O processo do pedido no registro anti-reemissão (nucleo.estado): a chave usa assinatura_processo()."""
    pedido: Pedido

    @property
    def id(self) -> str:
        return self.pedido.id

    @property
    def cnpj(self) -> str:
        return self.pedido.cnpj

    def assinatura(self) -> str:
        return "processo|" + self.pedido.assinatura_processo()


NOME_PROCESSO = "Processo"     # o "plano" do item do processo no registro (aparece em Pendências)
