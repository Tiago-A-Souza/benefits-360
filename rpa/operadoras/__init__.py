"""Registro das operadoras disponíveis.

Cada operadora é um módulo separado (operadoras/<id>/) e é carregada à parte: se o módulo de uma der erro
ao carregar, a tela abre normalmente e mostra só aquela operadora como "indisponível", com o motivo.

Para adicionar uma operadora: inclua (id, nome, módulo, classe) em _REGISTRO.
A tela mostra automaticamente toda operadora registrada e ativa no config.yaml.
"""
from __future__ import annotations

import importlib
import logging

from nucleo import credenciais

from .base import Operadora

# (id, nome para a tela, módulo, classe). O nome serve para mostrar a operadora mesmo quando ela não carrega.
_REGISTRO: list[tuple[str, str, str, str]] = [
    ("sulamerica", "SulAmérica", "operadoras.sulamerica", "SulAmerica"),
    ("bradesco", "Bradesco", "operadoras.bradesco", "Bradesco"),
    ("amil", "Amil", "operadoras.amil", "Amil"),
]
_INSTANCIAS: dict[str, Operadora] = {}
_INDISPONIVEIS: dict[str, dict] = {}


class OperadoraIndisponivel(KeyError):
    """A operadora está registrada, mas o módulo dela não carregou."""

    def __str__(self) -> str:
        return str(self.args[0]) if self.args else "operadora indisponível"


def _carregar(registro: list[tuple[str, str, str, str]] | None = None) -> None:
    """Carrega cada operadora à parte. Uma que falhar fica em _INDISPONIVEIS e não derruba as outras."""
    _INSTANCIAS.clear()
    _INDISPONIVEIS.clear()
    for op_id, nome, modulo, classe in (registro if registro is not None else _REGISTRO):
        try:
            instancia = getattr(importlib.import_module(modulo), classe)()
            credenciais.registrar_campos(instancia.id, instancia.campos_login())
            _INSTANCIAS[instancia.id] = instancia
        except Exception as e:  # noqa: BLE001  (qualquer erro de uma operadora fica só nela)
            motivo = (f"{type(e).__name__}: {e}".splitlines() or [""])[0][:300]
            _INDISPONIVEIS[op_id] = {"id": op_id, "nome": nome, "motivo": motivo}
            logging.getLogger("operadoras").error(f"A operadora {nome} está indisponível: {motivo}")


_carregar()


def obter(op_id: str) -> Operadora:
    if op_id in _INSTANCIAS:
        return _INSTANCIAS[op_id]
    if op_id in _INDISPONIVEIS:
        d = _INDISPONIVEIS[op_id]
        raise OperadoraIndisponivel(f"a operadora {d['nome']} está indisponível ({d['motivo']})")
    raise KeyError(f"operadora '{op_id}' não existe. Disponíveis: {', '.join(_INSTANCIAS)}")


def todas() -> list[Operadora]:
    return list(_INSTANCIAS.values())


def ativas(total: dict) -> list[Operadora]:
    secoes = total.get("operadoras") or {}
    return [op for op in todas() if (secoes.get(op.id) or {}).get("ativa", True) and op.id in secoes]


def indisponiveis(total: dict | None = None) -> list[dict]:
    """Operadoras que não carregaram: {id, nome, motivo}. Com a configuração, só as que estão nela e ativas."""
    if total is None:
        return [dict(d) for d in _INDISPONIVEIS.values()]
    secoes = total.get("operadoras") or {}
    return [dict(d) for i, d in _INDISPONIVEIS.items() if i in secoes and (secoes.get(i) or {}).get("ativa", True)]
