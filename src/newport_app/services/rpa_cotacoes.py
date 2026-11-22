"""Consulta a tela do RPA de Cotações (processo separado, sem CORS) — só leitura."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from newport_app.config.runtime import modo_hospedado

COMANDO_SUBIR = r"powershell -ExecutionPolicy Bypass -File .\scripts\subir-benefits-e-rpa.ps1"

DEFAULT_TELA_URL = "http://127.0.0.1:8600"

AVISO_IFRAME_HOSPEDADO = (
    "No site hospedado o iframe do robô não funciona. Use a aba Cotações: "
    "o navegador fala com o robô no seu PC (http://127.0.0.1:8600)."
)


def url_tela_rpa() -> str:
    return os.environ.get("NEWPORT_RPA_TELA_URL", DEFAULT_TELA_URL).rstrip("/")


def consultar_estado_tela_rpa(timeout_s: float = 2.5) -> dict[str, Any]:
    if modo_hospedado():
        return {
            "ligado": False,
            "url": url_tela_rpa(),
            "hospedado": True,
            "aviso": AVISO_IFRAME_HOSPEDADO,
        }
    url = f"{url_tela_rpa()}/api/estado"
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            if resp.status != 200:
                return {
                    "ligado": False,
                    "url": url_tela_rpa(),
                    "comando_subir": COMANDO_SUBIR,
                }
            estado = json.loads(resp.read().decode("utf-8"))
            return {
                "ligado": True,
                "url": url_tela_rpa(),
                "estado": estado,
            }
    except (urllib.error.URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError):
        return {
            "ligado": False,
            "url": url_tela_rpa(),
            "comando_subir": COMANDO_SUBIR,
        }