"""Leitura única do comparativo congelado no snapshot.

Toda renderização a partir de um snapshot — matriz, ViewModel ou HTML — passa
por aqui. A guarda de formato anterior não pode ser contornada lendo
``payload["comparativo"]`` direto.
"""

from __future__ import annotations

from newport_app.models.responses import ComparativoResponse


class SnapshotFormatoIncompativelError(Exception):
    """Comparativo gravado num formato que não pode ser reaberto neste código."""


MENSAGEM_FORMATO_ANTERIOR = (
    "Este snapshot foi gerado num formato anterior e não pode ser reaberto. "
    "Gere um novo snapshot a partir do comparativo atual."
)


def comparativo_em_formato_anterior(comparativo: object) -> bool:
    if not isinstance(comparativo, dict):
        return False
    if "plano_atual" in comparativo and not comparativo.get("planos_atuais"):
        return True
    return False


def recusar_se_formato_anterior(comparativo: object) -> None:
    if comparativo_em_formato_anterior(comparativo):
        raise SnapshotFormatoIncompativelError(MENSAGEM_FORMATO_ANTERIOR)


def ler_comparativo_congelado(payload: dict | None) -> ComparativoResponse:
    """Valida e devolve o ComparativoResponse gravado no payload do snapshot."""
    bruto = (payload or {}).get("comparativo") or {}
    recusar_se_formato_anterior(bruto)
    return ComparativoResponse.model_validate(bruto)
