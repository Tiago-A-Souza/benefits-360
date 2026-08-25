"""Assets da marca Newport embutidos no HTML autocontido (sem CDN)."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent / "assets"
_FONTS = _ASSETS / "fonts"
_REPO_DOCS_LOGO = Path(__file__).resolve().parents[3] / "docs" / "newport-logo.png"

_LEMA = "Tranquilidade, segurança e praticidade na escolha de benefícios."
_CONSULTORIA = "Consultoria de Benefícios"
_SITE_URL = "https://newportconsultoria.com.br"
_SITE_ROTULO = "newportconsultoria.com.br"

# Pesos usados no documento (origem: @fontsource/poppins via npm).
_FONT_FILES: tuple[tuple[int, str], ...] = (
    (300, "poppins-latin-300-normal.woff2"),
    (400, "poppins-latin-400-normal.woff2"),
    (600, "poppins-latin-600-normal.woff2"),
    (700, "poppins-latin-700-normal.woff2"),
    (800, "poppins-latin-800-normal.woff2"),
)
_FONT_EXT_FILES: tuple[tuple[int, str], ...] = (
    (400, "poppins-latin-ext-400-normal.woff2"),
    (600, "poppins-latin-ext-600-normal.woff2"),
    (700, "poppins-latin-ext-700-normal.woff2"),
    (800, "poppins-latin-ext-800-normal.woff2"),
)


def lema_newport() -> str:
    return _LEMA


def rotulo_consultoria() -> str:
    return _CONSULTORIA


def site_newport() -> tuple[str, str]:
    return _SITE_URL, _SITE_ROTULO


@lru_cache(maxsize=1)
def logo_data_uri() -> str:
    path = _REPO_DOCS_LOGO if _REPO_DOCS_LOGO.is_file() else (_ASSETS / "newport-logo.png")
    raw = path.read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{b64}"


@lru_cache(maxsize=1)
def logo_bytes_len() -> int:
    path = _REPO_DOCS_LOGO if _REPO_DOCS_LOGO.is_file() else (_ASSETS / "newport-logo.png")
    return path.stat().st_size


def _font_face(weight: int, filename: str, unicode_range: str) -> str:
    raw = (_FONTS / filename).read_bytes()
    b64 = base64.b64encode(raw).decode("ascii")
    return (
        "@font-face{"
        "font-family:'Poppins';"
        f"font-weight:{weight};"
        "font-style:normal;font-display:swap;"
        f"src:url(data:font/woff2;base64,{b64}) format('woff2');"
        f"unicode-range:{unicode_range};"
        "}"
    )


@lru_cache(maxsize=1)
def poppins_font_face_css() -> str:
    # Latin + latin-ext (acentos pt-BR) — arquivos vendidos de @fontsource/poppins.
    latin = "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD"
    latin_ext = "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
    partes: list[str] = []
    for weight, name in _FONT_FILES:
        partes.append(_font_face(weight, name, latin))
    for weight, name in _FONT_EXT_FILES:
        partes.append(_font_face(weight, name, latin_ext))
    return "".join(partes)


@lru_cache(maxsize=1)
def fonts_bytes_total() -> int:
    total = 0
    for _, name in _FONT_FILES + _FONT_EXT_FILES:
        total += (_FONTS / name).stat().st_size
    return total
