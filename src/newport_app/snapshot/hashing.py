"""Utilitários de hash determinístico para snapshots — ETAPA 2.8.1."""

from __future__ import annotations

import hashlib
import json
from typing import Any

# Formato 2.7.0 (implícito): versão não gravada; seleção de propostas fora do hash.
CAMPOS_PAYLOAD_CANONICO_2_7_0 = (
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

# Formato 2.8.0: versão gravada; seleção de propostas (e a ordem das colunas) entram no hash.
CAMPOS_PAYLOAD_CANONICO_2_8_0 = CAMPOS_PAYLOAD_CANONICO_2_7_0 + (
    "snapshot_versao",
    "propostas_apresentacao",
)

CAMPOS_PAYLOAD_CANONICO = CAMPOS_PAYLOAD_CANONICO_2_8_0


def serializar_deterministico(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def hash_sha256_objeto(obj: Any) -> str:
    return hashlib.sha256(serializar_deterministico(obj).encode("utf-8")).hexdigest()


def campos_payload_canonico(versao: str | None) -> tuple[str, ...]:
    """Conjunto canônico da versão do formato. Ausência = formato 2.7.0."""
    if versao is None or versao == "2.7.0":
        return CAMPOS_PAYLOAD_CANONICO_2_7_0
    return CAMPOS_PAYLOAD_CANONICO_2_8_0


def extrair_payload_canonico(conteudo: dict, versao: str | None = None) -> dict:
    """Conteúdo determinístico para hash — exclui timestamps e metadados externos."""
    formato = versao if versao is not None else conteudo.get("snapshot_versao")
    campos = campos_payload_canonico(formato)
    return {k: conteudo[k] for k in campos if k in conteudo}


def hash_snapshot_canonico(conteudo: dict, versao: str | None = None) -> str:
    return hash_sha256_objeto(extrair_payload_canonico(conteudo, versao))
