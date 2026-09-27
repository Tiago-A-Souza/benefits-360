"""Normalização de nomes de plano para casamento com a base de rede (igualdade estrita)."""

from __future__ import annotations

import re

from newport_app.siscor_importer.normalize import normalizar_cabecalho

APTO_WORDS = frozenset({"Q", "APTO", "QP", "APARTAMENTO"})
ENF_WORDS = frozenset({"E", "ENF", "QC", "ENFERMARIA"})
PCT_COPART_TOKENS = frozenset({"20", "30", "40", "50"})

LINHA_TAGS: tuple[tuple[str, str], ...] = (
    ("PRO", r"\bPRO\b"),
    ("MAIS", r"\bMAIS\b"),
    ("MAX", r"\bMAX\b"),
    ("SMART", r"\bSMART\b"),
    ("ADVANCE", r"\bADVANCE\b"),
    ("PREMIUM", r"\bPREMIUM\b"),
    ("INFINITY", r"\bINFINITY\b"),
    ("RIO", r"\bRIO\b"),
)


def _strip_period(tok: str) -> str:
    return tok.rstrip(".")


def _linha_produto(tokens: list[str]) -> str | None:
    joined = " ".join(tokens)
    norm = normalizar_cabecalho(joined)
    for tag, pat in LINHA_TAGS:
        if re.search(pat, norm):
            return tag
    return None


def _acom_token(tok: str) -> str | None:
    u = normalizar_cabecalho(_strip_period(tok))
    if u in APTO_WORDS:
        return "APTO"
    if u in ENF_WORDS:
        return "ENF"
    return None


def _extrair_acom(tokens: list[str], *, full: bool) -> tuple[str | None, list[str]]:
    if not tokens:
        return None, []
    if not full:
        ult = normalizar_cabecalho(tokens[-1])
        if ult in {"Q", "APTO", "QP"}:
            return "APTO", tokens[:-1]
        if ult in {"E", "ENF", "QC"}:
            return "ENF", tokens[:-1]
        return None, tokens
    ac = _acom_token(tokens[-1])
    if ac:
        return ac, tokens[:-1]
    for i in range(len(tokens) - 1, -1, -1):
        ac = _acom_token(tokens[i])
        if ac:
            resto = tokens[:i] + tokens[i + 1 :]
            return ac, resto
    return None, tokens


def normalizar_nome_plano_casamento(
    plano: str,
    operadora_canon: str | None,
    *,
    strip_op_prefix: bool,
    strip_copart: bool,
    strip_reembolso_sul: bool,
    strip_paren: bool,
) -> str:
    s = plano
    s = re.sub(r"[\u2014\u2013]", "-", s)
    if strip_paren:
        s = re.sub(r"\([^)]*\)", " ", s)
        s = re.sub(r"\)\s*", " ", s)
    if strip_copart:
        s = re.sub(r"\bCOPAR(?:T)?(?:\s+\d{1,2})?\b", " ", s, flags=re.I)
        s = re.sub(r"\bTP\b", " ", s, flags=re.I)
        s = re.sub(r"\bPJ\b", " ", s, flags=re.I)
    tokens = [
        normalizar_cabecalho(_strip_period(t))
        for t in re.split(r"[\s\-/]+", s)
        if t.strip()
    ]
    tokens = [t for t in tokens if t]
    if strip_copart:
        tokens = [t for t in tokens if t not in PCT_COPART_TOKENS]
    if strip_op_prefix and operadora_canon:
        pref = normalizar_cabecalho(operadora_canon).split()
        if tokens and tokens[0] == pref[0]:
            tokens = tokens[1:]
        elif (
            len(pref) >= 2
            and len(tokens) >= 2
            and tokens[0] == pref[0]
            and tokens[1] == pref[1]
        ):
            tokens = tokens[2:]
    if strip_reembolso_sul and operadora_canon == "SulAmérica":
        tokens = [t for t in tokens if t not in {"R1", "R2", "R3"}]
    return " ".join(tokens).strip()


def chave_casamento_rede(
    operadora: str | None,
    plano: str,
    *,
    strip_op_prefix: bool,
    strip_copart: bool,
    strip_reembolso_sul: bool,
    strip_paren: bool,
    ignore_acom_advance: bool,
    acom_full: bool = False,
) -> tuple[str, str, str, str]:
    nucleo_bruto = normalizar_nome_plano_casamento(
        plano,
        operadora,
        strip_op_prefix=strip_op_prefix,
        strip_copart=strip_copart,
        strip_reembolso_sul=strip_reembolso_sul,
        strip_paren=strip_paren,
    )
    tokens = [
        normalizar_cabecalho(_strip_period(t))
        for t in re.split(r"[\s\-/]+", nucleo_bruto)
        if t
    ]
    acom, resto = _extrair_acom(tokens, full=acom_full)
    linha = _linha_produto(resto)
    nucleo = normalizar_cabecalho(" ".join(resto).strip())
    if ignore_acom_advance and operadora == "NotreDame" and linha == "ADVANCE":
        acom = None
    return (operadora or "", acom or "", linha or "", nucleo)


def flags_chave_casamento(flags: dict) -> dict:
    return {
        "strip_op_prefix": flags.get("strip_op_prefix", False),
        "strip_copart": flags.get("strip_copart", False),
        "strip_reembolso_sul": flags.get("strip_reembolso_sul", False),
        "strip_paren": flags.get("strip_paren", False),
        "ignore_acom_advance": flags.get("ignore_acom_advance", False),
        "acom_full": flags.get("acom_full", False),
    }
