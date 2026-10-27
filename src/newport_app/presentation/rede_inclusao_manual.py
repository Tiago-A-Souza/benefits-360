"""Células de um prestador incluído à mão na etapa 5 (fora dos principais).

Função própria, para não mexer em `formatar_cobertura_abreviada` (usada pela
tabela dos principais):

- hospital que **passa** no critério (tem HGER, HD, PSGER ou MAT em algum plano):
  mesma regra e mesmas siglas dos principais (H, HD, M, PS) — o mesmo hospital
  não pode aparecer de dois jeitos conforme a origem;
- hospital que **não passa** em nenhum plano: o código real da base (siglas onde
  houver abreviação, cru onde não houver), senão a linha ficaria vazia e
  pareceria não coberta.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from newport_app.presentation.rede_codigos import formatar_cobertura_abreviada
from newport_app.presentation.rede_especialidade import (
    CODIGOS_ESPECIALIDADE_PERMITIDOS,
    prestador_passa_filtro_especialidade,
)
from newport_app.presentation.rede_matriz_hospital import PrestadorRedeHospital
from newport_app.presentation.rede_visao import (
    _coberto_na_coluna,
    operadoras_rede_verticalizada,
)
from newport_app.siscor_importer.normalize import normalizar_cabecalho

_ABREV = {"HGER": "H", "HD": "HD", "MAT": "M", "PSGER": "PS"}
_RE_SEP = re.compile(r"[\s\-/]+")
TRACO = "—"


@dataclass(frozen=True)
class ColunaManual:
    """Coluna de plano da seção, já casada com a coluna da base de rede."""

    chave: str
    col_idx: int | None
    operadora_canon: str = ""
    nao_mapeada: bool = False


def tokens_ordenados(valor: object) -> list[str]:
    """Códigos da célula na ordem da base, sem repetição (HPED - PSPED → HPED, PSPED)."""
    if valor is None or str(valor).strip() == "":
        return []
    vistos: list[str] = []
    for parte in _RE_SEP.split(normalizar_cabecalho(str(valor))):
        if parte and parte not in vistos:
            vistos.append(parte)
    return vistos


def prestador_fora_do_criterio(p: PrestadorRedeHospital) -> bool:
    """True se nenhuma célula do prestador traz HGER, HD, PSGER ou MAT."""
    return not prestador_passa_filtro_especialidade(p.celulas)


def texto_codigo_real(valor: object) -> str:
    """Siglas (H, HD, M, PS) onde houver abreviação + código cru nos demais."""
    tokens = tokens_ordenados(valor)
    siglas = [_ABREV[c] for c in ("HGER", "HD", "MAT", "PSGER") if c in tokens]
    crus = [t for t in tokens if t not in CODIGOS_ESPECIALIDADE_PERMITIDOS]
    return " ".join([*siglas, *crus])


def cobertura_celula_manual(
    p: PrestadorRedeHospital,
    ent,
    col_idx: int,
    operadora_canon: str,
    *,
    fora_criterio: bool,
) -> tuple[bool, str]:
    """(coberto, texto) de um prestador num plano — mesma regra de verticalização."""
    if not fora_criterio:
        cob, val = _coberto_na_coluna(
            p, col_idx, operadora_canon, entrada_principal=ent
        )
        return cob, formatar_cobertura_abreviada(val, coberto=cob)
    valor = p.celulas.get(col_idx)
    texto = texto_codigo_real(valor)
    if not texto:
        return False, ""
    ops_vert = operadoras_rede_verticalizada(ent.rede_verticalizada if ent else "")
    if ops_vert and operadora_canon not in ops_vert:
        return False, ""
    return True, texto


def celulas_prestador_manual(
    p: PrestadorRedeHospital,
    ent,
    colunas: Sequence[ColunaManual],
    *,
    fora_criterio: bool,
) -> dict[str, str]:
    """Texto por coluna (chave de coluna → código). Vazio quando não coberto."""
    celulas: dict[str, str] = {}
    for col in colunas:
        if col.nao_mapeada or col.col_idx is None:
            celulas[col.chave] = TRACO
            continue
        _, texto = cobertura_celula_manual(
            p, ent, col.col_idx, col.operadora_canon, fora_criterio=fora_criterio
        )
        celulas[col.chave] = texto
    return celulas
