"""Utilitários de hash determinístico para snapshots."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def serializar_deterministico(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def hash_sha256_objeto(obj: Any) -> str:
    return hashlib.sha256(serializar_deterministico(obj).encode("utf-8")).hexdigest()
