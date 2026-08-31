"""Resolução de vínculo titular–dependente a partir de colunas SISCOR opcionais.

Precedência da chave de grupo (documentada):
1. ``CPF TITULAR`` normalizado (11 dígitos) — primário para dependentes e, via
   dependentes, para o titular da mesma família.
2. ``MATRICULA`` — alternativa quando o CPF do titular não consta na linha.

Titulares herdam a chave ``cpf:…`` dos dependentes cujo campo ``TITULAR`` coincide
com o nome do titular, mesmo que o titular possua matrícula própria.
"""

from __future__ import annotations

import re
import unicodedata

from newport_app.models.draft import ParentescoRascunho
from newport_app.models.siscor_import import LinhaSiscorCandidata

_RE_NAO_ALFANUM = re.compile(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿ]+")


def normalizar_nome_titular(valor: str | None) -> str:
    if not valor:
        return ""
    texto = unicodedata.normalize("NFKD", valor.strip().upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = _RE_NAO_ALFANUM.sub(" ", texto)
    return " ".join(texto.split())


def chave_grupo_cpf(cpf_normalizado: str) -> str:
    return f"cpf:{cpf_normalizado}"


def chave_grupo_matricula(matricula: str) -> str:
    return f"mat:{matricula.strip()}"


def _dependentes_do_titular(
    linhas: list[LinhaSiscorCandidata],
    titular: LinhaSiscorCandidata,
) -> list[LinhaSiscorCandidata]:
    nome_tit = normalizar_nome_titular(titular.segurado)
    if not nome_tit:
        return []
    deps: list[LinhaSiscorCandidata] = []
    for linha in linhas:
        if linha.excluida or linha is titular:
            continue
        if linha.titular_nome and normalizar_nome_titular(linha.titular_nome) == nome_tit:
            deps.append(linha)
    return deps


def resolver_vinculos_grupo_familiar(linhas: list[LinhaSiscorCandidata]) -> None:
    """Preenche ``vinculo_grupo_chave`` e ``vinculo_resolvido`` em cada linha."""
    titulares = [
        l
        for l in linhas
        if not l.excluida
        and l.parentesco == ParentescoRascunho.TITULAR
        and l.segurado
    ]

    for linha in linhas:
        if linha.excluida:
            linha.vinculo_grupo_chave = None
            linha.vinculo_resolvido = False
            continue
        linha.vinculo_grupo_chave = None
        linha.vinculo_resolvido = False
        if linha.cpf_titular:
            linha.vinculo_grupo_chave = chave_grupo_cpf(linha.cpf_titular)
            linha.vinculo_resolvido = True

    for titular in titulares:
        chaves_cpf: set[str] = set()
        for dep in _dependentes_do_titular(linhas, titular):
            if dep.cpf_titular:
                chaves_cpf.add(chave_grupo_cpf(dep.cpf_titular))
        if len(chaves_cpf) == 1:
            titular.vinculo_grupo_chave = chaves_cpf.pop()
            titular.vinculo_resolvido = True

    for linha in linhas:
        if linha.excluida or linha.vinculo_resolvido:
            continue
        if linha.matricula:
            linha.vinculo_grupo_chave = chave_grupo_matricula(linha.matricula)
            linha.vinculo_resolvido = True

    for linha in linhas:
        if linha.excluida or linha.vinculo_resolvido:
            continue
        if not linha.titular_nome:
            continue
        for titular in titulares:
            if titular.vinculo_grupo_chave and normalizar_nome_titular(
                linha.titular_nome
            ) == normalizar_nome_titular(titular.segurado):
                linha.vinculo_grupo_chave = titular.vinculo_grupo_chave
                linha.vinculo_resolvido = True
                break
