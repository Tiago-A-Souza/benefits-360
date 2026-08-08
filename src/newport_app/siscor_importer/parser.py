"""Parser de planilha SISCOR (.xlsx)."""

from __future__ import annotations

import hashlib
import uuid
from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any

from openpyxl import load_workbook
from openpyxl.cell.cell import Cell

from newport_app.models.draft import (
    ComponenteFinanceiroRascunho,
    OrigemValorRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
)
from newport_app.models.siscor_import import (
    IMPORTADOR_SISCOR_VERSAO,
    AlertaLinhaSiscor,
    ErroArquivoSiscor,
    EstatisticasImportacaoSiscor,
    ImportacaoSiscorCandidata,
    LinhaSiscorCandidata,
    ResultadoParseSiscor,
    SubgrupoSiscorSugerido,
)
from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS
from newport_app.siscor_importer.parentesco_contagem import contar_parentesco
from newport_app.siscor_importer.duplicidades import recalcular_duplicidades
from newport_app.siscor_importer.money import valor_para_centavos
from newport_app.siscor_importer.normalize import (
    normalizar_cabecalho,
    normalizar_parentesco,
    normalizar_status,
    parse_data_nascimento,
)
from newport_app.siscor_importer.subgrupos import montar_subgrupos


def _erro_arquivo(codigo: str, mensagem: str) -> ErroArquivoSiscor:
    return ErroArquivoSiscor(codigo=codigo, mensagem=mensagem)


def _alerta(codigo: str, caminho: str, mensagem: str) -> AlertaLinhaSiscor:
    return AlertaLinhaSiscor(codigo=codigo, caminho=caminho, mensagem=mensagem)


def _celula_tem_formula(cell: Cell) -> bool:
    if cell.data_type == "f":
        return True
    if isinstance(cell.value, str) and cell.value.startswith("="):
        return True
    return False


def _valor_celula(cell: Cell) -> Any:
    if _celula_tem_formula(cell):
        return None
    return cell.value


