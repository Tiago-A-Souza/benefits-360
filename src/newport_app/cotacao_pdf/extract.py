"""Carregamento unificado de PDF para parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

import pdfplumber
import pymupdf


@dataclass
class PdfDocumento:
    conteudo: bytes
    paginas_texto: list[str] = field(default_factory=list)
    paginas_pymupdf: pymupdf.Document | None = None
    paginas_pdfplumber: pdfplumber.PDF | None = None

    @classmethod
    def from_paginas(cls, paginas: list[str]) -> PdfDocumento:
        """Somente para testes — evita depender de PDF binário."""
        return cls(conteudo=b"%PDF-teste", paginas_texto=list(paginas))
    @classmethod
    def abrir(cls, conteudo: bytes) -> PdfDocumento:
        doc = cls(conteudo=conteudo)
        doc.paginas_pymupdf = pymupdf.open(stream=conteudo, filetype="pdf")
        doc.paginas_texto = [
            (doc.paginas_pymupdf[i].get_text() or "") for i in range(doc.paginas_pymupdf.page_count)
        ]
        doc.paginas_pdfplumber = pdfplumber.open(BytesIO(conteudo))
        return doc

    @property
    def numero_paginas(self) -> int:
        return len(self.paginas_texto)

    def texto(self, pagina: int) -> str:
        if pagina < 0 or pagina >= self.numero_paginas:
            return ""
        return self.paginas_texto[pagina]

    def texto_todo(self) -> str:
        return "\n".join(self.paginas_texto)

    def linhas(self, pagina: int) -> list[str]:
        return [ln.strip() for ln in self.texto(pagina).splitlines() if ln.strip()]

    def tabelas_pdfplumber(self, pagina: int) -> list[list[list[str | None]]]:
        if self.paginas_pdfplumber is None:
            return []
        if pagina < 0 or pagina >= len(self.paginas_pdfplumber.pages):
            return []
        return self.paginas_pdfplumber.pages[pagina].extract_tables() or []

    def palavras_pymupdf(self, pagina: int) -> list[tuple[float, float, float, float, str]]:
        if self.paginas_pymupdf is None:
            return []
        page = self.paginas_pymupdf[pagina]
        return page.get_text("words")

    def fechar(self) -> None:
        if self.paginas_pdfplumber is not None:
            self.paginas_pdfplumber.close()
            self.paginas_pdfplumber = None
        if self.paginas_pymupdf is not None:
            self.paginas_pymupdf.close()
            self.paginas_pymupdf = None

    def __enter__(self) -> PdfDocumento:
        return self

    def __exit__(self, *args) -> None:
        self.fechar()
