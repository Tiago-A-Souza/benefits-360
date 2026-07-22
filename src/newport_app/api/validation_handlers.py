"""Respostas sanitizadas para erros de validação da API."""

from __future__ import annotations

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

_TIPOS_AMIGAVEIS: dict[str, str] = {
    "missing": "Campo obrigatório ausente.",
    "enum": "Valor não permitido para este campo.",
    "value_error": "Valor inválido para este campo.",
    "int_parsing": "Informe um número inteiro válido.",
    "date_parsing": "Informe uma data válida.",
    "model_type": "Estrutura de dados inválida.",
    "string_type": "Informe um texto válido.",
    "bool_parsing": "Informe sim ou não.",
}


def _caminho_de_loc(loc: tuple[str | int, ...]) -> str:
    partes = [str(p) for p in loc if p != "body"]
    return "/" + "/".join(partes) if partes else "/"


def _mensagem_amigavel(err: dict) -> str:
    tipo = err.get("type", "")
    if tipo in _TIPOS_AMIGAVEIS:
        return _TIPOS_AMIGAVEIS[tipo]
    return "Revise os dados informados neste campo."


def resposta_validacao_sanitizada(exc: RequestValidationError) -> JSONResponse:
    erros = [
        {
            "codigo": "APP-REQ-001",
            "caminho": _caminho_de_loc(tuple(err.get("loc", ()))),
            "mensagem": _mensagem_amigavel(err),
            "severidade": "bloqueante",
        }
        for err in exc.errors()
    ]
    return JSONResponse(status_code=422, content={"erros": erros})
