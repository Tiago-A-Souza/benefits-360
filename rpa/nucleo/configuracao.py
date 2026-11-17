"""Configuração do robô feita pelo corretor na tela (Robôs > <operadora>).

Cada operadora declara, tela por tela do portal, os campos que o corretor pode mudar
(Operadora.configuracao). Este módulo lê o valor atual, valida o que vem da tela e grava os
ajustes em saida/config_tela.json, por cima do config.yaml. Só os campos declarados podem ser
gravados: a tela nunca muda URL, pasta de saída, conferências ou tempos que não estejam na lista.

Tipos de campo:
  sim_nao   "sim" | "nao"  (com "booleano": True grava true/false)
  escolha   uma das "opcoes" [[valor, texto], ...]  (com "inteiro": True grava número)
  texto     texto curto  (com "validar": "nome_pdf" confere o modelo do nome do PDF)
  numero    inteiro entre "minimo" e "maximo"
  faixas    lista de faixas etárias da ANS ("0 - 18", ..., "59+")
  planos    lista de planos "Nome | Acomodação"
  pares     de-para {texto: texto}
  info      só explica (sem valor)
"""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path

from .modelo import ACOMODACOES, ROTULOS
from .texto import norm

# Na configuração "plana" que o robô usa, tempos viram execucao e arquivos viram saida.
_SECAO_PLANA = {"tempos": "execucao", "arquivos": "saida"}


def aprendido(pasta_operadora) -> dict:
    """O que o robô aprendeu do portal (saida/<op>/portal.json), ex.: {"senha_max": 16}."""
    try:
        return json.loads((Path(pasta_operadora) / "portal.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def aprender(pasta_operadora, chave: str, valor) -> None:
    """Grava um fato do portal (nunca credenciais), de forma atômica."""
    pasta = Path(pasta_operadora)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = aprendido(pasta)
    dados[chave] = valor
    tmp = pasta / f"portal.json.{os.getpid()}.tmp"
    tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, pasta / "portal.json")


def ler(cfg_plano: dict, chave: str):
    """Valor atual de um campo na configuração plana da operadora (op.config(total))."""
    partes = chave.split(".")
    partes[0] = _SECAO_PLANA.get(partes[0], partes[0])
    valor = cfg_plano
    for p in partes:
        if not isinstance(valor, dict) or p not in valor:
            return None
        valor = valor[p]
    return copy.deepcopy(valor)


def gravar(secao_operadora: dict, chave: str, valor) -> None:
    """Grava o valor nos ajustes da tela, na seção operadoras.<id> (mesma estrutura do config.yaml)."""
    partes = chave.split(".")
    alvo = secao_operadora
    for p in partes[:-1]:
        alvo = alvo.setdefault(p, {})
    alvo[partes[-1]] = valor


def para_tela(campo: dict, valor):
    """Valor da configuração no formato que a tela mostra."""
    tipo = campo.get("tipo")
    if tipo == "sim_nao":
        if isinstance(valor, bool):
            return "sim" if valor else "nao"
        return "sim" if norm(str(valor or "")) in ("sim", "s", "true", "1") else "nao"
    if tipo == "escolha":
        return "" if valor is None else str(valor)
    if tipo in ("faixas", "planos"):
        return list(valor or [])
    if tipo == "pares":
        return dict(valor or {})
    if tipo == "numero":
        return int(valor) if valor not in (None, "") else None
    if tipo == "texto":
        return "" if valor is None else str(valor)
    return valor


def problema_no_nome_pdf(modelo) -> str:
    """Confere o modelo do nome do PDF. Devolve o problema ou vazio."""
    modelo = str(modelo or "").strip()
    if not modelo.lower().endswith(".pdf"):
        return "o nome do PDF precisa terminar em .pdf"
    if "{plano" not in modelo:
        return "o nome do PDF precisa ter {plano_arquivo}, senão um plano substitui o PDF do outro"
    try:
        modelo.format(cnpj="1", protocolo="2", plano="P", plano_arquivo="P", acomodacao="A", versao="V")
    except (KeyError, IndexError, ValueError) as e:
        return (f"o nome do PDF tem um campo que não existe ({e}); use {{plano_arquivo}}, {{versao}}, "
                "{protocolo} ou {cnpj}")
    return ""


def validar(campo: dict, valor):
    """Valor vindo da tela -> valor para gravar. ValueError com a frase para o corretor."""
    tipo = campo.get("tipo")
    if tipo == "sim_nao":
        if valor not in ("sim", "nao"):
            raise ValueError("escolha sim ou não")
        return (valor == "sim") if campo.get("booleano") else valor
    if tipo == "escolha":
        validos = [str(o[0]) for o in campo.get("opcoes") or []]
        if str(valor) not in validos:
            raise ValueError("escolha uma das opções da lista")
        return int(valor) if campo.get("inteiro") else str(valor)
    if tipo == "texto":
        if not isinstance(valor, str) or len(valor) > 150:
            raise ValueError("texto inválido (até 150 letras)")
        valor = valor.strip()
        if campo.get("validar") == "nome_pdf":
            problema = problema_no_nome_pdf(valor)
            if problema:
                raise ValueError(problema)
        return valor
    if tipo == "numero":
        try:
            n = int(valor)
        except (TypeError, ValueError):
            raise ValueError("use um número inteiro")
        if not (campo.get("minimo", n) <= n <= campo.get("maximo", n)):
            raise ValueError(f"use um número de {campo.get('minimo')} a {campo.get('maximo')}")
        return n
    if tipo == "faixas":
        if not isinstance(valor, list) or any(v not in ROTULOS for v in valor):
            raise ValueError("faixa etária inválida")
        return [r for r in ROTULOS if r in valor]
    if tipo == "planos":
        if not isinstance(valor, list):
            raise ValueError("lista de planos inválida")
        limpos = []
        for item in valor:
            if not isinstance(item, str) or " | " not in item:
                raise ValueError(f"plano '{item}' sem acomodação (use Nome | Acomodação)")
            nome, acomod = [x.strip() for x in item.split(" | ", 1)]
            if not nome or norm(acomod) not in ACOMODACOES:
                raise ValueError(f"plano '{item}' com acomodação inválida")
            rotulo = f"{nome} | {ACOMODACOES[norm(acomod)]}"
            if rotulo not in limpos:
                limpos.append(rotulo)
        return limpos
    if tipo == "pares":
        if not isinstance(valor, dict):
            raise ValueError("lista inválida")
        limpo = {}
        for k, v in valor.items():
            if not isinstance(k, str) or not isinstance(v, str):
                raise ValueError("lista inválida")
            if k.strip() and v.strip():
                limpo[k.strip()] = v.strip()
        return limpo
    raise ValueError("este campo não pode ser mudado")


def campos_por_chave(telas: list[dict]) -> dict[str, dict]:
    return {c["chave"]: c for t in telas for c in t.get("campos", []) if c.get("chave")}