def _hash_arquivo(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _linha_vazia(valores: dict[str, Any]) -> bool:
    return all(v is None or str(v).strip() == "" for v in valores.values())


def _estatisticas(linhas: list[LinhaSiscorCandidata]) -> EstatisticasImportacaoSiscor:
    ativas = [linha for linha in linhas if not linha.excluida]
    excluidas = len(linhas) - len(ativas)
    com_excecao = sum(1 for linha in ativas if linha.tem_excecao)
    confirmadas = sum(1 for linha in ativas if linha.registro_confirmado)
    planos = {linha.subgrupo_sugerido_id for linha in ativas if linha.subgrupo_sugerido_id}
    parentesco = contar_parentesco(linhas)
    return EstatisticasImportacaoSiscor(
        total_linhas_lidas=len(ativas),
        linhas_utilizaveis=len(ativas),
        linhas_com_excecao=com_excecao,
        planos_detectados=len(planos),
        confirmadas=confirmadas,
        aguardando_conferencia=len(ativas) - confirmadas,
        qtd_titulares=parentesco.titulares,
        qtd_dependentes=parentesco.dependentes,
        qtd_sem_parentesco=parentesco.sem_parentesco,
        qtd_excluidas=excluidas,
    )


def parse_planilha_siscor(
    conteudo: bytes,
    *,
    estudo_id: str,
    documento_id: str,
    versao: int = 1,
    criado_por: str = "analista-local",
) -> ResultadoParseSiscor:
    if not conteudo:
        return ResultadoParseSiscor(
            sucesso=False,
            erros_arquivo=[
                _erro_arquivo("APP-SIS-F01", "Arquivo vazio ou inválido."),
            ],
        )

    if conteudo[:2] != b"PK":
        return ResultadoParseSiscor(
            sucesso=False,
            erros_arquivo=[
                _erro_arquivo(
                    "APP-SIS-F02",
                    "O arquivo deve estar no formato Excel (.xlsx).",
                ),
            ],
        )

    doc_hash = _hash_arquivo(conteudo)

    workbook_formulas = None
    try:
        workbook = load_workbook(filename=BytesIO(conteudo), read_only=True, data_only=True)
        workbook_formulas = load_workbook(
            filename=BytesIO(conteudo), read_only=True, data_only=False
        )
    except Exception:
        return ResultadoParseSiscor(
            sucesso=False,
            erros_arquivo=[
                _erro_arquivo("APP-SIS-F01", "Não foi possível ler a planilha."),
            ],
            documento_hash_sha256=doc_hash,
        )

    try:
        sheet = workbook.active
        sheet_formulas = workbook_formulas.active
        rows = sheet.iter_rows(min_row=1)
        rows_formulas = sheet_formulas.iter_rows(min_row=1)
        header_row = next(rows, None)
        next(rows_formulas, None)
        if header_row is None:
            return ResultadoParseSiscor(
                sucesso=False,
                erros_arquivo=[
                    _erro_arquivo("APP-SIS-F03", "Planilha sem cabeçalho."),
                ],
                documento_hash_sha256=doc_hash,
            )

        indice_colunas: dict[str, int] = {}
        cabecalhos_vistos: set[str] = set()
        for idx, cell in enumerate(header_row):
            nome = normalizar_cabecalho(cell.value)
            if not nome:
                continue
            if nome in cabecalhos_vistos:
                return ResultadoParseSiscor(
                    sucesso=False,
                    erros_arquivo=[
                        _erro_arquivo(
                            "APP-SIS-F04",
                            "Há colunas duplicadas no cabeçalho da planilha.",
                        ),
                    ],
                    documento_hash_sha256=doc_hash,
                )
            cabecalhos_vistos.add(nome)
            indice_colunas[nome] = idx

        faltantes = [c for c in COLUNAS_OBRIGATORIAS if c not in indice_colunas]
        if faltantes:
            return ResultadoParseSiscor(
                sucesso=False,
                erros_arquivo=[
                    _erro_arquivo(
                        "APP-SIS-F05",
                        "A planilha não possui todas as colunas obrigatórias do layout piloto.",
                    ),
                ],
                documento_hash_sha256=doc_hash,
            )

        linhas: list[LinhaSiscorCandidata] = []
        numero_linha = 1
        for row, row_f in zip(rows, rows_formulas, strict=False):
            numero_linha += 1
            valores: dict[str, Any] = {}
            formulas: dict[str, bool] = {}
            for coluna, col_idx in indice_colunas.items():
                if col_idx >= len(row):
                    valores[coluna] = None
                    continue
                cell = row[col_idx]
                cell_f = row_f[col_idx] if col_idx < len(row_f) else cell
                formulas[coluna] = _celula_tem_formula(cell_f)
                valores[coluna] = _valor_celula(cell_f) if formulas[coluna] else cell.value

            if _linha_vazia(valores):
                continue

            linha_id = str(uuid.uuid4())
            caminho = f"/linhas/{linha_id}"
            alertas: list[AlertaLinhaSiscor] = []

            for coluna, tem_formula in formulas.items():
                if tem_formula:
                    alertas.append(
                        _alerta(
                            "APP-SIS-F07",
                            f"{caminho}/{coluna}",
                            "Célula com fórmula não é aceita — informe o valor calculado.",
                        )
                    )

            cliente = str(valores["CLIENTE"]).strip() if valores.get("CLIENTE") else None
            segurado = (
                str(valores["SEGURADO"]).strip() if valores.get("SEGURADO") else None
            )
            if not segurado:
                alertas.append(
                    _alerta(
                        "APP-SIS-007",
                        f"{caminho}/segurado",
                        "Nome do beneficiário ausente.",
                    )
                )

            parentesco_texto, parentesco = normalizar_parentesco(valores.get("PARENTESCO"))
            if not parentesco_texto:
                alertas.append(
                    _alerta(
                        "APP-SIS-008",
                        f"{caminho}/parentesco",
                        "Parentesco ausente — informe antes de confirmar.",
                    )
                )
            elif parentesco is None:
                alertas.append(
                    _alerta(
                        "APP-SIS-008",
                        f"{caminho}/parentesco",
                        "Parentesco não reconhecido — revise.",
                    )
                )

            nascimento_texto, nascimento, data_invalida = parse_data_nascimento(
                valores.get("DATA DE NASCIMENTO")
            )
            if valores.get("DATA DE NASCIMENTO") in (None, "") or (
                isinstance(valores.get("DATA DE NASCIMENTO"), str)
                and not str(valores.get("DATA DE NASCIMENTO")).strip()
            ):
                alertas.append(
                    _alerta(
                        "APP-SIS-001",
                        f"{caminho}/nascimento",
                        "Data de nascimento ausente.",
                    )
                )
            elif data_invalida:
                alertas.append(
                    _alerta(
                        "APP-SIS-001",
                        f"{caminho}/nascimento",
                        "Data de nascimento inválida.",
                    )
                )
            elif nascimento and nascimento > date.today():
                alertas.append(
                    _alerta(
                        "APP-SIS-002",
                        f"{caminho}/nascimento",
                        "Data de nascimento no futuro.",
                    )
                )

            plano = str(valores["PLANO"]).strip() if valores.get("PLANO") else None
            if not plano:
                alertas.append(
                    _alerta(
                        "APP-SIS-004",
                        f"{caminho}/plano",
                        "Plano ausente na linha importada.",
                    )
                )

            operadora = (
                str(valores["SEGURADORA"]).strip() if valores.get("SEGURADORA") else None
            )
            if not operadora:
                alertas.append(
                    _alerta(
                        "APP-SIS-010",
                        f"{caminho}/operadora",
                        "Operadora ausente na linha importada.",
                    )
                )

            valor_bruto = valores.get("VALOR")
            valor_centavos = valor_para_centavos(valor_bruto)
            if valor_bruto is None or (
                isinstance(valor_bruto, str) and not str(valor_bruto).strip()
            ):
                alertas.append(
                    _alerta(
                        "APP-SIS-009",
                        f"{caminho}/valor",
                        "Valor mensal ausente — informe.",
                    )
                )
            elif valor_centavos is None:
                alertas.append(
                    _alerta(
                        "APP-SIS-012" if str(valor_bruto).strip().startswith("-") else "APP-SIS-009",
                        f"{caminho}/valor",
                        "Valor mensal negativo — revise."
                        if str(valor_bruto).strip().startswith("-")
                        else "Valor mensal ilegível — revise.",
                    )
                )
            elif valor_centavos == 0:
                alertas.append(
                    _alerta(
                        "APP-SIS-003",
                        f"{caminho}/valor",
                        "Valor mensal zerado — revise.",
                    )
                )

            status_texto, status_norm = normalizar_status(valores.get("STATUS SEGURADO"))
            if not status_texto:
                alertas.append(
                    _alerta(
                        "APP-SIS-005",
                        f"{caminho}/status",
                        "Status do beneficiário ausente — revise.",
                    )
                )
            elif status_norm is None:
                alertas.append(
                    _alerta(
                        "APP-SIS-005",
                        f"{caminho}/status",
                        "Status do beneficiário não reconhecido — revise.",
                    )
                )
            incluida = status_norm == "ATIVO"

            valor_fatura = None
            if valor_centavos is not None and valor_centavos > 0:
                valor_fatura = ComponenteFinanceiroRascunho(
                    centavos=valor_centavos,
                    price_basis=PriceBasisRascunho.DESCONHECIDO,
                    proveniencia=ProvenienciaRascunho(
                        origem=OrigemValorRascunho.EXTRAIDO,
                        documento_id=documento_id,
                        extrator_versao=IMPORTADOR_SISCOR_VERSAO,
                        linha_origem=numero_linha,
                        celula_origem=f"VALOR{numero_linha}",
                        confirmado=False,
                    ),
                )

            linhas.append(
                LinhaSiscorCandidata(
                    id=linha_id,
                    numero_linha=numero_linha,
                    celula_origem=f"A{numero_linha}",
                    cliente=cliente,
                    segurado=segurado,
                    parentesco_texto=parentesco_texto,
                    parentesco=parentesco,
                    nascimento=nascimento_texto,
                    plano=plano,
                    operadora=operadora,
                    valor_centavos=valor_centavos,
                    valor_fatura=valor_fatura,
                    status_texto=status_texto,
                    status_normalizado=status_norm,
                    incluida_sugerida=incluida,
                    alertas=alertas,
                )
            )

        if not linhas:
            return ResultadoParseSiscor(
                sucesso=False,
                erros_arquivo=[
                    _erro_arquivo(
                        "APP-SIS-F06",
                        "A planilha não possui linhas utilizáveis.",
                    ),
                ],
                documento_hash_sha256=doc_hash,
            )

        recalcular_duplicidades(linhas)
        subgrupos = montar_subgrupos(linhas)
        empresa = next((linha.cliente for linha in linhas if linha.cliente), None)

        candidata = ImportacaoSiscorCandidata(
            id=str(uuid.uuid4()),
            estudo_id=estudo_id,
            versao=versao,
            documento_id=documento_id,
            documento_hash_sha256=doc_hash,
            empresa_sugerida=empresa,
            linhas=linhas,
            subgrupos_sugeridos=subgrupos,
            estatisticas=_estatisticas(linhas),
            criado_em=datetime.now(timezone.utc),
            criado_por=criado_por,
        )
        return ResultadoParseSiscor(
            sucesso=True,
            candidata=candidata,
            documento_hash_sha256=doc_hash,
        )
    finally:
        workbook.close()
        if workbook_formulas is not None:
            workbook_formulas.close()
