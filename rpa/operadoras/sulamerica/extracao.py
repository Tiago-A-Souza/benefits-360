"""Leitura dos textos das telas. Funções puras, testáveis sem navegador.

Recebem o `inner_text()` de um elemento (ou da página) e devolvem dados.
Os exemplos de teste usam os valores reais vistos no vídeo do corretor.
"""
from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from nucleo.modelo import ACOMODACOES, ROTULOS

from .cartao import PlanoNaTela
from nucleo.texto import dinheiro, norm

_BOTOES_CARD = {"selecionar plano", "plano selecionado"}
_ROTULO_COMPACTO = {r.replace(" ", ""): r for r in ROTULOS}


def _tokens(texto: str) -> list[str]:
    partes = re.split(r"[\n\t]+", texto or "")
    return [p.strip() for p in partes if p and p.strip()]


def rotulo_faixa(token: str) -> str | None:
    """'0 - 18', '0-18', '59+' -> rótulo oficial; None se não for faixa."""
    compacto = re.sub(r"\s+", "", token)
    return _ROTULO_COMPACTO.get(compacto)


# Layout novo do portal (visto em 15/11; em 06/11 o card só tinha o total): "R$ 627,45 por vida / mês" e, abaixo,
# "Total estimado: R$ 1.882,35 / mês (3 vidas)". O robô compara o preço do card com a soma das faixas da Comparação, que é
# o TOTAL; lia o 1º valor do card (por vida) e parava com "soma das faixas 1882.35 difere do preço do plano 627.45".
_TOTAL_ESTIMADO_RE = re.compile(r"Total\s+estimado\s*:?\s*(R\$\s*(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?)", re.I)


def preco_do_card(texto: str):
    """O total do plano no card: "Total estimado: R$ X" (layout novo) ou o único valor em R$ do card (layout antigo)."""
    achado = _TOTAL_ESTIMADO_RE.search(texto or "")
    return dinheiro(achado.group(1)) if achado else dinheiro(texto)


def ler_card_plano(texto: str, pagina: int = 1) -> PlanoNaTela | None:
    linhas = [t for t in _tokens(texto) if norm(t) not in _BOTOES_CARD]
    preco = preco_do_card(texto)
    if not linhas or preco is None:
        return None
    acomodacao = next((ACOMODACOES[norm(t)] for t in linhas if norm(t) in ACOMODACOES), "")
    descricao = next((t for t in linhas if re.match(r"^\d{3}\s*[-–]", t)), "")
    copart = next((t for t in linhas if "coparticipa" in norm(t)), "")
    nome = next((t for t in linhas
                 if norm(t) not in ACOMODACOES and "R$" not in t and t != descricao and t != copart), "")
    if not nome:
        return None
    return PlanoNaTela(nome=nome, acomodacao=acomodacao, descricao=descricao,
                       coparticipacao=copart, preco=preco, pagina=pagina)


# Rótulos de faixa dentro de um texto corrido (não casa "10 - 18" nem "0 - 180").
_FAIXA_RE = re.compile(
    r"(?<![\d.,])(0\s*[-–]\s*18|19\s*[-–]\s*23|24\s*[-–]\s*28|29\s*[-–]\s*33|34\s*[-–]\s*38|"
    r"39\s*[-–]\s*43|44\s*[-–]\s*48|49\s*[-–]\s*53|54\s*[-–]\s*58|59\s*\+)(?!\d)")
_DINHEIRO_RE = re.compile(r"R\$\s*(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{1,2})?")
_POR_VIDA_RE = re.compile(_DINHEIRO_RE.pattern + r"\s*/\s*vida", re.I)


def _rotulo_de(trecho: str) -> str | None:
    return rotulo_faixa(trecho.replace("–", "-"))


