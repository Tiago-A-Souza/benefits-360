"""Leitura de texto das telas da Amil (vendasmil) e as conferências de valores. Funções puras, sem navegador.

Os textos vêm do vídeo e dos quadros (codegen/amil_mapa_video.md). O portal troca célula e linha de lugar sem
aviso: tudo aqui aceita tabulação, quebra de linha ou espaço entre os valores.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from nucleo.modelo import ROTULOS
from nucleo.texto import norm, rx

RX_OPP = re.compile(r"\bOPP-(\d+)\b")
RX_COT = re.compile(r"\bCOT-(\d+)\b")
_NUM = r"(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})"
_VALOR = r"(?:R\$\s*)?" + _NUM
RX_VALOR = re.compile(_VALOR)
RX_TOTAL_VIDAS = re.compile(r"Total\s+de\s+Vidas\s*:?\s*(\d+)", re.I)
RX_VALOR_TOTAL = re.compile(r"Valor\s+Total\s*:?\s*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})", re.I)
STATUS_COTACAO = ("Em Digitação", "Concluída", "Expirada", "Cancelada")


def dinheiro(texto: str) -> Decimal:
    """"R$ 4.769,00" ou "4.769,00" -> Decimal("4769.00")."""
    m = RX_VALOR.search(texto or "")
    if not m:
        raise ValueError(f"valor inválido: {texto!r}")
    return Decimal(m.group(1).replace(".", "").replace(",", "."))


def _num(texto: str) -> Decimal:
    return Decimal(texto.replace(".", "").replace(",", "."))


def _d(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def ler_opp(texto: str) -> str | None:
    m = RX_OPP.search(texto or "")
    return f"OPP-{m.group(1)}" if m else None


def ler_cot(texto: str) -> str | None:
    m = RX_COT.search(texto or "")
    return f"COT-{m.group(1)}" if m else None


def ler_numero_do_painel(texto: str, prefixo: str) -> str | None:
    """"Número da Oportunidade: OPP-5147302" / "Número da Cotação: COT-5185118" (painel da direita)."""
    rotulo = "Número da Oportunidade" if prefixo == "OPP" else "Número da Cotação"
    m = re.search(rf"{rx(rotulo).pattern}\s*:?\s*({prefixo}-\d+)", texto or "", re.I)
    return m.group(1) if m else None


# ---------------------------------------------------------------- Selecionar Planos (a grade das 10 faixas)

def ler_totais_da_grade(texto: str) -> tuple[int | None, Decimal | None]:
    """"Total de Vidas: 4" e "Valor Total: R$ 4.769,00" (aparecem duas vezes na tela, no alto e no rodapé da grade; vale a
    última leitura). Só até "Aditivos do Plano": a caixa do aditivo tem os próprios "Total de Vidas" e "Valor Total"
    (R$ 0,00 no portal real, 12/11) e não são os da grade."""
    texto = re.split(r"Aditivos? do Plano", texto or "", maxsplit=1, flags=re.I)[0]
    vidas = RX_TOTAL_VIDAS.findall(texto or "")
    valor = RX_VALOR_TOTAL.findall(texto or "")
    return (int(vidas[-1]) if vidas else None,
            _num(valor[-1]) if valor else None)


def conferir_grade(esperado: dict[str, int], qtds: list[int], valores: list[Decimal], subtotais: list[Decimal],
                   total_vidas: int | None, valor_total: Decimal | None, tol: Decimal) -> list[str]:
    """As 10 faixas, na ordem do portal (até 18 ... 59 ou mais): quantidade pedida, valor por vida, subtotal e totais.
    O valor por vida muda com o total de vidas: só vale depois de preencher todas as faixas."""
    problemas = []
    if not (len(qtds) == len(valores) == len(subtotais) == len(ROTULOS)):
        return [f"a grade tem {len(qtds)} quantidades, {len(valores)} valores e {len(subtotais)} subtotais; "
                f"esperava {len(ROTULOS)} de cada"]
    pedidas = [int(esperado.get(r, 0)) for r in ROTULOS]
    for r, pedido, tela in zip(ROTULOS, pedidas, qtds):
        if pedido != tela:
            problemas.append(f"faixa {r}: o portal está com {tela} vida(s), o pedido tem {pedido}")
    if total_vidas is not None and total_vidas != sum(pedidas):
        problemas.append(f"o portal diz {total_vidas} vida(s) no total, o pedido tem {sum(pedidas)}")
    for r, q, v, sub in zip(ROTULOS, qtds, valores, subtotais):
        if q and v <= 0:
            problemas.append(f"faixa {r}: o portal não mostrou valor por vida")
        if abs(_d(v * q) - sub) > tol:
            problemas.append(f"faixa {r}: {q} × {v} = {_d(v * q)}, o subtotal do portal é {sub}")
    soma = sum(subtotais, Decimal(0))
    if valor_total is not None and abs(soma - valor_total) > tol:
        problemas.append(f"a soma dos subtotais ({soma}) não é o Valor Total do portal ({valor_total})")
    return problemas


# ---------------------------------------------------------------- Revisar Cotação

def _depois_do_rotulo(texto: str, rotulo: str) -> str:
    """O valor que vem logo depois de um rótulo ("CORRETOR" / "EDLAINE ..."), na mesma linha ou na seguinte."""
    linhas = [" ".join(l.split()) for l in (texto or "").splitlines() if l.strip()]
    for i, linha in enumerate(linhas):
        if norm(linha) == norm(rotulo) and i + 1 < len(linhas):
            return linhas[i + 1]
        m = re.match(rf"^{re.escape(rotulo)}\s*:\s*(.+)$", linha, re.I)
        if m:
            return m.group(1).strip()
    return ""


def _bloco(texto: str, inicio: str, fim: str) -> str:
    """O texto entre dois títulos (sem acento, sem maiúsculas); vazio se o início não existir."""
    t = texto or ""
    i = rx(inicio).search(t)
    if not i:
        return ""
    f = rx(fim).search(t, i.end())
    return t[i.end(): f.start() if f else len(t)]


def ler_revisao(texto: str) -> dict:
    """A tela Revisar Cotação: números, plano, totais, selo de 50% e o dental dos 12 meses."""
    t = texto or ""
    medico = _bloco(t, "Nome do Plano Médico", "Nome do Plano Dental")
    total_medico = re.search(r"Total\s+(\d+)((?:\s*" + _VALOR + r")+)\s*$", medico.strip(), re.S)
    valores_total = [_num(x) for x in RX_VALOR.findall(total_medico.group(2))] if total_medico else []
    geral = re.search(r"Total\s+Geral(?!\s+ap[óo]s)\s*R\$\s*" + _NUM, t, re.I)
    apos12 = re.search(r"Total\s+Geral\s+ap[óo]s\s+12\s+Meses.*?R\$\s*" + _NUM, t, re.I | re.S)
    depois12 = t[apos12.start():] if apos12 else ""
    dental12 = re.findall(r"Total\s+(\d+)\s*R\$\s*" + _NUM, depois12)
    validade = re.search(r"DATA\s+DE\s+VALIDADE\s*(\d{2}/\d{2}/\d{4})(?:,?\s*(\d{2}:\d{2}))?", t, re.I)
    criacao = re.search(r"DATA\s+DE\s+CRIA[ÇC][ÃA]O\s*(\d{2}/\d{2}/\d{4})(?:,?\s*(\d{2}:\d{2}))?", t, re.I)
    oportunidade = re.search(r"OPORTUNIDADE\s*(OPP-\d+)", t, re.I)
    return {
        "cot": ler_cot(t), "opp": oportunidade.group(1) if oportunidade else ler_opp(t),
        "bloco_medico": medico,
        "selo_50": bool(re.search(r"Plano\s+eleg[ií]vel|Desconto\s*50\s*%", medico, re.I)),
        "vidas": int(total_medico.group(1)) if total_medico else None,
        "mensal": valores_total[-1] if valores_total else None,         # Valor/mês a partir da 3ª parcela
        "total_geral": _num(geral.group(1)) if geral else None,      # 1ª e 2ª parcelas (com o desconto, se houver)
        "total_12_meses": _num(apos12.group(1)) if apos12 else None,
        "dental_12_meses": _num(dental12[-1][1]) if dental12 else Decimal("0.00"),
        "tem_dental_12_meses": bool(dental12),
        "validade": (validade.group(1) + (f" {validade.group(2)}" if validade.group(2) else "")) if validade else "",
        "criacao": (criacao.group(1) + (f" {criacao.group(2)}" if criacao.group(2) else "")) if criacao else "",
        "tabela": _depois_do_rotulo(t, "TABELA"),
        "corretor": _depois_do_rotulo(t, "CORRETOR"),
    }


def conferir_revisao(rev: dict, plano: str, total_vidas: int, corretor: str, valor_total_grade: Decimal | None,
                     tol: Decimal, dental: bool) -> list[str]:
    """Falha fechada antes de "Concluir Cotação": plano, vidas, corretor e os valores (selo de 50% e 12 meses)."""
    problemas = []
    if not rev.get("cot"):
        problemas.append("a revisão não mostra o número da cotação (COT-...)")
    if not rx(plano).search(rev.get("bloco_medico") or ""):
        problemas.append(f"o plano '{plano}' não aparece na revisão")
    if rev.get("vidas") is not None and rev["vidas"] != total_vidas:
        problemas.append(f"a revisão tem {rev['vidas']} vida(s), o pedido tem {total_vidas}")
    if corretor and rev.get("corretor") and norm(corretor) not in norm(rev["corretor"]):
        problemas.append(f"o corretor da revisão é '{rev['corretor']}', o pedido é '{corretor}'")
    mensal, geral, apos12 = rev.get("mensal"), rev.get("total_geral"), rev.get("total_12_meses")
    if mensal is None or geral is None or apos12 is None:
        problemas.append("não consegui ler os totais da revisão (valor por mês, Total Geral e Total Geral após 12 Meses)")
        return problemas
    if valor_total_grade is not None and abs(mensal - valor_total_grade) > tol:
        problemas.append(f"o valor por mês da revisão ({mensal}) não é o Valor Total da grade ({valor_total_grade})")
    esperado_geral = _d(mensal / 2) if rev.get("selo_50") else mensal
    if abs(geral - esperado_geral) > tol:
        problemas.append(f"o Total Geral é {geral}; "
                         + (f"com o selo de 50% era esperado {esperado_geral} (metade de {mensal})"
                            if rev.get("selo_50") else f"sem desconto era esperado {mensal}"))
    esperado_12 = mensal + (rev.get("dental_12_meses") or Decimal(0))
    if abs(apos12 - esperado_12) > tol:
        problemas.append(f"o Total Geral após 12 Meses é {apos12}; esperado {esperado_12} "
                         f"(total {mensal} + dental {rev.get('dental_12_meses') or Decimal('0.00')})")
    if dental and not rev.get("tem_dental_12_meses"):
        problemas.append("o pedido adere ao dental, mas a revisão não mostra o dental nos 12 meses")
    if not dental and rev.get("tem_dental_12_meses"):
        problemas.append("o pedido não adere ao dental, mas a revisão mostra o dental nos 12 meses")
    return problemas


# ---------------------------------------------------------------- Oportunidade: lista de cotações

def ler_cotacoes_da_oportunidade(texto: str) -> list[dict]:
    """"Cotações da Oportunidade (N)": ID, valor, total de vidas e status de cada linha."""
    status = "|".join(re.escape(s).replace(r"\ ", r"\s+") for s in STATUS_COTACAO)
    saida = []
    for m in re.finditer(rf"(COT-\d+)\s*R\$\s*{_NUM}\s*(\d+)\s*({status})", texto or "", re.I):
        saida.append({"cot": m.group(1), "valor": _num(m.group(2)),
                      "vidas": int(m.group(3)), "status": " ".join(m.group(4).split())})
    return saida


def valores_por_vida(valores: list[Decimal]) -> dict[str, Decimal]:
    """Os valores da grade, na ordem do portal, com o rótulo de cada faixa."""
    return dict(zip(ROTULOS, valores))
