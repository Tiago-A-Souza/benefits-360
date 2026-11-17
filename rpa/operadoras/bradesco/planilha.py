"""Validação dos pedidos da Bradesco (tela e planilha) e a planilha modelo.

O que muda de empresa para empresa vem do pedido (CNPJ, vidas, idades, planos, pasta). O resto (contrato,
corretora, comissionamento, intermediário, ramo) vem da engrenagem do robô; coparticipação, dental, adesão e
cobertura podem mudar numa cotação só ("Mudar só nesta cotação").
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from nucleo.modelo import FAIXAS, LIMITES_POR_ROTULO, PlanoAlvo
from nucleo.texto import cnpj_valido, norm, so_digitos

from .pedido import ACOMODACOES, ADESOES, CATEGORIAS, COBERTURAS, COMISSOES, DENTAIS, PAPEIS, Pedido

FAIXAS_COM_IDADE = ("0 - 18", "59+")    # o portal pede a idade de cada pessoa nessas faixas (vídeo: 00 a 18)
OBRIGATORIAS = ["cnpj"] + [f"vidas_{f[0]}" for f in FAIXAS]
OPCIONAIS = ["id", "coparticipacao", "dental", "adesao", "cobertura", "planos", "pasta_destino", "observacao",
             "status"] + [f"idades_{f[0]}" for f in FAIXAS]
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


def _idades(valor, campo: str) -> list[int]:
    t = _texto(valor)
    if not t:
        return []
    idades = []
    for p in [p for p in re.split(r"[;,\s]+", t) if p]:
        if not p.isdigit():
            raise ValueError(f"{campo}: '{p}' não é idade válida (use números separados por ;)")
        idades.append(int(p))
    return idades


def _escolha(valor, opcoes: dict, campo: str, padrao: str) -> str:
    chave = norm(_texto(valor) or padrao).replace(" ", "_")
    if chave not in opcoes:
        raise ValueError(f"{campo} '{_texto(valor)}' inválido (use {', '.join(opcoes)})")
    return opcoes[chave]


def _planos(texto: str, acomodacao_padrao: str) -> list[PlanoAlvo]:
    alvos = []
    for item in [p.strip() for p in texto.split(";") if p.strip()]:
        nome, acomod = (item.split("|", 1) + [""])[:2] if "|" in item else (item, "")
        nome, acomod = " ".join(nome.split()), acomod.strip() or acomodacao_padrao
        if norm(acomod) not in ACOMODACOES:
            raise ValueError(f"planos: acomodação '{acomod}' inválida (use Quarto ou Enfermaria)")
        alvos.append(PlanoAlvo(nome=nome, acomodacao=ACOMODACOES[norm(acomod)]))
    return alvos


def _criterio(texto: str, padrao: int) -> int | None:
    m = re.fullmatch(r"menor[\s_]*preco(?:\s*:\s*(\d+))?", norm(texto))
    if not m:
        return None
    return int(m.group(1)) if m.group(1) else padrao


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
            if rotulo not in FAIXAS_COM_IDADE:
                continue          # o portal só pede a idade em 00 a 18 e 59 ou mais
            if vidas[rotulo] and not lista:
                problemas.append(f"idades_{chave}: o portal da Bradesco pede a idade de cada pessoa na faixa {rotulo} "
                                 f"(informe {vidas[rotulo]} idade(s); 0 = menor de 1 ano)")
            elif lista:
                minimo, maximo = LIMITES_POR_ROTULO[rotulo]
                fora = [i for i in lista if not (minimo <= i <= maximo)]
                if fora:
                    problemas.append(f"idades_{chave}: {fora} fora da faixa {rotulo}")
                if len(lista) != vidas[rotulo]:
                    problemas.append(f"idades_{chave}: {len(lista)} idade(s) informada(s) para {vidas[rotulo]} "
                                     "vida(s) na faixa")
                idades[rotulo] = lista
        total = sum(vidas.values())
        if not (3 <= total <= 29):
            problemas.append(f"total de vidas {total} fora do intervalo 3 a 29 do SPG")

        copart_texto = _texto(registro.get("coparticipacao")) or str(padroes.get("coparticipacao", "com"))
        copart = " ".join(norm(copart_texto).replace("coparticipacao", "").replace("_", " ").split())
        copart = {"as duas": "as_duas", "ambas": "as_duas", "com e sem": "as_duas", "sem e com": "as_duas",
                  "duas": "as_duas", "sim": "com", "nao": "sem"}.get(copart, copart)
        if copart not in ("com", "sem", "as_duas"):
            problemas.append(f"coparticipacao '{copart_texto}' inválida (use com, sem ou as_duas)")

        dental = _texto(registro.get("dental")) or str(padroes.get("dental", "Sem plano dental"))
        dental = next((d for d in DENTAIS if norm(d) == norm(dental)), None) or dental
        if dental not in DENTAIS:
            problemas.append(f"dental '{dental}' inválido (use {', '.join(DENTAIS)})")

        try:
            adesao = _escolha(registro.get("adesao"), ADESOES, "adesao", padroes.get("adesao", "compulsoria"))
        except ValueError as e:
            problemas.append(str(e))
            adesao = ""
        try:
            cobertura = _escolha(registro.get("cobertura"), COBERTURAS, "cobertura", padroes.get("cobertura", "top"))
        except ValueError as e:
            problemas.append(str(e))
            cobertura = ""

        categoria = next((c for c in CATEGORIAS if norm(c) == norm(padroes.get("categoria", CATEGORIAS[0]))), None)
        if categoria is None:
            problemas.append(f"categoria funcional '{padroes.get('categoria')}' inválida na configuração do robô")
        comissao = COMISSOES.get(norm(str(padroes.get("desconto_comissao", "nenhum"))).replace("%", "").strip())
        if comissao is None:
            problemas.append("desconto de comissionamento inválido na configuração do robô")
        papel = PAPEIS.get(norm(str(padroes.get("intermediario_papel", "corretor"))))
        if papel is None:
            problemas.append("papel do intermediário inválido na configuração do robô")

        acomodacao_padrao = str(padroes.get("acomodacao", "Quarto"))
        padrao_qtd = int((cfg.get("criterio_plano") or {}).get("quantidade", 1))
        texto_planos = _texto(registro.get("planos"))
        if not texto_planos:
            texto_planos = (f"menor_preco:{padrao_qtd}" if padroes.get("planos_modo") == "menor_preco"
                            else "; ".join(padroes.get("planos") or []))
        criterio = _criterio(texto_planos, padrao_qtd)
        planos = [] if criterio else _planos(texto_planos, acomodacao_padrao)
        if criterio is None and not planos:
            problemas.append("planos vazio: informe os planos (Nome | Acomodação; ...), ex.: Nacional Plus 4x | Quarto, "
                             "ou escreva menor_preco")
        if criterio is not None and criterio < 1:
            problemas.append("menor_preco precisa de quantidade >= 1")

        pasta = _texto(registro.get("pasta_destino")) or None
        if pasta and not Path(pasta).is_dir():
            problemas.append(f"pasta_destino não existe ou não está acessível: {pasta}")
    except ValueError as e:
        problemas.append(str(e))
    if problemas:
        raise ErroPedido(problemas)

    def sim(chave: str, padrao: str = "nao") -> bool:
        return norm(str(padroes.get(chave, padrao))) in ("sim", "true", "1", "s")

    return Pedido(
        linha=n, id=pid, cnpj=cnpj, vidas=vidas, idades=idades, planos=planos, coparticipacao=copart,
        dental=dental, adesao=adesao, cobertura=cobertura, categoria=categoria,
        mais_de_um_titular=sim("mais_de_um_titular"), desconto_folha=sim("desconto_folha"),
        desconto_comissao=comissao, sucursal=_texto(padroes.get("sucursal")) or "978",
        codigo_corretor=_texto(padroes.get("codigo_corretor")) or "438451",
        angariacao=_texto(padroes.get("angariacao")) or "3 Primeiras Parcelas 100%",
        corretagem=_texto(padroes.get("corretagem")) or "2% vitalício a partir da 4ª parcela",
        email_corretora=_texto(padroes.get("email_corretora")), celular_corretora=_texto(padroes.get("celular_corretora")),
        intermediario_papel=papel, intermediario_email=_texto(padroes.get("intermediario_email")),
        intermediario_celular=_texto(padroes.get("intermediario_celular")), transferencia=sim("transferencia"),
        ramo=_texto(padroes.get("ramo")) or "OUTROS", pasta_destino=pasta, observacao=_texto(registro.get("observacao")),
        criterio_quantidade=criterio,
    )


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
                         + ". Use os nomes da planilha modelo da Bradesco")
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
    """A planilha modelo da Bradesco, com o exemplo do vídeo (CNPJ fictício)."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "cotacoes"
    colunas = (["id", "cnpj", "coparticipacao", "dental", "adesao", "cobertura"] + [f"vidas_{f[0]}" for f in FAIXAS]
               + ["idades_0_18", "idades_59_mais", "planos", "pasta_destino", "observacao"])
    ws.append(colunas)
    exemplo = {"id": "EX-001", "cnpj": "11.222.333/0001-81", "coparticipacao": "com", "dental": "Sem plano dental",
               "adesao": "compulsoria", "cobertura": "top", "vidas_0_18": 1, "vidas_34_38": 2, "idades_0_18": "0",
               "planos": "Nacional Plus 4x | Quarto; Nacional III | Quarto",
               "observacao": "exemplo igual ao vídeo; troque pelo CNPJ real"}
    ws.append([exemplo.get(c, 0 if c.startswith("vidas_") else "") for c in colunas])
    for celula in ws[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor="CC092F")
    ajuda = wb.create_sheet("como_preencher")
    for linha in [
        ("coluna", "o que colocar"),
        ("cnpj", "com ou sem máscara; formate a coluna como Texto para não perder zeros"),
        ("coparticipacao", "com, sem ou as_duas (vazio = configuração do robô; o padrão da Newport é com, como no vídeo)"),
        ("dental", "Sem plano dental, Padrão Doc 1, Padrão Doc White ou Premium Top 1 (vazio = o padrão da engrenagem: Sem plano dental)"),
        ("adesao / cobertura", "compulsoria ou opcional / top ou hospitalar (vazio = configuração do robô)"),
        ("vidas_*", "quantidade em cada faixa; total de 3 a 29"),
        ("idades_0_18 / idades_59_mais", "a idade de cada pessoa nessas faixas, separadas por ';' (0 = menor de 1 ano)"),
        ("planos", "Nome | Acomodação separados por ';' (ex.: Nacional Plus 4x | Quarto). O 4x é o reembolso do card. "
                   "Todos os planos de uma empresa saem no mesmo processo, um cálculo e um PDF por plano"),
        ("pasta_destino", "pasta do cliente; vazio = o PDF fica só na pasta do robô"),
    ]:
        ajuda.append(linha)
    wb.save(caminho)
