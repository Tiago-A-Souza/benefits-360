"""Validação dos pedidos da Porto (tela e planilha) e a planilha modelo.

CNPJ, vidas, idades 0–18, plano anterior e planos vêm do pedido. Comissão, acomodação e
coparticipação vêm da engrenagem (podem mudar numa cotação só).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from nucleo.modelo import FAIXAS, LIMITES_POR_ROTULO, PlanoAlvo
from nucleo.texto import cnpj_valido, norm, so_digitos

from .pedido import ACOMODACOES, COMISSAO_K001, COPARTS, Pedido

MIN_VIDAS, MAX_VIDAS = 3, 29
OBRIGATORIAS = ["cnpj"] + [f"vidas_{f[0]}" for f in FAIXAS]
OPCIONAIS = ["id", "apelido", "seguro_novo", "congenere_atual", "coparticipacao", "acomodacao",
             "planos", "pasta_destino", "observacao", "status"] + [f"idades_{f[0]}" for f in FAIXAS]
CONHECIDAS = set(OBRIGATORIAS) | set(OPCIONAIS)


class ErroPedido(ValueError):
    def __init__(self, problemas: list[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


@dataclass
class ErroLinha:
    linha: int
    id: str
    mensagem: str


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _cnpj(valor) -> str:
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return str(int(valor)).zfill(14)
    return so_digitos(valor)


def _inteiro(valor, campo: str) -> int:
    t = _texto(valor)
    if t == "":
        return 0
    try:
        n = float(t.replace(",", "."))
    except ValueError:
        raise ValueError(f"{campo}: '{valor}' não é número")
    if not n.is_integer() or n < 0:
        raise ValueError(f"{campo}: '{valor}' precisa ser inteiro >= 0")
    return int(n)


def _sim_nao(valor, padrao: bool, campo: str) -> bool:
    t = norm(_texto(valor))
    if not t:
        return padrao
    if t in ("sim", "s", "true", "1"):
        return True
    if t in ("nao", "n", "false", "0"):
        return False
    raise ValueError(f"{campo} '{_texto(valor)}' inválido (use sim ou nao)")


def _idades(valor, campo: str) -> list[int]:
    t = _texto(valor)
    if t == "":
        return []
    partes = [p for p in re.split(r"[;,\s]+", t) if p]
    idades = []
    for p in partes:
        if not p.isdigit():
            raise ValueError(f"{campo}: '{p}' não é idade válida (use números separados por ;)")
        idades.append(int(p))
    return idades


def _planos(texto: str, acomodacao: str) -> list[PlanoAlvo]:
    alvos, vistos = [], set()
    for item in [p.strip() for p in texto.split(";") if p.strip()]:
        nome, _, extra = item.partition("|")
        nome = " ".join(nome.split())
        aco = " ".join(extra.split()) or acomodacao
        chave = (norm(nome), norm(aco))
        if nome and chave not in vistos:
            vistos.add(chave)
            alvos.append(PlanoAlvo(nome=nome, acomodacao=aco))
    return alvos


def _copart(valor, padrao: str) -> str:
    t = norm(_texto(valor) or padrao)
    if t in ("com", "30", "30%"):
        return "com"
    if t in ("sem", "0", "0%"):
        return "sem"
    if t in ("as_duas", "com e sem", "comesem"):
        return "as_duas"
    raise ValueError(f"coparticipacao '{_texto(valor)}' inválida (use com, sem ou as_duas)")


def _acomodacao(valor, padrao: str) -> str:
    t = norm(_texto(valor) or padrao)
    for a in ACOMODACOES:
        if t == norm(a):
            return a
    raise ValueError(f"acomodacao '{_texto(valor)}' inválida (use Apartamento ou Enfermaria)")


def _de_para(nome: str, cfg: dict) -> str:
    pares = cfg.get("congeneres_de_para") or {}
    for origem, destino in pares.items():
        if norm(origem) == norm(nome):
            return str(destino)
    return nome


def montar_pedido(registro: dict, n: int, cfg: dict) -> Pedido:
    padroes = cfg.get("padroes", {})
    pid = _texto(registro.get("id")) or f"L{n}"
    problemas: list[str] = []
    try:
        cnpj = _cnpj(registro.get("cnpj"))
        if not cnpj_valido(cnpj):
            problemas.append(f"CNPJ '{_texto(registro.get('cnpj'))}' inválido (dígito verificador)")

        vidas, idades = {}, {}
        for chave, rotulo, _, _ in FAIXAS:
            try:
                vidas[rotulo] = _inteiro(registro.get(f"vidas_{chave}"), f"vidas_{chave}")
            except ValueError as e:
                problemas.append(str(e))
                vidas[rotulo] = 0
            try:
                lista = _idades(registro.get(f"idades_{chave}"), f"idades_{chave}")
            except ValueError as e:
                problemas.append(str(e))
                lista = []
            if lista:
                lo, hi = LIMITES_POR_ROTULO[rotulo]
                fora = [i for i in lista if not (lo <= i <= hi)]
                if fora:
                    problemas.append(f"idades_{chave}: {fora} fora da faixa {rotulo}")
                if len(lista) != vidas[rotulo]:
                    problemas.append(
                        f"idades_{chave}: {len(lista)} idade(s) informada(s) para {vidas[rotulo]} vida(s) na faixa")
            elif rotulo == "0 - 18" and vidas[rotulo]:
                problemas.append(
                    f"idades_0_18: informe a idade exata de cada vida na faixa 0 - 18 (o portal pede uma caixa por idade)")
            idades[rotulo] = lista

        total = sum(vidas.values())
        if not (MIN_VIDAS <= total <= MAX_VIDAS):
            problemas.append(f"total de vidas {total} fora do intervalo {MIN_VIDAS} a {MAX_VIDAS} do PME da Porto")

        try:
            seguro_novo = _sim_nao(registro.get("seguro_novo"), False, "seguro_novo")
        except ValueError as e:
            problemas.append(str(e))
            seguro_novo = False
        digitada = _texto(registro.get("congenere_atual"))
        congenere = None if seguro_novo else (_de_para(digitada, cfg) if digitada else None)
        if not seguro_novo and not congenere:
            problemas.append("informe a operadora atual (congenere_atual) ou marque seguro novo")

        try:
            copart = _copart(registro.get("coparticipacao"), str(padroes.get("coparticipacao", "com")))
        except ValueError as e:
            problemas.append(str(e))
            copart = "com"
        if copart not in COPARTS:
            problemas.append("coparticipacao inválida")

        try:
            acomodacao = _acomodacao(registro.get("acomodacao"), str(padroes.get("acomodacao", "Apartamento")))
        except ValueError as e:
            problemas.append(str(e))
            acomodacao = "Apartamento"

        texto_planos = _texto(registro.get("planos")) or "; ".join(padroes.get("planos") or [])
        planos = _planos(texto_planos, acomodacao)
        if not planos:
            problemas.append("planos vazio: informe o nome exato da grade da Porto, ex.: Ouro Mais I; P470")

        comissao = _texto(padroes.get("comissao")) or COMISSAO_K001
        pasta = _texto(registro.get("pasta_destino")) or None
        if pasta and not Path(pasta).is_dir():
            problemas.append(f"pasta_destino não existe ou não está acessível: {pasta}")
    except ValueError as e:
        problemas.append(str(e))
    if problemas:
        raise ErroPedido(problemas)
    return Pedido(
        linha=n, id=pid, cnpj=cnpj, vidas=vidas, idades=idades, planos=planos, seguro_novo=seguro_novo,
        congenere=congenere, congenere_digitada=digitada or None, coparticipacao=copart,
        acomodacao=acomodacao, comissao=comissao, apelido=_texto(registro.get("apelido")),
        pasta_destino=pasta, observacao=_texto(registro.get("observacao")))


def _nome_coluna(valor) -> str:
    return norm(str(valor or "")).replace(" ", "_").replace("-", "_")


def ler_registros(caminho: str | Path) -> list[tuple[int, dict]]:
    wb = load_workbook(caminho, data_only=True, read_only=True)
    linhas = list(wb.worksheets[0].iter_rows(values_only=True))
    wb.close()
    if not linhas:
        raise ValueError("planilha vazia")
    cabecalho = [_nome_coluna(c) for c in linhas[0]]
    desconhecidas = [str(linhas[0][i]) for i, c in enumerate(cabecalho) if c and c not in CONHECIDAS]
    if desconhecidas:
        raise ValueError("colunas não reconhecidas: " + ", ".join(desconhecidas)
                         + ". Use os nomes da planilha modelo da Porto")
    faltando = [c for c in OBRIGATORIAS if c not in cabecalho]
    if faltando:
        raise ValueError("colunas obrigatórias ausentes na planilha: " + ", ".join(faltando))
    registros = []
    for n, valores in enumerate(linhas[1:], start=2):
        registro = {cabecalho[i]: v for i, v in enumerate(valores) if i < len(cabecalho) and cabecalho[i]}
        if all(_texto(v) == "" for v in registro.values()):
            continue
        registros.append((n, registro))
    return registros


def ler_planilha(caminho: str | Path, cfg: dict) -> tuple[list[Pedido], list[ErroLinha]]:
    pedidos, erros, vistos = [], [], set()
    for n, registro in ler_registros(caminho):
        pid = _texto(registro.get("id")) or f"L{n}"
        try:
            pedido = montar_pedido(registro, n, cfg)
            if pid in vistos:
                raise ErroPedido([f"id '{pid}' repetido na planilha"])
        except ErroPedido as e:
            erros.append(ErroLinha(n, pid, str(e)))
            vistos.add(pid)
            continue
        vistos.add(pid)
        pedidos.append(pedido)
    return pedidos, erros


def criar_modelo(caminho: str | Path) -> None:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "cotacoes"
    colunas = ["id", "cnpj", "apelido", "seguro_novo", "congenere_atual"] + [f"vidas_{f[0]}" for f in FAIXAS] + [
        "idades_0_18", "idades_59_mais", "planos", "pasta_destino", "observacao"]
    ws.append(colunas)
    exemplo = {"id": "EX-001", "cnpj": "11.222.333/0001-81", "apelido": "PADARIA", "seguro_novo": "nao",
               "congenere_atual": "NOTREDAME", "vidas_0_18": 1, "vidas_34_38": 2, "vidas_59_mais": 1,
               "idades_0_18": "0", "idades_59_mais": "60",
               "planos": "Ouro Mais I; P470",
               "observacao": "exemplo fictício; troque pelo CNPJ real"}
    ws.append([exemplo.get(c, 0 if c.startswith("vidas_") else "") for c in colunas])
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="00A651")
    ajuda = wb.create_sheet("como_preencher")
    for linha in [
        ("coluna", "o que colocar"),
        ("cnpj", "com ou sem máscara; formate a coluna como Texto"),
        ("apelido", "nome curto da empresa para o PDF (PORTO OURO MAIS I PADARIA.pdf)"),
        ("seguro_novo", "sim = a empresa não tem plano hoje; nao = informe congenere_atual"),
        ("congenere_atual", "como a Newport escreve; o robô troca pelo nome da lista da Porto (de-para na engrenagem)"),
        ("vidas_*", f"quantidade em cada faixa; total de {MIN_VIDAS} a {MAX_VIDAS}"),
        ("idades_0_18", "idade exata de cada vida 0–18, separadas por ';' (ex.: 0; 7). Obrigatório se houver vidas nessa faixa"),
        ("planos", "nome exato da grade da Porto, separados por ';'. Cada plano vira uma cotação e um PDF "
                   "(sempre Criar nova cotação, nunca Duplicar)"),
        ("pasta_destino", "pasta do cliente; vazio = o PDF fica só na pasta do robô"),
    ]:
        ajuda.append(linha)
    wb.save(caminho)
