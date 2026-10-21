"""Linha «Cobertos» — alinhamento de colunas no HTML estático da aba Rede."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_rede_documento_estatico import _html_completo_rede

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _colunas_visuais_tr(tr_inner: str) -> int:
    total = 0
    for m in re.finditer(r"<t[dh]([^>]*)>", tr_inner, re.I):
        attrs = m.group(1)
        cm = re.search(r"colspan=['\"](\d+)['\"]", attrs)
        total += int(cm.group(1)) if cm else 1
    return total


def _texto_td(td_html: str) -> str:
    return re.sub(r"<[^>]+>", "", td_html, flags=re.S).strip()


def _valores_cont_rede(table_html: str) -> list[list[str]]:
    out: list[list[str]] = []
    for inner in re.findall(
        r"<tr class='cont-rede'[^>]*>(.*?)</tr>", table_html, re.S
    ):
        tds = re.findall(r"<td([^>]*)>(.*?)</td>", inner, re.S)
        vals: list[str] = []
        for i, (_attrs, body) in enumerate(tds):
            if i == 0:
                assert "Cobertos" in _texto_td(body)
                continue
            vals.append(_texto_td(body))
        out.append(vals)
    return out


def _blocos_colspan(table_html: str) -> list[int]:
    spans: list[int] = []
    for m in re.finditer(
        r"<tr class='bloco-rede'[^>]*>\s*<td colspan='(\d+)'",
        table_html,
        re.S,
    ):
        spans.append(int(m.group(1)))
    return spans


def _tabelas_rede(html: str) -> list[str]:
    rede = html.split('id="visao-rede"', 1)[-1]
    return re.findall(r"<table class='tabela-rede[^>]*>.*?</table>", rede, re.S)


def test_cont_rede_valores_nao_vazios_e_sem_deslocamento(tmp_path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    for table in _tabelas_rede(html):
        vals_por_bloco = _valores_cont_rede(table)
        assert vals_por_bloco, "Cobertos ausente"
        for vals in vals_por_bloco:
            assert vals, "contagem vazia"
            assert not (
                len(vals) >= 2 and vals[0] == "0" and vals[1] != "0"
            ), f"deslocamento (zero à esquerda): {vals}"


def test_cont_rede_mesmo_numero_colunas_que_cabecalho(tmp_path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    for table in _tabelas_rede(html):
        thead = re.search(r"<thead>.*?<tr[^>]*>(.*?)</tr>", table, re.S)
        assert thead, "thead ausente"
        n_cab = _colunas_visuais_tr(thead.group(1))
        assert n_cab >= 2
        cont_rows = re.findall(
            r"<tr class='cont-rede'[^>]*>(.*?)</tr>", table, re.S
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


def test_bloco_rede_colspan_alinhado_ao_cabecalho(tmp_path):
    html, _, _, _ = _html_completo_rede(tmp_path)
    for table in _tabelas_rede(html):
        thead = re.search(r"<thead>.*?<tr[^>]*>(.*?)</tr>", table, re.S)
        assert thead
        n_cab = _colunas_visuais_tr(thead.group(1))
        blocos = _blocos_colspan(table)
        assert blocos
        assert blocos == [n_cab] * len(blocos)
