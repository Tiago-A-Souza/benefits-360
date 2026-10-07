"""Sandbox do corretor na aba Rede (fase D2) — estado no HTML, script só nesta aba."""

from __future__ import annotations

import hashlib
import html
import json
import re
from pathlib import Path

_ESTADO_INICIAL = {"v": 1, "mode": "edit", "excluded": []}

_SCRIPT_PATH = Path(__file__).with_name("rede_sandbox.js")


def hash_desbloqueio_estudo(estudo_id: str) -> str:
    """SHA-256 hex do ID — embutido no HTML; o ID em claro não aparece."""
    return hashlib.sha256(estudo_id.encode("utf-8")).hexdigest()


def nome_arquivo_para_cliente(nome_arquivo_origem: str) -> str:
    """Nome do HTML baixado após confirmar — distinto do arquivo de trabalho.

    Ex.: ``apresentacao_completo_71e431d7.html`` →
    ``apresentacao_completo_71e431d7_para_cliente.html``
    """
    bruto = (nome_arquivo_origem or "apresentacao_completo.html").strip()
    if bruto.lower().endswith(".html"):
        return bruto[:-5] + "_para_cliente.html"
    return bruto + "_para_cliente.html"


def _carregar_script() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def remover_coluna_incl_da_marca_rede(html: str) -> str:
    """Remove células «Incl.» — espelha prepareDocumentoCliente (testes estruturais)."""
    out = html
    for pat in (
        r"<th class='rede-sandbox-check[^']*'[^>]*>.*?</th>",
        r"<td class='rede-sandbox-check[^']*'[^>]*>.*?</td>",
    ):
        out = re.sub(pat, "", out, flags=re.S)
    return out


def ajustar_colspans_rede_cliente(html: str) -> str:
    """Ajusta colspan de bloco e cont-rede após remover Incl. (paridade com JS)."""

    out = re.sub(
        r"(<tr class='bloco-rede'[^>]*>\s*<td )colspan='(\d+)'",
        lambda m: f"{m.group(1)}colspan='{max(1, int(m.group(2)) - 1)}'",
        html,
        flags=re.S,
    )
    out = re.sub(
        r"(<tr class='cont-rede'[^>]*>\s*<td )colspan='\d+'",
        r"\1colspan='1'",
        out,
        flags=re.S,
    )
    return out


def preparar_marcacao_rede_para_cliente(html: str) -> str:
    """Transformações DOM da aba Rede no entregável _para_cliente (sem script)."""
    return ajustar_colspans_rede_cliente(remover_coluna_incl_da_marca_rede(html))


def aplicar_colspans_cliente_em_documento(html: str) -> tuple[str, int]:
    """Prepara cada ``table.tabela-rede`` — paridade com prepareDocumentoCliente."""
    matches = list(
        re.finditer(r"<table class='tabela-rede[^>]*>.*?</table>", html, re.S)
    )
    if not matches:
        return html, 0
    out: list[str] = []
    last = 0
    for m in matches:
        out.append(html[last : m.start()])
        out.append(preparar_marcacao_rede_para_cliente(m.group(0)))
        last = m.end()
    out.append(html[last:])
    return "".join(out), len(matches)


def envolver_rede_sandbox(
    corpo_rede: str,
    unlock_sha256: str,
    nome_arquivo_origem: str = "apresentacao_completo.html",
) -> str:
    """Envolve o corpo da aba rede com estado JSON, controles e script."""
    estado = json.dumps(_ESTADO_INICIAL, separators=(",", ":"), ensure_ascii=False)
    nome_origem = html.escape(nome_arquivo_origem, quote=True)
    nome_cliente = html.escape(nome_arquivo_para_cliente(nome_arquivo_origem), quote=True)
    barra = (
        "<div class='rede-sandbox-bar rede-sandbox-js-only' aria-label='Filtros da rede'>"
        "<label>Zona <select id='rede-filtro-zona'><option value=''>Todas</option></select></label>"
        "<label>Município <select id='rede-filtro-mun'><option value=''>Todos</option></select></label>"
        "<label>Busca <input type='search' id='rede-filtro-nome' "
        "placeholder='Nome do prestador' autocomplete='off'></label>"
        "<span class='rede-sandbox-contador' id='rede-contador-marcados'></span>"
        "<button type='button' class='rede-sandbox-btn' id='rede-btn-confirmar'>"
        "Confirmar seleção</button>"
        "</div>"
        "<div class='rede-sandbox-aviso-download rede-sandbox-js-only' "
        "id='rede-aviso-download' hidden role='status'></div>"
    )
    rodape = (
        "<div class='rede-sandbox-foot rede-sandbox-js-only'>"
        "<button type='button' class='rede-sandbox-btn-discreto' id='rede-btn-editar' "
        "hidden>Editar rede</button>"
        "</div>"
    )
    script = _carregar_script()
    return (
        f"<div class='rede-sandbox rede-sandbox-no-js' "
        f"data-unlock='{html.escape(unlock_sha256, quote=True)}' "
        f"data-arquivo-origem='{nome_origem}' "
        f"data-arquivo-cliente='{nome_cliente}'>"
        f"<script type='application/json' id='newport-rede-state'>{estado}</script>"
        f"{barra}"
        f"{corpo_rede}"
        f"{rodape}"
        f"<script>{script}</script>"
        "</div>"
    )
