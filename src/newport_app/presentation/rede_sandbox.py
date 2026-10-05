"""Sandbox do corretor na aba Rede (fase D2) — estado no HTML, script só nesta aba."""

from __future__ import annotations

import hashlib
import html
import json
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
