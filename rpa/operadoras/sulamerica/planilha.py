"""Leitura e validação da planilha de entrada (cotacoes.xlsx).

A planilha é só de entrada: o robô nunca escreve nela. O andamento fica em
saida/estado.json e os resultados em saida/resultados.xlsx.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from nucleo.modelo import ACOMODACOES, FAIXAS, LIMITES_POR_ROTULO, PlanoAlvo
from nucleo.texto import cnpj_valido, norm, so_digitos

from .pedido import PRODUTO_DO_VIDEO, TIPOS_CONTRATACAO, Pedido

ALIASES = {
    "planos_desejados": "planos",
    "congenere": "congenere_atual",
    "vigencia": "vigencia_meses",
}

# O que muda de empresa para empresa é obrigatório. Vigência, coparticipação, contratação, Cuidado 360°,
# vendedor e planos podem ficar vazios: aí vale a configuração do robô (tela Robôs > SulAmérica).
OBRIGATORIAS = ["cnpj", "seguro_novo"] + [f"vidas_{f[0]}" for f in FAIXAS]
OPCIONAIS = ["id", "vendedor", "cuidado_360", "congenere_atual", "tipo_contratacao", "vigencia_meses",
             "coparticipacao", "planos", "pasta_destino", "observacao", "status"] + [f"idades_{f[0]}" for f in FAIXAS]
CONHECIDAS = set(OBRIGATORIAS) | set(OPCIONAIS)


@dataclass
class ErroLinha:
    linha: int
    id: str
    mensagem: str


def _nome_coluna(valor) -> str:
    nome = norm(str(valor or "")).replace(" ", "_").replace("-", "_")
    return ALIASES.get(nome, nome)


def _texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, float) and valor.is_integer():
        valor = int(valor)
    return str(valor).strip()


def _sim_nao(valor, padrao: bool | None = None) -> bool | None:
    t = norm(_texto(valor))
    if t == "":
        return padrao
    if t in ("sim", "s", "yes", "y", "true", "1", "x"):
        return True
    if t in ("nao", "n", "no", "false", "0"):
        return False
    raise ValueError(f"valor '{valor}' não é sim/nao")


def _cnpj(valor) -> str:
    # O Excel guarda CNPJ digitado sem máscara como número e come o zero à esquerda.
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


def _criterio(valor, padrao: int) -> int | None:
    """'menor_preco' -> padrão do config; 'menor_preco:2' -> 2; outro texto -> None."""
    m = re.fullmatch(r"menor[\s_]*preco(?:\s*:\s*(\d+))?", norm(_texto(valor)))
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else padrao


def _planos(valor) -> list[PlanoAlvo]:
    t = _texto(valor)
    if not t:
        return []
    alvos = []
    for item in [p.strip() for p in t.split(";") if p.strip()]:
        nome, acomod = item, None
        if "|" in item:
            nome, acomod = [x.strip() for x in item.split("|", 1)]
        else:
            m = re.match(r"^(.*)\((.*)\)\s*$", item)
            if m:
                nome, acomod = m.group(1).strip(), m.group(2).strip()
        if acomod:
            chave = norm(acomod)
            if chave not in ACOMODACOES:
                raise ValueError(f"planos: acomodação '{acomod}' inválida (use Enfermaria ou Apartamento)")
            acomod = ACOMODACOES[chave]
        alvos.append(PlanoAlvo(nome=nome, acomodacao=acomod))
    return alvos


class ErroPedido(ValueError):
    def __init__(self, problemas: list[str]):
        super().__init__("; ".join(problemas))
        self.problemas = problemas


def ler_registros(caminho: str | Path) -> list[tuple[int, dict]]:
    """Linhas da planilha como dicionários {coluna: valor}, já com os cabeçalhos conferidos."""
    wb = load_workbook(caminho, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    linhas = list(ws.iter_rows(values_only=True))
    wb.close()
    if not linhas:
        raise ValueError("planilha vazia")

    cabecalho = [_nome_coluna(c) for c in linhas[0]]
    # Coluna com nome errado ("Tipo de contratação") seria ignorada e o robô usaria o padrão:
    # melhor recusar a planilha inteira.
    desconhecidas = [str(linhas[0][i]) for i, c in enumerate(cabecalho) if c and c not in CONHECIDAS]
    if desconhecidas:
        raise ValueError("colunas não reconhecidas: " + ", ".join(desconhecidas)
                         + ". Use os nomes da planilha modelo (python main.py --criar-modelo)")
    faltando = [c for c in OBRIGATORIAS if c not in cabecalho]
    if faltando:
        raise ValueError("colunas obrigatórias ausentes na planilha: " + ", ".join(faltando))
    repetidas = sorted({c for c in cabecalho if c and cabecalho.count(c) > 1})
    if repetidas:
        raise ValueError("colunas repetidas na planilha: " + ", ".join(repetidas))

    registros = []
    for n, valores in enumerate(linhas[1:], start=2):
        registro = {cabecalho[i]: v for i, v in enumerate(valores) if i < len(cabecalho) and cabecalho[i]}
        if all(_texto(v) == "" for v in registro.values()):
            continue
        registros.append((n, registro))
    return registros


def montar_pedido(registro: dict, n: int, cfg: dict) -> Pedido:
    """Valida um pedido (linha da planilha ou formulário da tela). Levanta ErroPedido com a lista de problemas."""
    padroes = cfg.get("padroes", {})
    de_para = {norm(k): v for k, v in (cfg.get("congeneres_de_para") or {}).items()}
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
                minimo, maximo = LIMITES_POR_ROTULO[rotulo]
                fora = [i for i in lista if not (minimo <= i <= maximo)]
                if fora:
                    problemas.append(f"idades_{chave}: {fora} fora da faixa {rotulo}")
                if len(lista) != vidas[rotulo]:
                    problemas.append(
                        f"idades_{chave}: {len(lista)} idade(s) informada(s) para {vidas[rotulo]} vida(s) na faixa")
                idades[rotulo] = lista

        total = sum(vidas.values())
        if not (3 <= total <= 29):
            problemas.append(f"total de vidas {total} fora do intervalo 3 a 29 do módulo PME")

        seguro_novo = _sim_nao(registro.get("seguro_novo"))
        if seguro_novo is None:
            problemas.append("seguro_novo vazio (use sim ou nao)")
        congenere = _texto(registro.get("congenere_atual")) or None
        digitada = congenere
        if seguro_novo is False and not congenere:
            problemas.append("congenere_atual é obrigatória quando seguro_novo = nao")
        if congenere:
            congenere = de_para.get(norm(congenere), congenere)

        try:
            vigencia = _inteiro(_texto(registro.get("vigencia_meses")) or padroes.get("vigencia_meses", 24),
                                "vigencia_meses")
        except ValueError as e:
            problemas.append(str(e))
            vigencia = 0
        if vigencia not in (12, 24):
            problemas.append(f"vigencia_meses {vigencia} inválida (use 12 ou 24)")

        copart_texto = _texto(registro.get("coparticipacao")) or str(padroes.get("coparticipacao", "as_duas"))
        copart = " ".join(norm(copart_texto).replace("coparticipacao", "").replace("_", " ").split())
        copart = {"as duas": "as_duas", "ambas": "as_duas", "com e sem": "as_duas", "sem e com": "as_duas",
                  "duas": "as_duas"}.get(copart, copart)
        if copart not in ("com", "sem", "as_duas"):
            problemas.append(f"coparticipacao '{copart_texto}' inválida (use com, sem ou as_duas)")

        tipo = norm(_texto(registro.get("tipo_contratacao")) or padroes.get("tipo_contratacao", "compulsoria"))
        if tipo not in TIPOS_CONTRATACAO:
            problemas.append(f"tipo_contratacao '{tipo}' inválido (use compulsoria, cbo ou flex)")

        cuidado = _sim_nao(registro.get("cuidado_360"),
                           _sim_nao(padroes.get("cuidado_360", "sim")))

        padrao_qtd = int((cfg.get("criterio_plano") or {}).get("quantidade", 1))
        texto_planos = _texto(registro.get("planos"))
        if not texto_planos:   # vazio: os planos que o robô marca por padrão (configuração do robô)
            if padroes.get("planos_modo") == "menor_preco":
                texto_planos = f"menor_preco:{padrao_qtd}"
            else:
                texto_planos = "; ".join(padroes.get("planos") or [])
        criterio = _criterio(texto_planos, padrao_qtd)
        planos = [] if criterio else _planos(texto_planos)
        if criterio is None and not planos:
            problemas.append("planos vazio: informe os planos (Nome | Acomodação; ...), escreva menor_preco "
                             "ou marque os planos padrão na configuração do robô")
        if criterio is not None and criterio < 1:
            problemas.append("menor_preco precisa de quantidade >= 1")

        pasta = _texto(registro.get("pasta_destino")) or None
        if pasta and not Path(pasta).is_dir():
            problemas.append(f"pasta_destino não existe ou não está acessível: {pasta}")
    except ValueError as e:
        problemas.append(str(e))
    if problemas:
        raise ErroPedido(problemas)
    return Pedido(
        linha=n, id=pid, cnpj=cnpj,
        vendedor=_texto(registro.get("vendedor")) or _texto(padroes.get("vendedor")) or None,
        cuidado_360=bool(cuidado), seguro_novo=bool(seguro_novo),
        congenere=None if seguro_novo else congenere,
        congenere_digitada=None if seguro_novo else digitada,
        tipo_contratacao=TIPOS_CONTRATACAO[tipo],
        vigencia_meses=vigencia, coparticipacao=copart,
        vidas=vidas, idades=idades, planos=planos,
        pasta_destino=pasta,
        observacao=_texto(registro.get("observacao")),
        criterio_quantidade=criterio,
        produto=_texto(padroes.get("produto")) or PRODUTO_DO_VIDEO,
    )


def ler_planilha(caminho: str | Path, cfg: dict) -> tuple[list[Pedido], list[ErroLinha]]:
    pedidos: list[Pedido] = []
    erros: list[ErroLinha] = []
    ids_vistos: set[str] = set()
    for n, registro in ler_registros(caminho):
        pid = _texto(registro.get("id")) or f"L{n}"
        try:
            pedido = montar_pedido(registro, n, cfg)
            if pid in ids_vistos:
                raise ErroPedido([f"id '{pid}' repetido na planilha"])
        except ErroPedido as e:
            erros.append(ErroLinha(n, pid, str(e)))
            ids_vistos.add(pid)
            continue
        ids_vistos.add(pid)
        pedidos.append(pedido)
    return pedidos, erros


def criar_modelo(caminho: str | Path) -> None:
    """Gera a planilha modelo com o exemplo do vídeo (com CNPJ fictício)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.worksheet.datavalidation import DataValidation

    wb = Workbook()
    ws = wb.active
    ws.title = "cotacoes"
    colunas = (["id", "cnpj", "vendedor", "cuidado_360", "seguro_novo", "congenere_atual",
                "tipo_contratacao", "vigencia_meses", "coparticipacao"]
               + [f"vidas_{f[0]}" for f in FAIXAS]
               + ["idades_0_18", "idades_59_mais", "planos", "pasta_destino", "observacao"])
    ws.append(colunas)
    exemplo = {
        "id": "EX-001", "cnpj": "11.222.333/0001-81", "vendedor": "", "cuidado_360": "sim",
        "seguro_novo": "nao", "congenere_atual": "NOTREDAME", "tipo_contratacao": "compulsoria",
        "vigencia_meses": 24, "coparticipacao": "com", "vidas_0_18": 1, "vidas_34_38": 2,
        "idades_0_18": "0", "planos": "Especial Mais | Apartamento; Executivo R1 | Apartamento",
        "pasta_destino": "", "observacao": "exemplo igual ao vídeo; troque pelo CNPJ real",
    }
    ws.append([exemplo.get(c, 0 if c.startswith("vidas_") else "") for c in colunas])
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="EA6424")
    for i, c in enumerate(colunas, start=1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = max(12, len(c) + 2)
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions[ws.cell(1, colunas.index("planos") + 1).column_letter].width = 55
    ws.column_dimensions[ws.cell(1, colunas.index("pasta_destino") + 1).column_letter].width = 45
    for coluna, opcoes in (("cuidado_360", "sim,nao"), ("seguro_novo", "sim,nao"),
                           ("tipo_contratacao", "compulsoria,cbo,flex"), ("vigencia_meses", "12,24"),
                           ("coparticipacao", "com,sem,as_duas")):
        letra = ws.cell(1, colunas.index(coluna) + 1).column_letter
        dv = DataValidation(type="list", formula1=f'"{opcoes}"', allow_blank=True)
        ws.add_data_validation(dv)
        dv.add(f"{letra}2:{letra}500")

    ajuda = wb.create_sheet("como_preencher")
    linhas_ajuda = [
        ("coluna", "o que colocar"),
        ("id", "rótulo do pedido nos resultados (opcional). Não controla reemissão: o robô reconhece a mesma cotação por CNPJ + parâmetros + plano"),
        ("cnpj", "com ou sem máscara; formate a coluna como Texto para não perder zeros"),
        ("vendedor", "vazio = o da configuração do robô (ou quem fez o login); senão, o nome como aparece na lista do cotador"),
        ("cuidado_360", "sim/nao (vazio = configuração do robô; o padrão da Newport é 'sim', como no vídeo)"),
        ("seguro_novo", "sim se a empresa não tem plano hoje; nao exige congenere_atual"),
        ("congenere_atual", "operadora atual, como aparece na lista do portal (ex.: NOTREDAME)"),
        ("tipo_contratacao", "compulsoria, cbo ou flex (vazio = configuração do robô)"),
        ("vigencia_meses", "12 ou 24 (vazio = configuração do robô)"),
        ("coparticipacao", "com, sem ou as_duas (vazio = configuração do robô; o padrão da Newport é as_duas). "
                           "as_duas = duas cotações por plano, uma com e outra sem coparticipação, cada uma "
                           "com o seu protocolo e o seu PDF"),
        ("vidas_*", "quantidade de vidas em cada faixa; 0 quando não houver; total de 3 a 29"),
        ("idades_<faixa>", "idade exata de cada vida, separadas por ';' (ex.: 0; 7; 12). O portal pede "
                           "isso em algumas faixas (no vídeo, 0-18). Pode criar colunas idades_ para "
                           "qualquer faixa, ex.: idades_54_58"),
        ("planos", "um ou mais, separados por ';', no formato Nome | Acomodação "
                   "(ex.: Especial Mais | Apartamento). Para o robô escolher o mais barato, escreva "
                   "menor_preco (ou menor_preco:2 para os 2 mais baratos). Vazio = os planos padrão da "
                   "configuração do robô. Cada plano vira uma cotação e um PDF"),
        ("pasta_destino", "pasta COTAÇÕES do cliente; se vazio, o PDF fica só em saida/pdfs"),
    ]
    for linha in linhas_ajuda:
        ajuda.append(linha)
    ajuda["A1"].font = ajuda["B1"].font = Font(bold=True)
    ajuda.column_dimensions["A"].width = 20
    ajuda.column_dimensions["B"].width = 110
    wb.save(caminho)
