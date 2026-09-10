"""FASE 2 — os estudos com cenários gravados não ganham bloqueio novo.

`APP-GRP-001` é bloqueante. Nenhum estudo anterior à FASE 1 tem seleção por
grupo, então todos os grupos herdam o catálogo e toda atribuição existente
continua válida. Este script prova isso no banco, um estudo por vez.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from newport_app.draft_compiler.selecao_validation import validar_atribuicoes_na_selecao
from newport_app.models.draft import RascunhoEstudo
from newport_app.rascunho.selecao_grupo import tem_selecao_propria

DB = Path(".data/newport_app.db")


def main() -> int:
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    linhas = conn.execute("SELECT id, payload FROM rascunhos").fetchall()
    conn.close()

    com_cenarios = 0
    atribuicoes = 0
    com_selecao_propria = 0
    bloqueados: list[str] = []

    for estudo_id, payload in linhas:
        rascunho = RascunhoEstudo.model_validate(json.loads(payload))
        if not rascunho.cenarios:
            continue
        com_cenarios += 1
        atribuicoes += sum(len(c.atribuicoes) for c in rascunho.cenarios)
        if any(tem_selecao_propria(rascunho, sg.id) for sg in rascunho.subgrupos_atuais):
            com_selecao_propria += 1
        erros = validar_atribuicoes_na_selecao(rascunho)
        if erros:
            bloqueados.append(f"{estudo_id}: {len(erros)} — {erros[0].mensagem}")

    print(f"ESTUDOS_COM_CENARIOS={com_cenarios}")
    print(f"ATRIBUICOES_VERIFICADAS={atribuicoes}")
    print(f"COM_SELECAO_PROPRIA_POR_GRUPO={com_selecao_propria}")
    print(f"BLOQUEIOS_NOVOS_APP_GRP_001={len(bloqueados)}")
    for linha in bloqueados[:10]:
        print(f"  {linha}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
