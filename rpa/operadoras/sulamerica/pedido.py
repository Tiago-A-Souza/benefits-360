"""Pedido de cotação da SulAmérica (Cotação PME, 3 a 29 vidas)."""
from __future__ import annotations

from dataclasses import dataclass, replace

from nucleo.modelo import PlanoAlvo
from nucleo.texto import norm

TIPOS_CONTRATACAO = {"compulsoria": "Compulsória", "cbo": "CBO", "flex": "Flex"}
PRODUTO_DO_VIDEO = "557 - AHO"   # o único produto visto no vídeo; as chaves já gravadas não o incluem


@dataclass
class Pedido:
    linha: int                       # linha na planilha (para mensagens)
    id: str                          # identificador do pedido (coluna id, ou L<linha>)
    cnpj: str                        # só dígitos
    vendedor: str | None
    cuidado_360: bool
    seguro_novo: bool
    congenere: str | None            # nome como aparece na lista do portal
    tipo_contratacao: str            # "Compulsória" | "CBO" | "Flex"
    vigencia_meses: int              # 12 | 24
    coparticipacao: str              # "com" | "sem" | "as_duas" (duas cotações por plano: com e sem)
    vidas: dict[str, int]            # rótulo da faixa -> quantidade
    idades: dict[str, list[int]]     # rótulo da faixa -> idades exatas (pode faltar)
    planos: list[PlanoAlvo]          # planos pedidos (vazio quando criterio_quantidade está definido)
    pasta_destino: str | None = None
    observacao: str = ""
    criterio_quantidade: int | None = None   # planos = "menor_preco[:N]" na planilha
    produto: str = PRODUTO_DO_VIDEO          # filtro "Produto Saúde PME" (configuração do robô)
    # A operadora atual como o corretor digitou (a "congenere" é a do de-para, que entra na chave do registro).
    # No portal o robô tenta primeiro esta, depois a do de-para.
    congenere_digitada: str | None = None

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
        """"as_duas" vira duas cotações por plano, nesta ordem: com e sem coparticipação."""
        return ["com", "sem"] if self.coparticipacao == "as_duas" else [self.coparticipacao]

    def na_versao(self, copart: str) -> "Pedido":
        """O mesmo pedido com uma coparticipação só: é a cotação real (chave do registro, filtros, conferências).
        A versão "com" de um pedido "as_duas" tem a mesma chave de um pedido "com": o que já saiu não sai de novo."""
        return self if copart == self.coparticipacao else replace(self, coparticipacao=copart)

    def assinatura(self) -> str:
        """Parâmetros que mudam o preço. Junto com CNPJ e plano, define 'a mesma cotação'."""
        vidas = ",".join(f"{r}={q}" for r, q in self.vidas.items() if q)
        idades = ",".join(f"{r}={sorted(v)}" for r, v in sorted(self.idades.items()) if v)
        partes = [
            self.cnpj, self.tipo_contratacao, str(self.vigencia_meses), self.coparticipacao,
            "c360" if self.cuidado_360 else "sem360",
            "novo" if self.seguro_novo else norm(self.congenere or ""), vidas, idades,
        ]
        # Outro produto é outra cotação. O 557 - AHO fica de fora para as chaves já gravadas continuarem valendo.
        if norm(self.produto or "") not in ("", norm(PRODUTO_DO_VIDEO)):
            partes.append("produto=" + norm(self.produto))
        return "|".join(partes)
