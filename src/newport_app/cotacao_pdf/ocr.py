"""OCR controlado para páginas sem texto útil."""

from __future__ import annotations

import shutil

from newport_app.cotacao_pdf.extract import PdfDocumento


def tesseract_disponivel() -> bool:
    return shutil.which("tesseract") is not None


def tentar_ocr_pagina(doc: PdfDocumento, pagina: int) -> tuple[str, bool]:
    if doc.paginas_pymupdf is None:
        return "", False
    if not tesseract_disponivel():
        return "", False
    try:
        page = doc.paginas_pymupdf[pagina]
        tp = page.get_textpage_ocr()
        texto = tp.extractText() or ""
        return texto, bool(texto.strip())
    except Exception:
        return "", False
