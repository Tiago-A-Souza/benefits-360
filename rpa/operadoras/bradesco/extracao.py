"""Leitura de texto das telas da Bradesco (funções puras, testadas sem navegador).

O texto vem de inner_text() da tela (ou do quadro da página antiga). Valores do vídeo para conferir:
Nacional Plus 4x, 1 vida em 00–18 (1.155,96) + 2 em 34–38 (2.257,84) = prêmio 5.671,64; IOF 134,99 (2,38%).
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from nucleo.modelo import ROTULOS
from nucleo.texto import dinheiro, norm, rx, so_digitos, todos_dinheiros

from .seletores import FAIXAS_ANTIGO, FAIXAS_NOVO, RX_NUMERO_PROCESSO, RX_PROCESSO_MODAL, RX_REEMBOLSO

_DINHEIRO = re.compile(r"R\$\s*(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?")


def ler_processo_gerado(texto: str) -> str | None:
    """O número da janela "Processo 16097787 gerado!" (aparece logo depois do Gerar processo, antes de a página do
    cálculo carregar)."""
    from .seletores import RX_PROCESSO_GERADO
    m = RX_PROCESSO_GERADO.search(texto or "")
    return m.group(1) if m else None


def ler_numero_processo(texto: str) -> str | None:
    m = RX_NUMERO_PROCESSO.search(texto or "") or RX_PROCESSO_MODAL.search(texto or "")
    return m.group(1) if m else None


def _linhas(texto: str) -> list[str]:
    return [" ".join(l.split()) for l in (texto or "").splitlines() if l.strip()]


def _juntar_quebras(texto: str) -> str:
    """O portal quebra "R$" e o valor em duas linhas nas colunas estreitas ("R$\\n4.515,68")."""
    return re.sub(r"R\$\s*\n\s*", "R$ ", texto or "")


def ler_tabela_calculo(texto: str) -> dict[str, dict]:
    """Tabela "Valores Unitários" do cálculo: {faixa (rótulo do núcleo): {"valor_vida", "qtd", "total"}}.
    Cada linha: faixa, Saúde (por vida), Saúde Conjugado, Dental Conjugado, Qtd, Saúde (total), ..."""
    tabela: dict[str, dict] = {}
    linhas = _linhas(_juntar_quebras(texto))
    for rotulo in ROTULOS:
        inicio = rx(FAIXAS_ANTIGO[rotulo])
        for linha in linhas:
            m = inicio.match(linha)
            if not m:
                continue
            resto = linha[m.end():]
            valores = [dinheiro(x) for x in _DINHEIRO.findall(resto)]
            inteiros = re.findall(r"(?<![\d,.])\d+(?![\d,.])", _DINHEIRO.sub(" ", resto))
            if len(valores) < 3 or not inteiros:
                continue
            # vídeo: Saúde, Saúde Conjugado, Dental, Qtd, Saúde, Conjugado, Dental, Saúde+Dental (total = 4º valor);
            # portal real 07/11: Saúde, Dental, Qtd, Saúde, Dental, Saúde+Dental (total = 3º valor)
            total = valores[3] if len(valores) >= 7 else valores[2] if len(valores) >= 3 else valores[0]
            tabela[rotulo] = {"valor_vida": valores[0], "qtd": int(inteiros[0]), "total": total}
            break
    return tabela


def _secao(texto: str, inicio: str, fim: str | None = None) -> str:
    t = texto or ""
    m = rx(inicio).search(t)
    if not m:
        return ""
    pedaco = t[m.start():]
    if fim:
        f = rx(fim).search(pedaco, m.end() - m.start())
        if f:
            pedaco = pedaco[:f.start()]
    return pedaco


def _valor_apos(texto: str, rotulo: str) -> Decimal | None:
    for linha in _linhas(_juntar_quebras(texto)):
        if norm(linha).startswith(norm(rotulo)):
            achados = todos_dinheiros(linha)
            if achados:
                return achados[0]
    return None


def _inteiro_apos(texto: str, rotulo: str) -> int | None:
    for linha in _linhas(texto):
        if norm(linha).startswith(norm(rotulo)):
            m = re.search(r"(\d+)\s*$", linha)
            if m:
                return int(m.group(1))
    return None


def ler_totais(texto: str) -> dict:
    """Totais: vidas, prêmio, kit digital, IOF, 1ª parcela e demais parcelas. Vídeo: quadro "Totais Saúde" (e outro
    "Totais Conjugado"); portal real 07/11: um quadro só, "Totais", com o Prêmio Dental e a 1ª parcela já com o dental."""
    secao = _secao(texto, "Totais Saúde", "Totais Conjugado") or _secao(texto, "Totais")
    return {"vidas": _inteiro_apos(secao, "Total de Vidas"), "premio": _valor_apos(secao, "Prêmio Saúde"),
            "dental": _valor_apos(secao, "Prêmio Dental"),
            "kit": _valor_apos(secao, "Taxa Kit Digital") or Decimal("0.00"), "iof": _valor_apos(secao, "I.O.F. Saúde"),
            "total1": _valor_apos(secao, "Total 1ª Parcela"), "demais": _valor_apos(secao, "Demais Parcelas")}


def tem_totais_saude(texto: str) -> bool:
    """O layout do vídeo (sem plano dental): a página do cálculo tem o bloco "Totais Saúde" (e "Totais Conjugado").
    Com um dental marcado o portal mostra outro layout: linha "Plano Dental" e um bloco "Totais" só (07/11)."""
    return bool(rx("Totais Saúde").search(texto or ""))


def layout_do_calculo(texto: str) -> str:
    """"conjugado" (Totais Saúde + Totais Conjugado), "dental" (linha Plano Dental e um "Totais") ou "desconhecido"."""
    if tem_totais_saude(texto):
        return "conjugado"
    return "dental" if rx("Plano Dental").search(texto or "") else "desconhecido"


def ler_totais_conjugado(texto: str) -> dict:
    secao = _secao(texto, "Totais Conjugado")
    return {"dental": _valor_apos(secao, "Prêmio Dental"), "total_geral": _valor_apos(secao, "Total Geral"),
            "total1": _valor_apos(secao, "Total 1ª Parcela")}


def ler_perfil(texto: str) -> dict:
    """Cabeçalho do Perfil 1: plano, código do plano e coparticipação (vídeo: "Nacional Plus", "TPN4 COPART", "30%")."""
    t = " ".join((texto or "").split())
    plano = re.search(r"Plano\s+Sa[uú]de\s+(.+?)\s+C[oó]digo\s+do\s+Plano", t, re.I)
    codigo = re.search(r"C[oó]digo\s+do\s+Plano\s*:\s*(.+?)\s+Regi[aã]o", t, re.I)
    copart = re.search(r"Coparticipa[cç][aã]o\s*:\s*(\d+\s*%|Sem\s+coparticipa[cç][aã]o|N[aã]o|Sem)", t, re.I)
    return {"plano": plano.group(1).strip() if plano else "", "codigo": codigo.group(1).strip() if codigo else "",
            "coparticipacao": copart.group(1).strip() if copart else ""}


def copart_do_texto(texto: str) -> str:
    """"30%" -> "com"; "Sem coparticipação"/"Não"/"0%" -> "sem"; "" -> ""."""
    t = norm(texto)
    if not t:
        return ""
    # "--" é a opção "sem coparticipação" do Alterar Cotação do portal real (10/11: o processo sem copay aparece com "--")
    if t.startswith("sem") or t.startswith("nao") or t.replace(" ", "") in ("0%", "0", "--", "-"):
        return "sem"
    return "com" if re.search(r"\d+\s*%", t) or t in ("sim", "com") else ""


def iof(premio: Decimal, aliquota: Decimal) -> Decimal:
    """IOF de 2,38% sobre o prêmio, arredondado (vídeo: 5.671,64 -> 134,99; 2.448,93 -> 58,28)."""
    return (premio * aliquota).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def conferir_calculo(tabela: dict, vidas: dict[str, int], totais: dict, aliquota: Decimal, tol: Decimal) -> list[str]:
    """O que não bate entre o cálculo e o pedido. Lista vazia = tudo certo."""
    problemas = []
    if not tabela:
        return ["não consegui ler a tabela de valores por faixa etária"]
    for rotulo in ROTULOS:
        pedidas = int(vidas.get(rotulo, 0))
        linha = tabela.get(rotulo)
        if linha is None:
            if pedidas:
                problemas.append(f"a faixa {rotulo} não aparece na tabela do cálculo")
            continue
        if linha["qtd"] != pedidas:
            problemas.append(f"a faixa {rotulo} tem {linha['qtd']} vida(s) no cálculo; o pedido tem {pedidas}")
    soma = sum((v["valor_vida"] * v["qtd"] for v in tabela.values()), Decimal("0"))
    premio = totais.get("premio")
    if premio is None:
        problemas.append("não consegui ler o Prêmio Saúde")
        return problemas
    if abs(soma - premio) > tol:
        problemas.append(f"a soma das faixas ({soma}) não bate com o Prêmio Saúde ({premio})")
    total_vidas = sum(int(v) for v in vidas.values())
    if totais.get("vidas") is not None and totais["vidas"] != total_vidas:
        problemas.append(f"o cálculo tem {totais['vidas']} vida(s); o pedido tem {total_vidas}")
    if totais.get("iof") is None:
        problemas.append("não consegui ler o IOF")
    elif abs(iof(premio, aliquota) - totais["iof"]) > tol:
        problemas.append(f"o IOF ({totais['iof']}) não é {aliquota * 100}% do prêmio ({iof(premio, aliquota)})")
    elif totais.get("total1") is not None:
        sem_dental = premio + totais["kit"] + totais["iof"]
        com_dental = sem_dental + (totais.get("dental") or Decimal("0"))
        if min(abs(sem_dental - totais["total1"]), abs(com_dental - totais["total1"])) > tol:
            problemas.append(f"a 1ª parcela ({totais['total1']}) não é prêmio + kit digital + IOF (+ dental)")
    return problemas


# ------------------------------------------------------------------ resultado (cotador novo)
def reembolso_do_card(texto: str) -> int:
    """"Reembolso Completo (4x tabela)" -> 4; sem multiplicador -> 0."""
    m = RX_REEMBOLSO.search(texto or "")
    return int(m.group(1)) if m else 0


def nome_do_plano(nome_card: str, reembolso: int) -> str:
    """O nome do plano no robô: o nome do card e, quando o card tem multiplicador de reembolso, "Nx" (os três
    "Nacional Plus" do vídeo só se diferenciam por ele: 8x, 6x e 4x)."""
    nome = " ".join((nome_card or "").split())
    return f"{nome} {reembolso}x" if reembolso else nome


def separar_reembolso(nome: str) -> tuple[str, int]:
    """"Nacional Plus 4x" -> ("Nacional Plus", 4); "Nacional III" -> ("Nacional III", 0)."""
    m = re.match(r"^(.*?)\s+(\d+)\s*x$", " ".join((nome or "").split()), re.I)
    return (m.group(1), int(m.group(2))) if m else (" ".join((nome or "").split()), 0)


# Faixas como o bloco "Valores por faixa etária" do card mostra (portal real 07/11): "0-18", ..., "59+"
_FAIXA_CURTA = {"0-18": "0 - 18", "00-18": "0 - 18", "19-23": "19 - 23", "24-28": "24 - 28", "29-33": "29 - 33",
                "34-38": "34 - 38", "39-43": "39 - 43", "44-48": "44 - 48", "49-53": "49 - 53", "54-58": "54 - 58",
                "59+": "59+"}


def ler_valores_card(texto: str) -> dict[str, Decimal]:
    """"Valores por faixa etária" de um card: {faixa do núcleo: valor por vida}. Portal real 07/11: tabela FAIXA |
    Qtd | Tabela | Subtotal, um item por linha ("0-18", "1", "R$ 930,53", "R$ 930,53"); o valor por vida é a Tabela."""
    valores: dict[str, Decimal] = {}
    linhas = _linhas(_juntar_quebras(texto))
    for i, linha in enumerate(linhas):
        rotulo = _FAIXA_CURTA.get(re.sub(r"\s+", "", linha).replace("–", "-"))
        if rotulo and i + 2 < len(linhas) and re.fullmatch(r"\d+", linhas[i + 1]):
            valor = dinheiro(linhas[i + 2])
            if valor is not None:
                valores[rotulo] = valor
    if valores:
        return valores
    for linha in linhas:
        for rotulo in ROTULOS:
            novo = FAIXAS_NOVO[rotulo]
            if norm(linha).startswith(norm(novo)):
                achados = todos_dinheiros(linha)
                if achados:
                    valores[rotulo] = achados[0]
    return valores


def ler_cabecalho_resultado(texto: str) -> dict:
    """Topo do Resultado: CNPJ, adesão, cobertura e total de pessoas."""
    t = " ".join((texto or "").split())
    cnpj = re.search(r"CNPJ/CAEPF\s*:?\s*([\d./-]{14,18})", t)
    adesao = re.search(r"Ades[aã]o\s*:\s*(Compuls[oó]ria|Opcional)", t, re.I)
    cobertura = re.search(r"Cobertura\s*:\s*(Top|Hospitalar)", t, re.I)
    pessoas = re.search(r"Total\s+de\s+pessoas\s*:\s*(\d+)", t, re.I)
    return {"cnpj": so_digitos(cnpj.group(1)) if cnpj else "", "adesao": adesao.group(1) if adesao else "",
            "cobertura": cobertura.group(1) if cobertura else "", "pessoas": int(pessoas.group(1)) if pessoas else None}


def preco(texto: str) -> Decimal | None:
    return dinheiro(texto or "")
