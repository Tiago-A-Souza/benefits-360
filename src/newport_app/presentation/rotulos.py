"""Rótulos de proposta compartilhados entre matriz e apresentação."""

from __future__ import annotations

from collections import defaultdict

from newport_app.models.draft import RascunhoEstudo


def rotulo_regime(tipo: str, percentual: int | None = None) -> str:
    if tipo == "percentual" and percentual is not None:
        return f"Coparticipação {percentual}%"
    mapa = {
        "sem": "Sem coparticipação",
        "parcial": "Coparticipação parcial (terapias)",
        "percentual": "Coparticipação percentual",
    }
    return mapa.get(tipo, tipo)


def copart_descricao(rascunho: RascunhoEstudo, regime_id: str | None) -> str | None:
    if not regime_id:
        return None
    regime = next((r for r in rascunho.regimes_copart if r.id == regime_id), None)
    if regime is None:
        return None
    return rotulo_regime(regime.tipo, regime.percentual)


def qualificador_regime_curto(rascunho: RascunhoEstudo, regime_id: str | None) -> str | None:
    desc = copart_descricao(rascunho, regime_id)
    if not desc:
        return None
    if desc == "Sem coparticipação":
        return "sem copart"
    if desc.startswith("Coparticipação "):
        resto = desc.removeprefix("Coparticipação ").strip()
        if resto.endswith("%"):
            return f"copart {resto}"
        return f"copart {resto}"
    return desc


def qualificar_rotulos_propostas(rascunho: RascunhoEstudo, propostas: list) -> None:
    """Garante rótulos únicos entre colunas do comparativo, só quando necessário."""
    grupos: dict[str, list] = defaultdict(list)
    for prop in propostas:
        grupos[(prop.plano_nome or "").strip() or prop.opcao_id].append(prop)

    for nome_base, itens in grupos.items():
        if len(itens) < 2:
            continue
        ops = {
            p.opcao_id: next((o for o in rascunho.opcoes_proposta if o.id == p.opcao_id), None)
            for p in itens
        }
        quals_regime = [
            qualificador_regime_curto(
                rascunho, ops[p.opcao_id].regime_copart_id if ops[p.opcao_id] else None
            )
            for p in itens
        ]
        if len({q for q in quals_regime if q}) == len(itens) and all(quals_regime):
            for prop, qual in zip(itens, quals_regime):
                prop.plano_nome = f"{nome_base} ({qual})"
            continue
        quals_acom = [
            (ops[p.opcao_id].acomodacao or "").strip() if ops[p.opcao_id] else ""
            for p in itens
        ]
        if len({q for q in quals_acom if q}) == len(itens) and all(quals_acom):
            for prop, qual in zip(itens, quals_acom):
                prop.plano_nome = f"{nome_base} ({qual})"
            continue
        for idx, prop in enumerate(itens, start=1):
            prop.plano_nome = f"{nome_base} ({idx})"
