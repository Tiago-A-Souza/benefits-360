"""Validação dos pedidos da Amil (tela e planilha) e a planilha modelo.

O que muda de empresa para empresa vem do pedido (CNPJ, vidas, planos, pasta, nome curto). O resto (coligação, corretor,
supervisor, dental) vem da engrenagem do robô; o dental também pode mudar numa cotação só ("Mudar só nesta cotação").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from nucleo.modelo import FAIXAS, PlanoAlvo
from nucleo.texto import cnpj_valido, norm, so_digitos

from .pedido import COLIGACOES, Pedido

MIN_VIDAS, MAX_VIDAS = 2, 29
OBRIGATORIAS = ["cnpj"] + [f"vidas_{f[0]}" for f in FAIXAS]
OPCIONAIS = ["id", "apelido", "dental", "planos", "pasta_destino", "observacao", "status"]
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
    if t in ("sim", "s", "true", "1", "aderir"):
        return True
    if t in ("nao", "n", "false", "0"):
        return False
    raise ValueError(f"{campo} '{_texto(valor)}' inválido (use sim ou nao)")


def _planos(texto: str) -> list[PlanoAlvo]:
    """"PLATINUM R1 COPART; AMIL BLACK I R1 COPART". Depois de "|" vem a família que a tela mostra: é ignorada."""
    alvos, vistos = [], set()
    for item in [p.strip() for p in texto.split(";") if p.strip()]:
        nome = " ".join(item.split("|", 1)[0].split())
        if nome and norm(nome) not in vistos:
            vistos.add(norm(nome))
            alvos.append(PlanoAlvo(nome=nome, acomodacao=None))
    return alvos


def montar_pedido(registro: dict, n: int, cfg: dict) -> Pedido:
    padroes = cfg.get("padroes", {})
    pid = _texto(registro.get("id")) or f"L{n}"
    problemas: list[str] = []
    try:
        cnpj = _cnpj(registro.get("cnpj"))
        if not cnpj_valido(cnpj):
            problemas.append(f"CNPJ '{_texto(registro.get('cnpj'))}' inválido (dígito verificador)")

        vidas = {}
        for chave, rotulo, _, _ in FAIXAS:
            try:
                vidas[rotulo] = _inteiro(registro.get(f"vidas_{chave}"), f"vidas_{chave}")
            except ValueError as e:
                problemas.append(str(e))
                vidas[rotulo] = 0
        total = sum(vidas.values())
        if not (MIN_VIDAS <= total <= MAX_VIDAS):
            problemas.append(f"total de vidas {total} fora do intervalo {MIN_VIDAS} a {MAX_VIDAS} do PME da Amil")

        try:
            dental = _sim_nao(registro.get("dental"), norm(str(padroes.get("dental_aderir", "sim"))) in ("sim", "true", "1"),
                              "dental")
        except ValueError as e:
            problemas.append(str(e))
            dental = True

        coligacao = COLIGACOES.get(norm(str(padroes.get("coligacao", "nao"))))
        if coligacao is None:
            problemas.append("'Haverá coligação?' inválido na configuração do robô (use sim ou nao)")

        texto_planos = _texto(registro.get("planos")) or "; ".join(padroes.get("planos") or [])
        planos = _planos(texto_planos)
        if not planos:
            problemas.append("planos vazio: informe o nome do plano como aparece na lista da Amil, "
                             "ex.: PLATINUM R1 COPART; AMIL BLACK I R1 COPART")

        corretor = _texto(padroes.get("corretor"))
        if not corretor:
            problemas.append("o corretor do Vínculo de Vendas não está na configuração do robô (Robôs > Amil)")

        pasta = _texto(registro.get("pasta_destino")) or None
        if pasta and not Path(pasta).is_dir():
            problemas.append(f"pasta_destino não existe ou não está acessível: {pasta}")
    except ValueError as e:
        problemas.append(str(e))
    if problemas:
        raise ErroPedido(problemas)
    return Pedido(
        linha=n, id=pid, cnpj=cnpj, vidas=vidas, planos=planos, coligacao=coligacao, corretor=corretor,
        supervisor=_texto(padroes.get("supervisor")), dental=dental, apelido=_texto(registro.get("apelido")),
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
                         + ". Use os nomes da planilha modelo da Amil")
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
    """A planilha modelo da Amil, com o exemplo do vídeo (CNPJ fictício)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "cotacoes"
    colunas = ["id", "cnpj", "apelido", "dental"] + [f"vidas_{f[0]}" for f in FAIXAS] + [
        "planos", "pasta_destino", "observacao"]
    ws.append(colunas)
    exemplo = {"id": "EX-001", "cnpj": "11.222.333/0001-81", "apelido": "EMPRESA", "dental": "sim", "vidas_0_18": 1,
               "vidas_34_38": 2, "vidas_59_mais": 1,
               "planos": "PLATINUM R1 COPART; AMIL BLACK I R1 COPART; AMIL S2500 R1 QP COPART",
               "observacao": "exemplo igual ao vídeo; troque pelo CNPJ real"}
    ws.append([exemplo.get(c, 0 if c.startswith("vidas_") else "") for c in colunas])
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="0033A0")
    ajuda = wb.create_sheet("como_preencher")
    for linha in [
        ("coluna", "o que colocar"),
        ("cnpj", "com ou sem máscara; formate a coluna como Texto para não perder zeros"),
        ("apelido", "nome curto da empresa para o nome do PDF (AMIL PLATINUM EMPRESA.pdf); vazio = sem nome"),
        ("dental", "sim ou nao: aderir ao dental que o portal oferece (vazio = a configuração do robô: sim)"),
        ("vidas_*", f"quantidade em cada faixa; total de {MIN_VIDAS} a {MAX_VIDAS}"),
        ("planos", "o nome do plano exatamente como aparece na lista da Amil, separados por ';'. Cada plano vira "
                   "uma cotação (COT) e um PDF, todas na mesma oportunidade (OPP) da empresa"),
        ("pasta_destino", "pasta do cliente; vazio = o PDF fica só na pasta do robô"),
    ]:
        ajuda.append(linha)
    wb.save(caminho)
