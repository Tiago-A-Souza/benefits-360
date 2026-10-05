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


def _carregar_script() -> str:
    return _SCRIPT_PATH.read_text(encoding="utf-8")


def envolver_rede_sandbox(corpo_rede: str, unlock_sha256: str) -> str:
    """Envolve o corpo da aba rede com estado JSON, controles e script."""
    estado = json.dumps(_ESTADO_INICIAL, separators=(",", ":"), ensure_ascii=False)
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
        f"data-unlock='{html.escape(unlock_sha256, quote=True)}'>"
        f"<script type='application/json' id='newport-rede-state'>{estado}</script>"
        f"{barra}"
        f"{corpo_rede}"
        f"{rodape}"
        f"<script>{script}</script>"
        "</div>"
    )
