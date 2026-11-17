"""Prazo de retenção (playbook): apaga arquivos do robô com mais de N dias.

Apaga só o que o robô guarda para si dentro da pasta de saída: PDFs da pasta pdfs/, prints e HTML
da calibragem (mapa/) e logs (logs/). Nunca toca na pasta do cliente (pasta_destino), no registro
que impede reemissão (estado.json), na planilha resultados.xlsx nem na sessão do navegador.
"""
from __future__ import annotations

import time
from pathlib import Path

PASTAS_COM_PRAZO = {"logs", "mapa", "pdfs"}


def limpar(pasta_saida: str | Path, dias: int | None, log=None) -> int:
    """Apaga os arquivos vencidos e devolve quantos apagou. dias vazio ou 0 desliga a limpeza."""
    if not dias or int(dias) <= 0:
        return 0
    raiz = Path(pasta_saida)
    if not raiz.exists():
        return 0
    limite = time.time() - int(dias) * 86400
    apagados = 0
    for pasta in [p for p in raiz.rglob("*") if p.is_dir() and p.name in PASTAS_COM_PRAZO]:
        if "perfil_navegador" in pasta.parts:
            continue
        for arquivo in pasta.rglob("*"):
            try:
                if arquivo.is_file() and arquivo.stat().st_mtime < limite:
                    arquivo.unlink()
                    apagados += 1
            except OSError:
                pass   # arquivo aberto em outro programa: fica para a próxima
        for sub in sorted((p for p in pasta.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            try:
                sub.rmdir()   # só some se estiver vazia
            except OSError:
                pass
    if apagados and log:
        log.info(f"Prazo de retenção ({dias} dias): {apagados} arquivo(s) antigo(s) do robô apagado(s).")
    return apagados
