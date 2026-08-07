"""Registro estruturado de falhas operacionais — sem PII."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from newport_app.config.paths import caminho_diagnostico_jsonl, garantir_diretorios

_lock = Lock()

_CHAVES_PROIBIDAS = frozenset(
    {
        "nome",
        "segurado",
        "cliente",
        "cpf",
        "endereco",
        "telefone",
        "email",
        "mae",
        "beneficiario",
        "beneficiário",
    }
)


def _sanitizar_valor(valor: Any) -> Any:
    if isinstance(valor, dict):
        return {k: _sanitizar_valor(v) for k, v in valor.items() if k.lower() not in _CHAVES_PROIBIDAS}
    if isinstance(valor, list):
        return [_sanitizar_valor(v) for v in valor]
    if isinstance(valor, str) and len(valor) > 500:
        return valor[:500] + "…"
    return valor


def registrar_evento(
    *,
    estudo_id: str | None,
    etapa: str,
    evento: str,
    detalhe: dict[str, Any] | None = None,
) -> None:
    """Grava uma linha JSON em diagnostico.jsonl."""
    garantir_diretorios()
    caminho = caminho_diagnostico_jsonl()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linha = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "estudo_id": estudo_id,
        "etapa": etapa,
        "evento": evento,
        "detalhe": _sanitizar_valor(detalhe or {}),
    }
    payload = json.dumps(linha, ensure_ascii=False, separators=(",", ":"))
    with _lock:
        with caminho.open("a", encoding="utf-8") as fh:
            fh.write(payload + "\n")


def listar_eventos(*, limite: int = 200) -> list[dict[str, Any]]:
    """Retorna os eventos mais recentes (até ``limite``)."""
    caminho = caminho_diagnostico_jsonl()
    if not caminho.is_file():
        return []
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    eventos: list[dict[str, Any]] = []
    for bruta in linhas[-limite:]:
        bruta = bruta.strip()
        if not bruta:
            continue
        try:
            eventos.append(json.loads(bruta))
        except json.JSONDecodeError:
            continue
    return eventos