def ler_tabela_comparacao(texto: str) -> dict[str, dict]:
    """Tabela 'Faixas / Qtd / Valores' da tela de comparação de um plano.

    Retorna {rótulo: {"qtd": int, "valor_vida": Decimal, "subtotal": Decimal|None}}.
    Funciona com cada valor numa linha ou com a linha inteira junta ("0 - 18 1 R$ 521,90 ...").
    """
    inicio = re.search(r"faixas", texto or "", re.I)
    corpo = texto[inicio.start():] if inicio else (texto or "")
    fim = re.search(r"adicionar mais planos", corpo, re.I)
    if fim:
        corpo = corpo[:fim.start()]
    marcas = list(_FAIXA_RE.finditer(corpo))
    tabela: dict[str, dict] = {}
    for i, m in enumerate(marcas):
        rotulo = _rotulo_de(m.group(1))
        if not rotulo or rotulo in tabela:
            continue
        trecho = corpo[m.end(): marcas[i + 1].start() if i + 1 < len(marcas) else len(corpo)]
        por_vida = _POR_VIDA_RE.search(trecho)
        resto = _POR_VIDA_RE.sub(" ", trecho)
        subtotal = dinheiro(resto)
        qtd = re.search(r"\b(\d+)\b", _DINHEIRO_RE.sub(" ", resto))
        tabela[rotulo] = {"qtd": int(qtd.group(1)) if qtd else None,
                          "valor_vida": dinheiro(por_vida.group(0)) if por_vida else None,
                          "subtotal": subtotal}
    return tabela


def conferir_tabela(tabela: dict[str, dict], vidas: dict[str, int], preco_card: Decimal,
                    tolerancia: Decimal) -> list[str]:
    """Lista de divergências (vazia = tudo certo)."""
    problemas = []
    faltando = [r for r in ROTULOS if r not in tabela]
    if faltando:
        problemas.append(f"faixas ausentes na comparação: {faltando}")
    soma = Decimal("0")
    for rotulo, linha in tabela.items():
        qtd, vv, sub = linha["qtd"], linha["valor_vida"], linha["subtotal"]
        esperado = vidas.get(rotulo, 0)
        if qtd is None or vv is None:
            problemas.append(f"faixa {rotulo}: não consegui ler quantidade/valor")
            continue
        if qtd != esperado:
            problemas.append(f"faixa {rotulo}: portal mostra {qtd} vida(s), planilha tem {esperado}")
        if qtd and sub is not None and abs(sub - vv * qtd) > tolerancia:
            problemas.append(f"faixa {rotulo}: subtotal {sub} difere de {qtd} x {vv}")
        soma += vv * qtd
    if preco_card is not None and abs(soma - preco_card) > tolerancia:
        problemas.append(f"soma das faixas {soma} difere do preço do plano {preco_card}")
    return problemas


def ler_resumo(texto: str) -> dict:
    """Bloco 'Saúde + Vida' do Resumo da Simulação."""
    toks = _tokens(texto)
    try:
        inicio = next(i for i, t in enumerate(toks) if norm(t).replace(" ", "") == "saude+vida")
    except StopIteration:
        inicio = 0
    valores = {"total_sem_iof": None, "vida": None, "iof": None, "total": None}
    pendente = None
    for t in toks[inicio + 1:]:
        n = norm(t)
        if n.startswith("odonto"):
            break
        rotulo = None
        if n.startswith("total sem iof"):
            rotulo = "total_sem_iof"
        elif n.startswith("vida"):
            rotulo = "vida"
        elif n.startswith("iof"):
            rotulo = "iof"
        elif n.startswith("total"):
            rotulo = "total"
        valor = dinheiro(t)
        if rotulo:
            pendente = rotulo
        if valor is not None and pendente and valores[pendente] is None:
            valores[pendente] = valor
            pendente = None
    return valores


