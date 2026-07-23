"""Pipeline de extração de cotações PDF."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

__all__ = ["parse_cotacao_pdf"]


def parse_cotacao_pdf(*args: Any, **kwargs: Any):
    from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf as _impl

    return _impl(*args, **kwargs)


if TYPE_CHECKING:
    from newport_app.cotacao_pdf.pipeline import parse_cotacao_pdf as parse_cotacao_pdf
