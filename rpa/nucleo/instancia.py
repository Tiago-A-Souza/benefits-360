"""Uma instância do robô por porta, e o casamento config.yaml ↔ 8600 / config_simulador.yaml ↔ 8601."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from .trava import OcupadoErro, Trava

__all__ = ["OcupadoErro", "TravaPorta", "mensagem_porta_config", "PORTA_REAL", "PORTA_TREINO"]

PORTA_REAL = 8600
PORTA_TREINO = 8601
ARQUIVO_REAL = "config.yaml"
ARQUIVO_TREINO = "config_simulador.yaml"

MENSAGEM_TREINO_NA_REAL = (
    "Este arquivo é o modo TREINO (simulador). Ele sobe na porta 8601, com saída em saida_simulador. "
    "A porta 8600 é só do robô REAL (config.yaml, pasta saida). "
    "Use o atalho “Treinar no simulador” ou: python -m app --config config_simulador.yaml --porta 8601."
)
MENSAGEM_REAL_NO_TREINO = (
    "config.yaml é o robô REAL (porta 8600, pasta saida). "
    "A porta 8601 é só do modo treino (config_simulador.yaml, saida_simulador). "
    "Use o atalho “Abrir Benefits Robo” ou: python -m app --config config.yaml --porta 8600."
)


def pasta_travas() -> Path:
    extra = os.environ.get("NEWPORT_TRAVA_PASTA")
    if extra:
        return Path(extra)
    raiz = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return Path(raiz) / "NewportCotacoes" / "travas"


def mensagem_porta_config(caminho_config: str | Path, porta: int) -> str | None:
    """None se a combinação for permitida; senão a frase para o corretor."""
    nome = Path(caminho_config).name.lower()
    porta = int(porta)
    if nome == ARQUIVO_TREINO and porta == PORTA_REAL:
        return MENSAGEM_TREINO_NA_REAL
    if nome == ARQUIVO_REAL and porta == PORTA_TREINO:
        return MENSAGEM_REAL_NO_TREINO
    return None


class TravaPorta(Trava):
    """Impede dois robôs na mesma porta. Não derruba o que já está ligado."""

    def __init__(self, porta: int):
        porta = int(porta)
        super().__init__(
            pasta_travas(),
            nome=f"porta-{porta}.lock",
            mensagem=(
                f"Já existe um robô nesta porta ({porta}). O que está ligado continua; "
                "este atalho não abre outro. Feche a janela do robô que já está no ar se quiser trocar."
            ),
        )
        self.porta = porta

    def __enter__(self) -> "TravaPorta":
        super().__enter__()
        try:
            self._arquivo.seek(0)
            self._arquivo.truncate()
            self._arquivo.write(str(os.getpid()))
            self._arquivo.flush()
        except Exception:  # noqa: BLE001
            pass
        return self