def iof_por_vida(tabela: dict[str, dict], aliquota: Decimal) -> Decimal:
    """IOF como o portal calcula: arredondado por vida e somado.

    No vídeo: 521,90 x 2,38% = 12,42 e 960,78 x 2,38% = 22,87 (x2) -> 58,16,
    enquanto 2,38% do total (2.443,46) daria 58,15.
    """
    soma = Decimal("0")
    for linha in tabela.values():
        if linha.get("qtd") and linha.get("valor_vida") is not None:
            soma += (linha["valor_vida"] * aliquota).quantize(Decimal("0.01"), ROUND_HALF_UP) * linha["qtd"]
    return soma


def conferir_resumo(resumo: dict, preco_card: Decimal, aliquota: Decimal,
                    tolerancia: Decimal, iof_vida: Decimal | None = None) -> list[str]:
    problemas = []
    if any(resumo[k] is None for k in ("total_sem_iof", "iof", "total")):
        return [f"não consegui ler os totais do resumo: {resumo}"]
    if preco_card is not None and abs(resumo["total_sem_iof"] - preco_card) > tolerancia:
        problemas.append(f"total sem IOF {resumo['total_sem_iof']} difere do preço do plano {preco_card}")
    iof_total = (resumo["total_sem_iof"] * aliquota).quantize(Decimal("0.01"), ROUND_HALF_UP)
    bate_por_vida = iof_vida is not None and abs(resumo["iof"] - iof_vida) <= Decimal("0.01")
    if not bate_por_vida and abs(resumo["iof"] - iof_total) > tolerancia:
        problemas.append(f"IOF {resumo['iof']} não bate com {aliquota * 100}% por vida ({iof_vida}) "
                         f"nem sobre o total ({iof_total})")
    vida = resumo["vida"] or Decimal("0")
    if abs(resumo["total_sem_iof"] + vida + resumo["iof"] - resumo["total"]) > tolerancia:
        problemas.append(f"total {resumo['total']} difere de sem IOF + vida + IOF")
    return problemas


def ler_protocolo(texto: str) -> str | None:
    m = re.search(r"protocolo\s+saude\D{0,12}?(\d{5,})", norm(texto))
    return m.group(1) if m else None


def ler_razao_social(texto: str) -> str:
    toks = _tokens(texto)
    for i, t in enumerate(toks):
        n = norm(t)
        if n.startswith("razao social"):
            resto = t.split(":", 1)[1].strip() if ":" in t else ""
            if resto:
                return resto
            if i + 1 < len(toks):
                return toks[i + 1]
    return ""


def ler_status_vidas(texto: str) -> int | None:
    """'3 vidas distribuídas' -> 3; '1/3 vidas (faltam 2)' -> 1."""
    n = norm(texto)
    m = re.search(r"(\d+)\s*vidas?\s+distribuidas?", n)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*/\s*\d+\s*vidas?", n)
    if m:
        return int(m.group(1))
    return None


def ler_faixas_idades(texto: str) -> dict[str, tuple[int, int]]:
    """Faixas que o portal pede idade exata: {rótulo: (informadas, total)}.

    Lê só o bloco de cima (antes do campo 'Idade'), porque a lista de
    'Idades adicionadas' repete os rótulos.
    """
    texto = texto or ""
    marco = re.search(r"(?im)^\s*idade\s*:?\s*$", texto)
    topo = texto[:marco.start()] if marco else texto
    faixas: dict[str, tuple[int, int]] = {}
    for m in re.finditer(_FAIXA_RE.pattern + r"\s*(\d+)\s*/\s*(\d+)", topo):
        rotulo = _rotulo_de(m.group(1))
        if rotulo and rotulo not in faixas:
            faixas[rotulo] = (int(m.group(2)), int(m.group(3)))
    return faixas


