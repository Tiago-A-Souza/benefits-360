"""Filtro de log: não gravar JWT nem Authorization."""

from __future__ import annotations

import logging
import re

_BEARER = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-+=/]+")
_JWT = re.compile(r"eyJ[A-Za-z0-9_\-]+=*\.[A-Za-z0-9._\-]+=*")
_AUTH_HDR = re.compile(r"(?i)(authorization['\"]?\s*[:=]\s*['\"]?)[^'\"\s]+")


def redigir_segredos(texto: str) -> str:
    saida = _BEARER.sub(r"\1[redacted]", texto)
    saida = _JWT.sub("[jwt-redacted]", saida)
    saida = _AUTH_HDR.sub(r"\1[redacted]", saida)
    return saida


class SemSegredoFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redigir_segredos(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redigir_segredos(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redigir_segredos(a) if isinstance(a, str) else a for a in record.args
                )
        return True


_instalado = False


def instalar_filtro_logs() -> None:
    global _instalado
    if _instalado:
        return
    _instalado = True
    filtro = SemSegredoFilter()
    logging.getLogger().addFilter(filtro)
    for nome in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        logging.getLogger(nome).addFilter(filtro)
