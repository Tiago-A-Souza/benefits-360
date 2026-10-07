"""Estrutura da linha «Cobertos» no HTML _para_cliente (colunas alinhadas)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from newport_app.presentation.rede_sandbox import preparar_marcacao_rede_para_cliente
from tests.test_rede_fase_d2 import _html_completo_rede

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _colunas_visuais_tr(tr_inner: str) -> int:
    total = 0
    for m in re.finditer(r"<t[dh]([^>]*)>", tr_inner, re.I):
        attrs = m.group(1)
        cm = re.search(r"colspan=['\"](\d+)['\"]", attrs)
        total += int(cm.group(1)) if cm else 1
    return total


def _tabelas_rede(html: str) -> list[str]:
    rede = html.split('id="visao-rede"', 1)[-1]
    return re.findall(r"<table class='tabela-rede[^>]*>.*?</table>", rede, re.S)


def test_cont_rede_mesmo_numero_colunas_que_cabecalho_no_cliente(tmp_path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    html, _, _ = _html_completo_rede(tmp_path)
    for table in _tabelas_rede(html):
        cliente = preparar_marcacao_rede_para_cliente(table)
        thead = re.search(r"<thead>.*?<tr[^>]*>(.*?)</tr>", cliente, re.S)
        assert thead, "thead ausente"
        n_cab = _colunas_visuais_tr(thead.group(1))
        assert n_cab >= 2
        cont_rows = re.findall(
            r"<tr class='cont-rede'[^>]*>(.*?)</tr>", cliente, re.S
        )
        assert cont_rows, "linha Cobertos ausente"
        for inner in cont_rows:
            n_cont = _colunas_visuais_tr(inner)
            assert n_cont == n_cab, (n_cont, n_cab, inner[:160])
            assert re.match(
                r"\s*<td colspan='1'>Cobertos</td>",
                inner,
                re.S,
            ), inner[:160]
