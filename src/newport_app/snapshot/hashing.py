"""Utilitários de hash determinístico para snapshots — ETAPA 2.8.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any

CAMPOS_PAYLOAD_CANONICO = (
    "rascunho",
    "estudo_input",
    "effective_policy",
    "motor_result",
    "comparativo",
    "compiler_versao",
    "motor_versao",
    "policy_set_versao",
    "documentos",
)


def serializar_deterministico(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def hash_sha256_objeto(obj: Any) -> str:
    return hashlib.sha256(serializar_deterministico(obj).encode("utf-8")).hexdigest()


def extrair_payload_canonico(conteudo: dict) -> dict:
    """Conteúdo determinístico para hash — exclui timestamps e metadados externos."""
    return {k: conteudo[k] for k in CAMPOS_PAYLOAD_CANONICO if k in conteudo}


def hash_snapshot_canonico(conteudo: dict) -> str:
    return hash_sha256_objeto(extrair_payload_canonico(conteudo))
