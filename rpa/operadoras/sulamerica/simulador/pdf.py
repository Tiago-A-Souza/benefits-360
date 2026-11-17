"""Gera um PDF mínimo (sem dependências) com algumas linhas de texto."""
from __future__ import annotations


def _escapar(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def pdf_simples(linhas: list[str]) -> bytes:
    conteudo = ["BT", "/F1 12 Tf", "50 800 Td", "16 TL"]
    for linha in linhas:
        conteudo.append(f"({_escapar(linha)}) Tj T*")
    conteudo.append("ET")
    stream = "\n".join(conteudo).encode("latin-1", "replace")
    objetos = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
        b"/Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    saida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    saida += b"%" + b"0" * 1200 + b"\n"   # comentário: deixa o arquivo com tamanho de proposta real
    offsets = []
    for i, obj in enumerate(objetos, start=1):
        offsets.append(len(saida))
        saida += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"
    xref = len(saida)
    saida += f"xref\n0 {len(objetos) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        saida += f"{off:010d} 00000 n \n".encode()
    saida += f"trailer\n<< /Size {len(objetos) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(saida)
