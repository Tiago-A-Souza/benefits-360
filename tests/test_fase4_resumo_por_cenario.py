"""FASE 4 — coluna_id = cenário e resumo executivo por cenário."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho
from newport_app.presentation.builder import construir_view_model, _propostas_por_id
from newport_app.presentation.colisao_coluna import (
    CODIGO_COLISAO_COLUNA,
    chave_de_coluna,
    colisoes_de_chave_de_coluna,
    resolver_colunas_selecionadas,
)
from newport_app.presentation.html_renderer import render_html
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)

_ESTUDOS_COLISAO = (
    "est-6ec6d7945a",
    "est-629bfca67e",
    "est-e1862b46be",
)


def test_01_tres_estudos_colisao_duas_colunas_no_documento():
    """Os três estudos com primeira atribuição repetida: documento guarda as duas."""
    db = Path("C:/np/.data/newport_app.db")
    if not db.is_file():
        return
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    achados = []
    for eid in _ESTUDOS_COLISAO:
        row = con.execute(
            "SELECT payload FROM rascunhos WHERE id=?", (eid,)
        ).fetchone()
        if row is None:
            continue
        from newport_app.models.draft import RascunhoEstudo

        rascunho = RascunhoEstudo.model_validate(json.loads(row[0]))
        matriz, _ = _calcular_matriz(rascunho)
        calculadas = [p for p in matriz.propostas if p.calculo_realizado]
        assert len(calculadas) == len(rascunho.cenarios)
        chaves = [chave_de_coluna(p) for p in calculadas]
        assert len(chaves) == len(set(chaves))
        assert not colisoes_de_chave_de_coluna(calculadas)
        assert not any(p.codigo == CODIGO_COLISAO_COLUNA for p in matriz.pendencias)
        por = _propostas_por_id(matriz)
        assert len(por) == len(calculadas)
        valores = [p.numerico.proposta_mensal_centavos for p in calculadas if p.numerico]
        assert len(set(valores)) >= 2
        achados.append((eid, len(calculadas), valores))
    assert len(achados) == 3, achados


def test_02_validacao_colisao_existe_como_rede():
    assert CODIGO_COLISAO_COLUNA == "APP-COL-001"
    assert colisoes_de_chave_de_coluna.__module__.endswith("colisao_coluna")


def test_03_mesma_composicao_ordem_diferente_duas_colunas():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-a",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        ),
        CenarioRascunho(
            id="c-b",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="b1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-ouro"
                ),
                AtribuicaoRascunho(
                    id="b2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-prata"
                ),
            ],
        ),
    ]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 2
    assert {chave_de_coluna(p) for p in matriz.propostas} == {"c-a", "c-b"}
    assert matriz.propostas[0].numerico.proposta_mensal_centavos != (
        matriz.propostas[1].numerico.proposta_mensal_centavos
    )


def test_05_cabecalho_misto_e_uniforme(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        ),
        CenarioRascunho(
            id="c-prata",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="b1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="b2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-prata"
                ),
            ],
        ),
    ]
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    assert "Cenário 1" in html
    assert "Proposta prata + Proposta ouro" in html
    assert "Proposta prata" in html
    assert "Cenário 2" not in html
    assert "op-linha" in html
    assert "class='pl'>Cenário 1</span>" in html


def test_06_celula_traz_nome_do_plano_atribuido(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        )
    ]
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["c-misto"]
    )
    html = render_html(vm)
    assert "pl-cel" in html
    assert "Proposta prata" in html
    assert "Proposta ouro" in html
    coluna = vm.secoes_regime[0].propostas[0]
    assert coluna.nomes_atribuidos_por_subgrupo["sg-a"] == "Proposta prata"
    assert coluna.nomes_atribuidos_por_subgrupo["sg-b"] == "Proposta ouro"
    assert coluna.subtotais_por_subgrupo["sg-a"] == 2_360_717
    assert coluna.subtotais_por_subgrupo["sg-b"] == 710_988
    assert coluna.total_mensal_centavos == 2_360_717 + 710_988


def test_08_inverter_ordem_nao_muda_resumo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    for op in rascunho.opcoes_proposta:
        if op.id == "op-prata":
            op.acomodacao = "Apartamento"
        elif op.id == "op-ouro":
            op.acomodacao = "Enfermaria"
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        )
    ]
    matriz, _ = _calcular_matriz(rascunho)
    rascunho.cenarios[0].atribuicoes.reverse()
    matriz2, _ = _calcular_matriz(rascunho)
    assert matriz.propostas[0].acomodacao == matriz2.propostas[0].acomodacao == "misto"
    assert (
        matriz.propostas[0].numerico.proposta_mensal_centavos
        == matriz2.propostas[0].numerico.proposta_mensal_centavos
    )
    assert matriz.propostas[0].plano_nome == matriz2.propostas[0].plano_nome


def test_09_resumo_mantem_todas_as_linhas(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    ids = [chave_de_coluna(p) for p in matriz.propostas]
    html = render_html(
        construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    )
    for rotulo in (
        "Acomodação",
        "Coparticipação",
        "Custo total mensal",
        "Diferença mensal",
        "Diferença anual",
        "Validade da cotação",
        "Consolidado",
    ):
        assert rotulo in html


def test_04_selecoes_gravadas_continuam_abrindo():
    """Todo estudo com selecao_apresentacao gravada continua abrindo.

    A quantidade é a do banco neste momento — não um censo congelado.
    Um deles (est-6d06b1bc26) não calcula — zero cenários, já bloqueava.
    Abrir = carregar o rascunho e resolver a seleção sem apagá-la.
    """
    from newport_app.models.draft import RascunhoEstudo
    from newport_app.services.comparativo_ui import sanitizar_selecao_apresentacao

    db = Path("C:/np/.data/newport_app.db")
    if not db.is_file():
        return
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    n = 0
    for _eid, payload in con.execute("SELECT id, payload FROM rascunhos"):
        rascunho = RascunhoEstudo.model_validate(json.loads(payload))
        sel = rascunho.selecao_apresentacao
        if not sel or not (sel.opcao_ids or sel.ordem):
            continue
        n += 1
        gravados = list(sel.ordem or sel.opcao_ids)
        sanitizar_selecao_apresentacao(rascunho)
        assert rascunho.selecao_apresentacao is not None
        assert rascunho.selecao_apresentacao.opcao_ids or rascunho.selecao_apresentacao.ordem
        resolver_colunas_selecionadas(gravados, [])
    assert n > 0


def test_07_consolidado_misto_numeros_da_reuniao():
    """R$ 23.906,72 + R$ 20.418,04 = R$ 44.324,76 — células reais do estudo da reunião."""
    assert 2_390_672 + 2_041_804 == 4_432_476
    db = Path("C:/np/.data/newport_app.db")
    con = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    ouro_s750 = diamante_one = None
    for payload, in con.execute("SELECT payload FROM snapshots"):
        if "2390672" not in payload or "2041804" not in payload:
            continue
        comp = json.loads(payload).get("comparativo") or {}
        for p in comp.get("propostas") or []:
            for s in p.get("subgrupos") or []:
                if s.get("proposta_centavos") == 2_390_672:
                    ouro_s750 = s
                if s.get("proposta_centavos") == 2_041_804:
                    diamante_one = s
    assert ouro_s750 is not None and diamante_one is not None
    assert ouro_s750["proposta_centavos"] + diamante_one["proposta_centavos"] == 4_432_476


def test_fallback_selecao_por_opcao_id():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-uniforme",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-prata"
                ),
            ],
        ),
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="b1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="b2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        ),
    ]
    matriz, _ = _calcular_matriz(rascunho)
    resolvidos = resolver_colunas_selecionadas(["op-prata"], matriz.propostas)
    assert set(resolvidos) == {"c-uniforme", "c-misto"}


def test_10_nome_misto_quebra_em_linhas_alinhadas():
    from newport_app.presentation.tabela_densa import html_linhas_nome_plano

    unico = html_linhas_nome_plano("PRATA MAIS I Q")
    assert unico == "PRATA MAIS I Q"
    misto = html_linhas_nome_plano("PRATA MAIS I Q + DIAMANTE MAIS I Q")
    assert "op-linha" in misto
    assert "PRATA MAIS I Q" in misto
    assert "DIAMANTE MAIS I Q" in misto
    assert misto.index("PRATA MAIS I Q") < misto.index("DIAMANTE MAIS I Q")
