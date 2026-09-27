"""Utilitários para fixtures XLSX fictícias."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook

from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS, COLUNAS_OPCIONAIS

CABECALHO_COMPLETO_50 = list(COLUNAS_OBRIGATORIAS) + [
    "CNPJ CLIENTE",
    "UNIDADE",
    "CNPJ UNIDADE",
    "CONTRATO",
    "STATUS CONTRATO",
    "RAMO",
    "TITULAR",
    "CPF TITULAR",
    "NOME DA MAE",
    "CPF",
    "DOC PIS",
    "RG",
    "CARTAO SUS",
    "DATA DE INICIO",
    "ESTADO CIVIL",
    "SEXO",
    "TIPO DE VIDA",
    "REGISTRO EMPREGADO",
    "CARGO",
    "DEPARTAMENTO",
    "CENTRO DE CUSTO",
    "NIVEL DE CARGO",
    "COD CONTABIL",
    "SALARIO",
    "DATA DE ADMISSAO",
    "MATRICULA",
    "NUM SEGURO",
    "TEL FIXO",
    "TEL CELULAR",
    "EMAIL",
    "CEP",
    "ENDERECO",
    "UF",
    "CIDADE",
    "NUMERO",
    "COMPLEMENTO",
    "BAIRRO",
    "CAMPO EXTRA 1",
    "CAMPO EXTRA 2",
    "CAMPO EXTRA 3",
    "CAMPO EXTRA 4",
    "CAMPO EXTRA 5",
]


def gerar_planilha_siscor(linhas: list[dict[str, object]]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(COLUNAS_OBRIGATORIAS))
    for linha in linhas:
        ws.append([linha.get(col) for col in COLUNAS_OBRIGATORIAS])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def gerar_planilha_siscor_completa(
    linhas: list[dict[str, object]],
    *,
    cabecalho: list[str] | None = None,
    chaves_linha: list[str] | None = None,
) -> bytes:
    """Gera XLSX. ``chaves_linha`` mapeia cada coluna do cabeçalho → chave do dict.

    Use quando o cabeçalho visual difere da chave canônica (ex.: NBSP no header).
    """
    cab = cabecalho or CABECALHO_COMPLETO_50
    chaves = chaves_linha or cab
    if len(chaves) != len(cab):
        raise ValueError("chaves_linha e cabecalho devem ter o mesmo comprimento")
    wb = Workbook()
    ws = wb.active
    ws.append(cab)
    for linha in linhas:
        ws.append([linha.get(chave) for chave in chaves])
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def linha_ficticia(
    idx: int,
    *,
    plano: str = "Plano Demo A",
    operadora: str = "Operadora Fictícia",
    cliente: str = "Empresa Demonstração Ltda.",
    valor: float | None = None,
) -> dict[str, object]:
    ano = 1970 + (idx % 30)
    valor_efetivo = 850.0 + idx if valor is None else valor
    return {
        "CLIENTE": cliente,
        "SEGURADO": f"Beneficiário Fictício {idx + 1}",
        "PARENTESCO": "TITULAR" if idx % 3 == 0 else "FILHO(A)",
        "DATA DE NASCIMENTO": f"01/01/{ano}",
        "PLANO": plano,
        "SEGURADORA": operadora,
        "VALOR": valor_efetivo,
        "STATUS SEGURADO": "ATIVO",
    }


def _cpf_ficticio(seed: int) -> str:
    base = f"{seed:011d}"
    return base


def linha_completa_anistia(
    idx: int,
    *,
    plano: str,
    operadora: str = "Operadora Fictícia",
    cliente: str = "Anistia Internacional Brasil",
    parentesco: str,
    sexo: str,
    titular_nome: str | None,
    cpf_titular: str | None,
    matricula: str | None,
    valor: float,
) -> dict[str, object]:
    ano = 1965 + (idx % 35)
    cpf_tit = cpf_titular
    linha = linha_ficticia(
        idx,
        plano=plano,
        operadora=operadora,
        cliente=cliente,
        valor=valor,
    )
    linha["PARENTESCO"] = parentesco
    linha["SEGURADO"] = f"Vida Anistia {idx + 1}"
    linha["DATA DE NASCIMENTO"] = f"15/06/{ano}"
    linha["SEXO"] = sexo
    linha["TITULAR"] = titular_nome
    linha["CPF TITULAR"] = cpf_tit
    linha["MATRICULA"] = matricula
    linha["TIPO DE VIDA"] = "TITULAR" if parentesco == "TITULAR" else "DEPENDENTE"
    return linha


def _espacos_para_nbsp(texto: str) -> str:
    """Reproduz cabeçalho SISCOR real: espaço comum → U+00A0 entre palavras."""
    return texto.replace(" ", "\u00A0")


def _linhas_anistia_41() -> list[dict[str, object]]:
    """41 vidas — 29F/12M; 5 dependentes sem matrícula; vínculo via CPF TITULAR."""
    linhas: list[dict[str, object]] = []
    sexos = (["FEMININO"] * 29) + (["MASCULINO"] * 12)
    titulares: list[tuple[str, str, str]] = []
    for t in range(27):
        cpf = _cpf_ficticio(1000 + t)
        mat = f"M{t + 1:04d}"
        nome = f"Titular Anistia {t + 1}"
        titulares.append((nome, cpf, mat))

    idx = 0
    for t_idx, (nome, cpf, mat) in enumerate(titulares):
        plano = "Plano Fictício A" if idx < 36 else "Plano Fictício B"
        linha = linha_completa_anistia(
            idx,
            plano=plano,
            parentesco="TITULAR",
            sexo=sexos[idx],
            titular_nome=None,
            cpf_titular=None,
            matricula=mat,
            valor=900.0 + idx,
        )
        linha["SEGURADO"] = nome
        linhas.append(linha)
        idx += 1

    # 14 dependentes — espelha Anistia real: 8 cônjuges, 5 filhos, 1 companheiro;
    # 5 primeiros sem matrícula (só CPF TITULAR).
    dep_specs = [
        ("CÔNJUGE", 0),
        ("CÔNJUGE", 1),
        ("CÔNJUGE", 2),
        ("CÔNJUGE", 3),
        ("CÔNJUGE", 4),
        ("CÔNJUGE", 5),
        ("CÔNJUGE", 6),
        ("CÔNJUGE", 7),
        ("FILHO(A)", 8),
        ("FILHO(A)", 9),
        ("FILHO(A)", 10),
        ("FILHO(A)", 11),
        ("FILHO(A)", 12),
        ("COMPANHEIRO(A)", 0),
    ]
    for d_i, (parentesco, tit_ref) in enumerate(dep_specs):
        nome_tit, cpf_tit, mat_tit = titulares[tit_ref]
        sem_matricula = d_i < 5
        plano = "Plano Fictício A" if idx < 36 else "Plano Fictício B"
        linhas.append(
            linha_completa_anistia(
                idx,
                plano=plano,
                parentesco=parentesco,
                sexo=sexos[idx],
                titular_nome=nome_tit,
                cpf_titular=cpf_tit,
                matricula=None if sem_matricula else mat_tit,
                valor=450.0 + idx,
            )
        )
        idx += 1

    assert len(linhas) == 41

    ufs_distrib = (
        ["RJ"] * 22
        + ["SP"] * 13
        + ["PA"] * 2
        + ["RS"] * 1
        + ["BA"] * 1
    )
    cidade_por_uf = {
        "RJ": "RIO DE JANEIRO",
        "SP": "SAO PAULO",
        "PA": "BELEM",
        "RS": "PORTO ALEGRE",
        "BA": "SALVADOR",
    }
    loc_idx = 0
    for i, linha in enumerate(linhas):
        if i in (3, 17):
            linha["UF"] = None
            linha["CIDADE"] = None
            continue
        uf = ufs_distrib[loc_idx]
        loc_idx += 1
        linha["UF"] = uf
        linha["CIDADE"] = cidade_por_uf[uf]

    return linhas


def planilha_anistia_41_sintetica() -> bytes:
    return gerar_planilha_siscor_completa(_linhas_anistia_41())


def planilha_anistia_41_cabecalho_nbsp() -> bytes:
    """Anistia 41 com cabeçalhos multi-palavra em NBSP (U+00A0), como o SISCOR real.

    Não versione a planilha real — esta fixture reproduz a regressão.
    """
    cab_canon = list(CABECALHO_COMPLETO_50)
    cab_nbsp = [_espacos_para_nbsp(h) for h in cab_canon]
    assert "CPF\u00A0TITULAR" in cab_nbsp
    assert "TIPO\u00A0DE\u00A0VIDA" in cab_nbsp
    assert "DATA\u00A0DE\u00A0NASCIMENTO" in cab_nbsp
    assert "NOME\u00A0DA\u00A0MAE" in cab_nbsp
    assert "SEXO" in cab_nbsp  # palavra única — sem NBSP
    return gerar_planilha_siscor_completa(
        _linhas_anistia_41(),
        cabecalho=cab_nbsp,
        chaves_linha=cab_canon,
    )


def planilha_atef_3_sintetica() -> bytes:
    linhas = [
        linha_completa_anistia(
            0,
            plano="Plano ATEF",
            cliente="ATEF Demo",
            parentesco="TITULAR",
            sexo="MASCULINO",
            titular_nome=None,
            cpf_titular=None,
            matricula="A001",
            valor=1200.0,
        ),
        linha_completa_anistia(
            1,
            plano="Plano ATEF",
            cliente="ATEF Demo",
            parentesco="CÔNJUGE",
            sexo="MASCULINO",
            titular_nome="Titular Anistia 1",
            cpf_titular=_cpf_ficticio(2001),
            matricula=None,
            valor=600.0,
        ),
        linha_completa_anistia(
            2,
            plano="Plano ATEF",
            cliente="ATEF Demo",
            parentesco="FILHO(A)",
            sexo="FEMININO",
            titular_nome="Titular Anistia 1",
            cpf_titular=_cpf_ficticio(2001),
            matricula=None,
            valor=400.0,
        ),
    ]
    linhas[0]["SEGURADO"] = "Titular ATEF"
    linhas[0]["CPF"] = _cpf_ficticio(2001)
    linhas[1]["TITULAR"] = "Titular ATEF"
    linhas[2]["TITULAR"] = "Titular ATEF"
    return gerar_planilha_siscor_completa(linhas)


def planilha_sexo_coluna_celulas_vazias() -> bytes:
    linhas = []
    for i in range(4):
        row = linha_ficticia(i)
        row["SEXO"] = "FEMININO" if i % 2 == 0 else None
        linhas.append(row)
    cab = list(COLUNAS_OBRIGATORIAS) + list(COLUNAS_OPCIONAIS)
    return gerar_planilha_siscor_completa(linhas, cabecalho=cab)


def planilha_12_vidas() -> bytes:
    return gerar_planilha_siscor([linha_ficticia(i) for i in range(12)])


def planilha_12_vidas_valores_zerados() -> bytes:
    return gerar_planilha_siscor([linha_ficticia(i, valor=0) for i in range(12)])


def planilha_41_vidas_2_planos() -> bytes:
    linhas = []
    for i in range(36):
        linhas.append(linha_ficticia(i, plano="Plano Fictício A"))
    for i in range(36, 41):
        linhas.append(linha_ficticia(i, plano="Plano Fictício B"))
    return gerar_planilha_siscor(linhas)


def planilha_41_vidas_cabecalho_nbsp() -> bytes:
    """Simula layout real: 50 colunas e cabeçalhos com U+00A0 (Excel/SISCOR)."""
    cabecalhos: list[str] = []
    for col in COLUNAS_OBRIGATORIAS:
        if col == "DATA DE NASCIMENTO":
            cabecalhos.append("DATA\u00A0DE\u00A0NASCIMENTO")
        elif col == "STATUS SEGURADO":
            cabecalhos.append("STATUS\u00A0SEGURADO")
        else:
            cabecalhos.append(col)
    cabecalhos.extend(f"CAMPO EXTRA {i}" for i in range(1, 43))

    linhas_dados = []
    for i in range(36):
        linhas_dados.append(linha_ficticia(i, plano="Plano Fictício A"))
    for i in range(36, 41):
        linhas_dados.append(linha_ficticia(i, plano="Plano Fictício B"))

    wb = Workbook()
    ws = wb.active
    ws.append(cabecalhos)
    for linha in linhas_dados:
        row = [linha.get(col) for col in COLUNAS_OBRIGATORIAS]
        row.extend([None] * 42)
        ws.append(row)
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def planilha_com_formula_no_valor() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(COLUNAS_OBRIGATORIAS))
    linha = linha_ficticia(0)
    ws.append([linha.get(col) for col in COLUNAS_OBRIGATORIAS])
    linha2 = linha_ficticia(1)
    row = [linha2.get(col) for col in COLUNAS_OBRIGATORIAS]
    ws.append(row)
    col_valor = list(COLUNAS_OBRIGATORIAS).index("VALOR") + 1
    ws.cell(row=3, column=col_valor, value="=850+1")
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
