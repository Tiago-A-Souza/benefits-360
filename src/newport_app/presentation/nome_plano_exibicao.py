"""Encurtamento de nomes de plano só para exibição no documento HTML."""

from __future__ import annotations

import re

# Palavras de acomodação por extenso — já têm linha própria na tabela.
# Não incluir Q, E, QC, QP isolados (código comercial, ex.: «OURO MAIS I Q»).
_ACOMODACAO_PALAVRAS = frozenset(
    {
        "apartamento",
        "enfermaria",
        "quarto coletivo",
        "quarto privativo",
    }
)

_ABRANGENCIA_PAREN = re.compile(
    r"\(([^)]*(?:\bnacional\b|\bregional\b)[^)]*)\)",
    re.IGNORECASE,
)
_SEPARADOR_TRACO = re.compile(r"\s*[—–-]\s*")


def _limpar_espacos(texto: str) -> str:
    return re.sub(r"\s+", " ", texto).strip(" \t—–-")


def encurtar_nome_plano_exibicao(nome: str) -> tuple[str, str | None]:
    """Retira do nome o que já aparece em linha própria (acomodação, abrangência).

    O nome completo permanece no rascunho/snapshot; isto é só para cabeçalhos.
    Retorna (nome_curto, abrangencia_extraida ou None).
    """
    if not (nome or "").strip():
        return "", None
    bruto = nome.strip()
    abrangencias: list[str] = []

    def _capturar_paren(match: re.Match[str]) -> str:
        trecho = match.group(1).strip()
        if trecho:
            abrangencias.append(trecho)
        return " "

    sem_paren = _ABRANGENCIA_PAREN.sub(_capturar_paren, bruto)

    # Trecho após travessão costuma repetir acomodação («R1 — Apartamento»).
    partes_traco = _SEPARADOR_TRACO.split(sem_paren, maxsplit=1)
    base = partes_traco[0]
    if len(partes_traco) > 1:
        resto = partes_traco[1]
        tokens_resto = [t for t in re.split(r"\s+", resto.strip()) if t]
        if all(t.lower() in _ACOMODACAO_PALAVRAS for t in tokens_resto):
            pass  # descarta só acomodação após travessão
        else:
            base = sem_paren

    tokens = [t for t in re.split(r"(\s+)", base) if t]
    filtrados: list[str] = []
    for tok in tokens:
        if tok.isspace():
            filtrados.append(tok)
            continue
        limpo = tok.strip(".,;")
        if limpo.lower() in _ACOMODACAO_PALAVRAS:
            continue
        filtrados.append(tok)

    curto = _limpar_espacos("".join(filtrados))
    if not curto:
        curto = _limpar_espacos(re.sub(_ABRANGENCIA_PAREN, " ", bruto))
    if not curto:
        curto = bruto

    abr: str | None = None
    if abrangencias:
        vistos: set[str] = set()
        unicos: list[str] = []
        for a in abrangencias:
            chave = a.casefold()
            if chave not in vistos:
                vistos.add(chave)
                unicos.append(a)
        abr = " · ".join(unicos)

    return curto, abr


def nome_plano_documento(nome: str) -> str:
    """Nome encurtido para paridade e testes — espelha o cabeçalho do documento."""
    partes = [p.strip() for p in (nome or "").split(" + ") if p.strip()]
    if not partes:
        return ""
    curtos = [encurtar_nome_plano_exibicao(p)[0] for p in partes]
    return " + ".join(curtos) if len(curtos) > 1 else curtos[0]


def nome_plano_cabecalho(
    nome: str,
    *,
    modalidade: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Nome curto para cabeçalho, abrangência retirada e sufixo de modalidade."""
    curto, abr = encurtar_nome_plano_exibicao(nome)
    mod = (modalidade or "").strip() or None
    if mod:
        curto = f"{curto} ({mod})"
    return curto, abr, mod
