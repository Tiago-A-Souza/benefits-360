"""Qual versão do código a tela está rodando, e se o código no disco ficou mais novo depois que ela abriu.

O Python só lê o código quando a tela abre: mudou um arquivo .py (ou o commit) com a tela aberta, ela continua
rodando o antigo até ser reiniciada. A tela mostra o commit no rodapé e avisa quando é preciso reiniciar.
Os arquivos da página (JavaScript, CSS) não entram: o servidor sempre os lê do disco.
"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PASTAS_DO_CODIGO = ("app", "nucleo", "operadoras")
ARQUIVOS_DO_CODIGO = ("main.py",)


def _git(raiz: Path, *args: str) -> str | None:
    try:
        r = subprocess.run(["git", "-C", str(raiz), *args], capture_output=True, text=True, timeout=5,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except (OSError, subprocess.SubprocessError):
        return None                       # sem git (ex.: a pasta veio num .zip): fica só a data dos arquivos
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def commit(raiz: Path = RAIZ) -> dict | None:
    """O commit do disco: {"id": "abc1234", "quando": "06/11 18:20"}; None sem git."""
    saida = _git(raiz, "log", "-1", "--format=%h|%cd", "--date=format:%d/%m %H:%M")
    if not saida or "|" not in saida:
        return None
    ident, quando = saida.split("|", 1)
    return {"id": ident, "quando": quando}


def ultima_mudanca(raiz: Path = RAIZ, pastas=PASTAS_DO_CODIGO, arquivos=ARQUIVOS_DO_CODIGO) -> float:
    """A data do arquivo .py mais novo do código (pega também mudanças que ainda não viraram commit)."""
    datas = [0.0]
    for pasta in pastas:
        for arq in (raiz / pasta).rglob("*.py"):
            try:
                datas.append(arq.stat().st_mtime)
            except OSError:
                pass
    for nome in arquivos:
        try:
            datas.append((raiz / nome).stat().st_mtime)
        except OSError:
            pass
    return max(datas)


class VersaoDoCodigo:
    """Guarda o que estava no disco quando a tela abriu e compara com o disco de agora (no máximo a cada 15 s)."""

    INTERVALO_S = 15.0

    def __init__(self, raiz: Path = RAIZ, pastas=PASTAS_DO_CODIGO, arquivos=ARQUIVOS_DO_CODIGO):
        self._raiz, self._pastas, self._arquivos = Path(raiz), pastas, arquivos
        self.commit = commit(self._raiz)
        self.mudanca = ultima_mudanca(self._raiz, pastas, arquivos)
        self._conferido_em = 0.0
        self._mais_novo = False

    def mais_novo_no_disco(self) -> bool:
        if self._mais_novo:
            return True                   # o servidor não volta a ficar atualizado sem reiniciar
        agora = time.monotonic()
        if agora - self._conferido_em < self.INTERVALO_S:
            return False
        self._conferido_em = agora
        disco = commit(self._raiz)
        self._mais_novo = (bool(disco and self.commit and disco["id"] != self.commit["id"])
                           or ultima_mudanca(self._raiz, self._pastas, self._arquivos) > self.mudanca)
        return self._mais_novo

    def situacao(self) -> dict:
        return {"commit": (self.commit or {}).get("id"), "quando": (self.commit or {}).get("quando"),
                "mais_novo_no_disco": self.mais_novo_no_disco()}
