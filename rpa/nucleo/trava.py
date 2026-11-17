"""Travas entre processos.

Trava(pasta): impede duas execuções do robô ao mesmo tempo na mesma pasta de saída. Sem ela, a tela
e a linha de comando (ou duas janelas da tela) poderiam ler o mesmo registro anti-reemissão ao mesmo
tempo e emitir a mesma cotação duas vezes. A tela segura esta trava enquanto a janela da operadora
estiver aberta.

Trava(pasta, nome, esperar_s=...): a mesma ideia para operações curtas (ex.: cada gravação do
estado.json), esperando a vez em vez de recusar.
"""
from __future__ import annotations

import os
import time
from pathlib import Path


class OcupadoErro(RuntimeError):
    pass


MENSAGEM_ROBO = ("já existe um robô rodando com esta pasta de saída (tela aberta com a janela do portal, "
                 "ou outro terminal). Espere terminar ou feche o outro antes de começar.")


class Trava:
    def __init__(self, pasta: str | Path, nome: str = ".robo_em_execucao", esperar_s: float = 0,
                 mensagem: str = MENSAGEM_ROBO):
        self.caminho = Path(pasta) / nome
        self.esperar_s = esperar_s
        self.mensagem = mensagem
        self._arquivo = None

    @staticmethod
    def _travar(arquivo) -> None:
        if os.name == "nt":
            import msvcrt
            arquivo.seek(0)
            msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __enter__(self) -> "Trava":
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        arquivo = open(self.caminho, "a+")
        fim = time.monotonic() + self.esperar_s
        while True:
            try:
                self._travar(arquivo)
                break
            except OSError:
                if time.monotonic() >= fim:
                    arquivo.close()
                    raise OcupadoErro(self.mensagem)
                time.sleep(0.05)
        self._arquivo = arquivo
        return self

    def __exit__(self, *exc) -> None:
        if self._arquivo is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._arquivo.seek(0)
                msvcrt.locking(self._arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._arquivo.fileno(), fcntl.LOCK_UN)
        finally:
            self._arquivo.close()
            self._arquivo = None
