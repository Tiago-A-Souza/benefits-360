"""Detecção de duplicidades — todas as ocorrências são marcadas."""

from __future__ import annotations

from newport_app.models.siscor_import import AlertaLinhaSiscor, LinhaSiscorCandidata

MENSAGEM_DUPLICIDADE = "Possível registro duplicado — revise."


def _alerta(codigo: str, caminho: str, mensagem: str) -> AlertaLinhaSiscor:
    return AlertaLinhaSiscor(codigo=codigo, caminho=caminho, mensagem=mensagem)


def _chave_duplicidade(linha: LinhaSiscorCandidata) -> tuple[str, str, str] | None:
    if linha.excluida:
        return None
    if not linha.segurado or not linha.nascimento or not linha.plano:
        return None
    return (linha.segurado, linha.nascimento, linha.plano)


def recalcular_duplicidades(linhas: list[LinhaSiscorCandidata]) -> None:
    for linha in linhas:
        linha.alertas = [a for a in linha.alertas if a.codigo != "APP-SIS-006"]

    grupos: dict[tuple[str, str, str], list[LinhaSiscorCandidata]] = {}
    for linha in linhas:
        chave = _chave_duplicidade(linha)
        if chave is None:
            continue
        grupos.setdefault(chave, []).append(linha)

    for grupo in grupos.values():
        if len(grupo) < 2:
            continue
        for linha in grupo:
            caminho = f"/linhas/{linha.id}"
            if not any(a.codigo == "APP-SIS-006" for a in linha.alertas):
                linha.alertas.append(
                    _alerta("APP-SIS-006", caminho, MENSAGEM_DUPLICIDADE)
                )
