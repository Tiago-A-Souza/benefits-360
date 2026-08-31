"""Tabela de vidas por faixa ANS × titular/dependente × sexo — etapa 1 (cotação).

Usa o mesmo critério de faixa do motor (`newport_motor.faixa.faixa_em`): idade
completa na data de referência e limites ANS 0–9. Não redefine faixas.

As dez faixas sempre aparecem (zeros inclusos): formulários de operadora
esperam o quadro completo para colagem.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from newport_app.cotacao_pdf.faixas import ROTULOS_FAIXA
from newport_app.models.siscor_import import (
    DisponibilidadeColunasSiscor,
    LinhaSiscorCandidata,
)
from newport_app.siscor_importer.parentesco_contagem import classificar_parentesco_linha
from newport_motor.faixa import faixa_em

ModoSexoTabela = Literal["completo", "sem_sexo", "parcial"]


class LinhaFaixaCotacao(BaseModel):
    faixa: int
    rotulo: str
    tit_m: int | None = None
    tit_f: int | None = None
    dep_m: int | None = None
    dep_f: int | None = None
    titulares: int | None = None
    dependentes: int | None = None
    nao_informado: int | None = None
    sem_parentesco: int = 0
    total: int = 0


class TabelaFaixasCotacao(BaseModel):
    """Quadro para copy-paste no formulário da operadora."""

    modo_sexo: ModoSexoTabela
    data_referencia: date
    aviso_sexo: str | None = None
    linhas: list[LinhaFaixaCotacao] = Field(default_factory=list)
    total_vidas: int = 0
    total_titulares: int = 0
    total_dependentes: int = 0
    total_feminino: int | None = None
    total_masculino: int | None = None
    total_nao_informado: int | None = None
    total_sem_parentesco: int = 0


_AVISO_FORMATO_SEM_SEXO = (
    "Este arquivo não traz a coluna SEXO. A tabela mostra titular e dependente "
    "por faixa, sem cruzamento por sexo. A operadora pode exigir a separação "
    "masculino/feminino — complete o dado na origem ou informe manualmente."
)

_AVISO_SEXO_PARCIAL = (
    "Algumas vidas estão sem sexo preenchido. Elas aparecem na coluna "
    "«Não informado» — ausência não é zero nas colunas M/F."
)


def _sexo_slot(sexo: str | None) -> Literal["m", "f", "ni"]:
    if sexo == "masculino":
        return "m"
    if sexo == "feminino":
        return "f"
    return "ni"


def montar_tabela_faixas_cotacao(
    linhas: list[LinhaSiscorCandidata],
    *,
    data_referencia: date,
    disponibilidade: DisponibilidadeColunasSiscor | None = None,
) -> TabelaFaixasCotacao:
    disp = disponibilidade or DisponibilidadeColunasSiscor()
    ativas = [l for l in linhas if not l.excluida]

    if not disp.sexo:
        modo: ModoSexoTabela = "sem_sexo"
        aviso: str | None = _AVISO_FORMATO_SEM_SEXO
    elif any(l.sexo is None for l in ativas):
        modo = "parcial"
        aviso = _AVISO_SEXO_PARCIAL
    else:
        modo = "completo"
        aviso = None

    # Contadores por faixa: índices 0–9
    tit_m = [0] * 10
    tit_f = [0] * 10
    dep_m = [0] * 10
    dep_f = [0] * 10
    tit = [0] * 10
    dep = [0] * 10
    ni = [0] * 10
    sem = [0] * 10
    tot = [0] * 10

    tot_fem = tot_masc = tot_ni = 0
    tot_tit = tot_dep = tot_sem = 0

    for linha in ativas:
        if not linha.nascimento:
            continue
        try:
            nasc = date.fromisoformat(linha.nascimento)
        except ValueError:
            continue
        _, faixa = faixa_em(nasc, data_referencia)
        if faixa < 0 or faixa > 9:
            continue

        cat = classificar_parentesco_linha(linha)
        tot[faixa] += 1

        if cat == "sem_parentesco":
            sem[faixa] += 1
            tot_sem += 1
            if modo != "sem_sexo":
                ni[faixa] += 1
                tot_ni += 1
            continue

        if cat == "titular":
            tit[faixa] += 1
            tot_tit += 1
        else:
            dep[faixa] += 1
            tot_dep += 1

        if modo == "sem_sexo":
            continue

        slot = _sexo_slot(linha.sexo)
        if slot == "m":
            tot_masc += 1
            if cat == "titular":
                tit_m[faixa] += 1
            else:
                dep_m[faixa] += 1
        elif slot == "f":
            tot_fem += 1
            if cat == "titular":
                tit_f[faixa] += 1
            else:
                dep_f[faixa] += 1
        else:
            ni[faixa] += 1
            tot_ni += 1

    saida: list[LinhaFaixaCotacao] = []
    for i in range(10):
        if modo == "sem_sexo":
            saida.append(
                LinhaFaixaCotacao(
                    faixa=i,
                    rotulo=ROTULOS_FAIXA[i],
                    titulares=tit[i],
                    dependentes=dep[i],
                    sem_parentesco=sem[i],
                    total=tot[i],
                )
            )
        else:
            saida.append(
                LinhaFaixaCotacao(
                    faixa=i,
                    rotulo=ROTULOS_FAIXA[i],
                    tit_m=tit_m[i],
                    tit_f=tit_f[i],
                    dep_m=dep_m[i],
                    dep_f=dep_f[i],
                    nao_informado=ni[i] if modo == "parcial" else None,
                    sem_parentesco=sem[i],
                    total=tot[i],
                )
            )

    return TabelaFaixasCotacao(
        modo_sexo=modo,
        data_referencia=data_referencia,
        aviso_sexo=aviso,
        linhas=saida,
        total_vidas=sum(tot),
        total_titulares=tot_tit,
        total_dependentes=tot_dep,
        total_feminino=tot_fem if modo != "sem_sexo" else None,
        total_masculino=tot_masc if modo != "sem_sexo" else None,
        total_nao_informado=tot_ni if modo == "parcial" else None,
        total_sem_parentesco=tot_sem,
    )


def tabela_para_tsv(tabela: TabelaFaixasCotacao) -> str:
    """Texto TSV pronto para colar em planilha / formulário."""
    if tabela.modo_sexo == "sem_sexo":
        header = ["Faixa", "Titulares", "Dependentes", "Total"]
        rows = [
            [ln.rotulo, str(ln.titulares or 0), str(ln.dependentes or 0), str(ln.total)]
            for ln in tabela.linhas
        ]
    else:
        header = ["Faixa", "Tit. M", "Tit. F", "Dep. M", "Dep. F"]
        if tabela.modo_sexo == "parcial" or (tabela.total_nao_informado or 0) > 0:
            header.append("Não informado")
        header.append("Total")
        rows = []
        for ln in tabela.linhas:
            row = [
                ln.rotulo,
                str(ln.tit_m or 0),
                str(ln.tit_f or 0),
                str(ln.dep_m or 0),
                str(ln.dep_f or 0),
            ]
            if "Não informado" in header:
                row.append(str(ln.nao_informado or 0))
            row.append(str(ln.total))
            rows.append(row)
    lines = ["\t".join(header)]
    lines.extend("\t".join(r) for r in rows)
    return "\n".join(lines) + "\n"