def ler_caracteristicas(texto: str) -> dict[str, str]:
    """Bloco 'Características da Cotação' do resumo (visto no vídeo):

    Vidas: 3 | Produto: 557 - AHO | Tipo de contratação: Compulsória | Vigência contratual: 24 meses |
    Operadora de origem / anterior: NOTREDAME | Coparticipação: Com coparticipação
    """
    toks = _tokens(texto)
    try:
        inicio = next(i for i, t in enumerate(toks) if norm(t).startswith("caracteristicas da cotacao"))
    except StopIteration:
        return {}
    campos = {"vidas": "vidas", "produto": "produto", "tipo de contratacao": "tipo",
              "vigencia contratual": "vigencia", "operadora de origem": "operadora",
              "coparticipacao": "coparticipacao"}
    achados: dict[str, str] = {}
    pendente = None
    for t in toks[inicio + 1:]:
        rotulo, _, valor = t.partition(":")
        chave = next((v for k, v in campos.items() if norm(rotulo).startswith(k)), None) if _ else None
        if chave:
            if valor.strip():
                achados.setdefault(chave, valor.strip())
                pendente = None
            else:
                pendente = chave
        elif pendente:
            achados.setdefault(pendente, t)
            pendente = None
    return achados


def conferir_caracteristicas(c: dict[str, str], pedido) -> list[str]:
    """Compara o que o resumo diz com o pedido. Campo ausente também é problema (falha fechada)."""
    problemas = []

    def falta(campo):
        problemas.append(f"o resumo não mostra '{campo}'")

    produto = getattr(pedido, "produto", "")
    if produto and "produto" in c and norm(c["produto"]) != norm(produto):
        problemas.append(f"resumo com produto '{c['produto']}'; pedido {produto}")
    if "vidas" not in c:
        falta("Vidas")
    elif re.sub(r"\D", "", c["vidas"]) != str(pedido.total_vidas):
        problemas.append(f"resumo com {c['vidas']} vidas; planilha tem {pedido.total_vidas}")
    if "tipo" not in c:
        falta("Tipo de contratação")
    elif norm(c["tipo"]) != norm(pedido.tipo_contratacao):
        problemas.append(f"resumo com tipo de contratação '{c['tipo']}'; pedido {pedido.tipo_contratacao}")
    if "vigencia" not in c:
        falta("Vigência contratual")
    elif f"{pedido.vigencia_meses} meses" not in norm(c["vigencia"]):
        problemas.append(f"resumo com vigência '{c['vigencia']}'; pedido {pedido.vigencia_meses} meses")
    if "coparticipacao" not in c:
        falta("Coparticipação")
    elif not norm(c["coparticipacao"]).startswith(pedido.coparticipacao):
        problemas.append(f"resumo com '{c['coparticipacao']}'; pedido {pedido.coparticipacao} coparticipação")
    if not pedido.seguro_novo:   # VALIDAR: o que o portal mostra aqui para seguro novo
        if "operadora" not in c:
            falta("Operadora de origem / anterior")
        elif not any(norm(n) in norm(c["operadora"])
                     for n in (getattr(pedido, "congeneres_para_tentar", lambda: [pedido.congenere])() or [pedido.congenere])):
            problemas.append(f"resumo com operadora anterior '{c['operadora']}'; pedido {pedido.congenere}")
    return problemas


def ler_plano_resumo(texto: str) -> str:
    """Nome do plano logo abaixo de 'Planos Saúde' no resumo."""
    toks = _tokens(texto)
    for i, t in enumerate(toks):
        if norm(t) == "planos saude" and i + 1 < len(toks):
            return toks[i + 1]
    return ""


# Identidade da versão do cotador (Next.js): os arquivos principais levam o hash do build no nome. Mudou o hash = o portal
# foi atualizado (15/11: card do plano e trocas de tela passaram a se comportar de outro jeito e o robô parou).
_BUILD_RE = re.compile(r"/_next/static/chunks/((?:webpack|main-app|app/layout)-[0-9a-f]{8,}\.js)")


def build_do_portal(srcs: list[str]) -> str:
    """'webpack-538a...js|app/layout-81e0...js|main-app-81e2...js' a partir dos <script src> da página; '' se não for Next.js."""
    achados = {m.group(1) for src in srcs or [] if (m := _BUILD_RE.search(src or ""))}
    return "|".join(sorted(achados))
