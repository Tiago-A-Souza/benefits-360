"""Configuração (config.yaml com várias operadoras) e log."""
from __future__ import annotations

import copy
import json
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

from .credenciais import FiltroSegredos

GERAL_PADRAO = {
    "pasta_saida": "saida",
    "modo_visual": False,      # janela do portal visível (só para calibrar; o login é automático)
    "janela_escondida": "headless",   # "headless" ou "fora_da_tela" (se o portal estranhar o headless)
    "lentidao_ms": 150,
    "mapear": False,
    "pausa_entre_pedidos_s": 3,
}


def mesclar(base: dict, extra: dict | None) -> dict:
    final = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(final.get(k), dict):
            final[k] = mesclar(final[k], v)
        else:
            final[k] = copy.deepcopy(v)
    return final


# Listas que a tela grava inteiras: apagar uma linha nos Ajustes tem que apagar de verdade
# (mesclar dicionários manteria a linha que veio do config.yaml).
SUBSTITUIR_INTEIRO = (("congeneres_de_para",), ("arquivos", "nomes_arquivo"))


def carregar_config(caminho: str | Path, sobreposicao: dict | None = None) -> dict:
    """Lê o config.yaml. `sobreposicao` são os ajustes feitos pela tela (mesma estrutura)."""
    caminho = Path(caminho).resolve()
    with open(caminho, encoding="utf-8") as f:
        dados = yaml.safe_load(f) or {}
    if "operadoras" not in dados:
        # Formato antigo (uma operadora só, chaves soltas): vira a seção da SulAmérica.
        geral = {k: dados.get("execucao", {}).get(k) for k in GERAL_PADRAO if k in dados.get("execucao", {})}
        if "pasta" in dados.get("saida", {}):
            geral["pasta_saida"] = dados["saida"]["pasta"]
        dados = {"geral": geral, "teste": dados.get("teste", {}), "legado": True,
                 "operadoras": {"sulamerica": dados}}
    dados = mesclar(dados, sobreposicao)
    for op_id, secao in ((sobreposicao or {}).get("operadoras") or {}).items():
        for chaves in SUBSTITUIR_INTEIRO:
            valor, achou = secao, True
            for k in chaves:
                if isinstance(valor, dict) and k in valor:
                    valor = valor[k]
                else:
                    achou = False
                    break
            if achou:
                alvo = dados["operadoras"].setdefault(op_id, {})
                for k in chaves[:-1]:
                    alvo = alvo.setdefault(k, {})
                alvo[chaves[-1]] = copy.deepcopy(valor)
    dados["_pasta_config"] = str(caminho.parent)
    dados["geral"] = mesclar(GERAL_PADRAO, dados.get("geral"))
    return dados


def ajustes_da_tela(total: dict) -> dict:
    """Ajustes gravados pela tela (saida/config_tela.json), se houver."""
    try:
        return json.loads((pasta_saida(total) / "config_tela.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}


def carregar_config_com_ajustes(caminho: str | Path) -> dict:
    """config.yaml + ajustes da tela: o que a linha de comando usa, para fazer o mesmo que a tela."""
    return carregar_config(caminho, ajustes_da_tela(carregar_config(caminho)))


_ARQUIVOS_V2 = ("estado.json", "resultados.xlsx", "pdfs", "mapa", "logs", "perfil_navegador")


def migrar_legado(total: dict) -> None:
    """A v2 (uma operadora) guardava tudo direto em saida/. Na v3 a SulAmérica usa saida/sulamerica/.
    Sem mover, o registro anti-reemissão da v2 seria ignorado e cotações já emitidas sairiam de novo."""
    if total.get("legado"):
        return
    raiz = pasta_saida(total)
    antigo = raiz / "estado.json"
    if not antigo.exists():
        return
    destino = raiz / "sulamerica"
    if (destino / "estado.json").exists():
        raise RuntimeError(
            f"há dois registros de cotações: {antigo} (versão anterior) e {destino / 'estado.json'}. "
            "Junte os dois antes de continuar; sem isso, cotações já emitidas podem sair de novo.")
    destino.mkdir(parents=True, exist_ok=True)
    for nome in _ARQUIVOS_V2:
        if (raiz / nome).exists() and not (destino / nome).exists():
            shutil.move(str(raiz / nome), str(destino / nome))


def retencao_dias(total: dict) -> int:
    """Prazo de retenção dos arquivos do robô (seguranca.retencao_dias; 0 desliga)."""
    seg = total.get("seguranca") or ((total.get("operadoras") or {}).get("sulamerica") or {}).get("seguranca") or {}
    return int(seg.get("retencao_dias", 90) or 0)


def pasta_saida(total: dict) -> Path:
    pasta = Path(total["geral"]["pasta_saida"])
    if not pasta.is_absolute():
        pasta = Path(total.get("_pasta_config", ".")) / pasta
    return pasta.absolute()


def config_operadora(total: dict, op_id: str, padrao_op: dict) -> dict:
    """Monta a configuração "plana" que o robô de uma operadora usa."""
    geral = total["geral"]
    op = copy.deepcopy((total.get("operadoras") or {}).get(op_id) or {})
    legado = bool(total.get("legado"))
    execucao = {k: geral[k] for k in ("modo_visual", "janela_escondida", "lentidao_ms", "mapear",
                                      "pausa_entre_pedidos_s")}
    execucao.update(op.pop("tempos", {}) or {})
    if legado:
        execucao.update(op.pop("execucao", {}) or {})
    saida = {"pasta": str(pasta_saida(total) if legado else pasta_saida(total) / op_id)}
    saida.update(op.pop("arquivos", {}) or {})
    if legado:
        legado_saida = op.pop("saida", {}) or {}
        legado_saida.pop("pasta", None)
        saida.update(legado_saida)
    plana = {"execucao": execucao, "saida": saida, "teste": copy.deepcopy(total.get("teste") or {})}
    plana.update(op)
    return mesclar(padrao_op, plana)


def configurar_log(pasta: str | Path, extra_handler: logging.Handler | None = None,
                   nome: str = "cotacao") -> logging.Logger:
    """O log do robô em <pasta>/execucao_<data>.log. Na tela, cada operadora tem o seu ("cotacao.<operadora>"),
    para dois robôs ao mesmo tempo não misturarem as linhas."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(nome)
    logger.setLevel(logging.INFO)
    for f in list(logger.filters):
        logger.removeFilter(f)
    logger.addFilter(FiltroSegredos())   # nenhum valor de login sai no log, no evento da tela ou no tela.db
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()
    fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S")
    arq = logging.FileHandler(pasta / datetime.now().strftime("execucao_%Y%m%d_%H%M%S.log"), encoding="utf-8")
    arq.setFormatter(fmt)
    con = logging.StreamHandler(sys.stdout)
    con.setFormatter(fmt)
    logger.addHandler(arq)
    logger.addHandler(con)
    if extra_handler:
        logger.addHandler(extra_handler)
    return logger
