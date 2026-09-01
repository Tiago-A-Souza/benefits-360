"""Agrupamento de vidas em grupos familiares para apresentação.

Precedência da chave: a mesma da frente base (`vinculo_grupo_chave` no rascunho).
Vidas sem vínculo resolvido formam cada uma um grupo próprio, listadas ao final
(ordenadas pelo nome) — não desaparecem; a soma dos grupos = vidas incluídas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from newport_app.models.draft import RascunhoEstudo, VidaRascunho
from newport_app.models.responses import DetalheVidaComparativo


@dataclass
class GrupoFamiliarMontado:
    grupo_id: str
    titular: DetalheVidaComparativo | None
    membros: list[DetalheVidaComparativo] = field(default_factory=list)
    sem_vinculo_resolvido: bool = False

    @property
    def exibir_subtotal(self) -> bool:
        return len(self.membros) > 1


def _chave_grupo(
    detalhe: DetalheVidaComparativo,
    vida_r: VidaRascunho | None,
) -> tuple[str, bool]:
    stamped = detalhe.vinculo_grupo_chave
    if stamped:
        return stamped, False
    if vida_r and vida_r.vinculo_grupo_chave:
        return vida_r.vinculo_grupo_chave, False
    return f"nao_resolvido:{detalhe.vida_id}", True


def _eh_titular(parentesco: str | None) -> bool:
    return bool(parentesco and str(parentesco).lower() == "titular")


def primeiro_nome(nome: str | None) -> str:
    if not nome:
        return "Grupo"
    partes = str(nome).strip().split()
    return partes[0] if partes else "Grupo"


def rotulo_parentesco_exibicao(parentesco: str | None) -> str | None:
    """Rótulo de vínculo para exibição — não é dado pessoal."""
    if not parentesco:
        return None
    chave = str(parentesco).lower()
    mapa = {
        "titular": "titular",
        "conjuge": "cônjuge",
        "filho": "filho(a)",
        "companheiro": "companheiro",
    }
    return mapa.get(chave, parentesco)


def rotulo_vida_agregada(faixa_rotulo: str | None, parentesco: str | None) -> str:
    base = f"Beneficiário · {faixa_rotulo or 'faixa não informada'}"
    rot = rotulo_parentesco_exibicao(parentesco)
    return f"{base} · {rot}" if rot else base


def rotulo_grupo(
    grupo: GrupoFamiliarMontado,
    *,
    nomes_ocultos: bool,
    numero: int | None = None,
) -> str:
    if nomes_ocultos:
        if numero is not None:
            return f"Grupo {numero}"
        n = len(grupo.membros)
        return f"Grupo familiar · {n} vida{'s' if n != 1 else ''}"
    if grupo.sem_vinculo_resolvido:
        base = grupo.membros[0].nome if grupo.membros else "Sem vínculo"
        return primeiro_nome(base)
    if grupo.titular:
        return primeiro_nome(grupo.titular.nome)
    if grupo.membros:
        return primeiro_nome(grupo.membros[0].nome)
    return "Grupo"


def _chave_ordenacao(grupo: GrupoFamiliarMontado) -> tuple[int, str]:
    """Não resolvidos ao final; demais alfabético pelo nome do titular."""
    if grupo.sem_vinculo_resolvido:
        nome = (grupo.membros[0].nome if grupo.membros else grupo.grupo_id).casefold()
        return (1, nome)
    if grupo.titular and grupo.titular.nome:
        return (0, grupo.titular.nome.casefold())
    if grupo.membros:
        return (0, (grupo.membros[0].nome or grupo.grupo_id).casefold())
    return (0, grupo.grupo_id.casefold())


def montar_grupos_familiares(
    vidas: dict[str, DetalheVidaComparativo],
    rascunho: RascunhoEstudo,
) -> list[GrupoFamiliarMontado]:
    por_id = {v.id: v for v in rascunho.vidas}
    buckets: dict[str, GrupoFamiliarMontado] = {}

    for vida_id, detalhe in vidas.items():
        vida_r = por_id.get(vida_id)
        chave, sem = _chave_grupo(detalhe, vida_r)
        slot = buckets.get(chave)
        if slot is None:
            slot = GrupoFamiliarMontado(
                grupo_id=chave, titular=None, sem_vinculo_resolvido=sem
            )
            buckets[chave] = slot
        slot.membros.append(detalhe)
        if _eh_titular(detalhe.parentesco):
            slot.titular = detalhe

    for slot in buckets.values():

        def _ord_membro(v: DetalheVidaComparativo) -> tuple[int, str]:
            return (0 if _eh_titular(v.parentesco) else 1, (v.nome or v.vida_id).casefold())

        slot.membros.sort(key=_ord_membro)
        if slot.titular is None:
            for m in slot.membros:
                if _eh_titular(m.parentesco):
                    slot.titular = m
                    break

    return sorted(buckets.values(), key=_chave_ordenacao)
