"""Uma operadora falsa mínima: o núcleo e a tela são testados sem nenhuma operadora de verdade.

Não abre portal nenhum. `processar` só registra um resultado por plano, depois de esperar `espera_s` (o
"portal" lento ou travado, para testar que um robô parado não segura o outro).
"""
from __future__ import annotations

import time
from dataclasses import dataclass

from nucleo.modelo import PlanoAlvo, ResultadoPlano
from nucleo.navegador import Parado
from operadoras.base import Operadora


@dataclass
class PedidoFalso:
    linha: int
    id: str
    cnpj: str
    planos: list
    espera_s: float = 0.0

    def assinatura(self) -> str:
        return self.cnpj


class SessaoFalsa:
    def __init__(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio, parar=None):
        self.cfg, self.log, self.contexto, self.page = cfg, log, contexto, page
        self.estado, self.resultados, self.mapa, self.ensaio, self.parar = estado, resultados, mapa, ensaio, parar


class OperadoraFalsa(Operadora):
    id = "falsa"
    nome = "Operadora Falsa"
    produto = "Só para testes"
    etapas = (("inicio", "Início"), ("emitida", "Emitida"))
    PADRAO_CONFIG = {"execucao": {"timeout_tela_ms": 5000}, "saida": {}, "padroes": {}}
    nome_versao_planilha = "variante"

    def configuracao(self, cfg: dict) -> list[dict]:
        return [{"etapa": "inicio", "faz": "Entra no portal falso.",
                 "campos": [{"tipo": "credenciais", "rotulo": "Login", "campos": self.campos_login()}]}]

    def planos_conhecidos(self) -> list[dict]:
        return [{"nome": "Plano A", "acomodacao": "Enfermaria"}]

    def rotulos_versao(self) -> dict[str, str]:
        return {"a": "versão A", "b": "versão B"}

    def montar_pedido(self, dados: dict, cfg: dict, linha: int = 0):
        cnpj = "".join(ch for ch in str(dados.get("cnpj") or "") if ch.isdigit())
        if len(cnpj) != 14:
            erro = ValueError("CNPJ inválido")
            erro.problemas = ["CNPJ inválido"]
            raise erro
        planos = [PlanoAlvo(p.strip()) for p in str(dados.get("planos") or "Plano A").split(";") if p.strip()]
        return PedidoFalso(linha, str(dados.get("id") or f"L{linha}"), cnpj, planos, float(dados.get("espera_s") or 0))

    def qtd_cotacoes(self, pedido) -> int:
        return len(pedido.planos)

    def nova_sessao(self, cfg, log, contexto, page, estado, resultados, mapa, ensaio: bool, avisar=None,
                    parar=None, pedir_codigo=None, reemitir=()):
        return SessaoFalsa(cfg, log, contexto, page, estado, resultados, mapa, ensaio, parar=parar)

    def login(self, sessao) -> None:
        pass

    def conectado(self, page) -> bool:
        return True

    def recuperar_pdfs(self, sessao) -> None:
        pass

    def processar(self, sessao, pedido) -> None:
        sessao.log.info(f"{pedido.id}: cotando na {self.nome}")
        fim = time.monotonic() + pedido.espera_s
        while time.monotonic() < fim:          # "portal" lento ou travado
            if sessao.parar and sessao.parar():
                raise Parado("inicio")          # Parar: na hora, inclusive com o "portal" travado
            time.sleep(0.05)
        for alvo in pedido.planos:
            sessao.resultados.plano(ResultadoPlano(
                pedido_id=pedido.id, linha=pedido.linha, cnpj=pedido.cnpj, plano=alvo.nome,
                status="ENSAIO_OK" if sessao.ensaio else "OK"))


class OutraOperadoraFalsa(OperadoraFalsa):
    """A segunda operadora falsa (para testar duas operadoras ao mesmo tempo)."""
    id = "falsa2"
    nome = "Outra Operadora Falsa"

    def campos_login(self) -> list[dict]:
        return [{"chave": "documento", "rotulo": "CPF/CNPJ", "tipo": "cpf_cnpj"},
                {"chave": "senha", "rotulo": "Senha", "tipo": "senha", "artigo": "a"}]
