"""Etapa 4 — cenários montados pelo usuário (renovação multi-plano)."""

from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    RascunhoEstudo,
)
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html
from newport_app.rascunho.cenarios_sync import (
    cenarios_sincronizados,
    podar_cenarios_orfaos,
    rotulo_cenario,
    sincronizar_cenarios,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.pendencias import pendencias_compilacao
from tests.test_cenarios_contrato_motor import _rascunho_dois_subgrupos, _rascunho_seguro_novo
from tests.test_paridade_matriz_html import (
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
)


def _multi_vazio(n_opcoes: int = 5) -> RascunhoEstudo:
    base = rascunho_demo_12_vidas()
    ops = []
    for i in range(n_opcoes):
        op = deepcopy(base.opcoes_proposta[0])
        op.id = f"op-{i + 1}"
        op.plano_nome = f"Cotação {i + 1}"
        ops.append(op)
    base.opcoes_proposta = ops
    sg2 = deepcopy(base.subgrupos_atuais[0])
    sg2.id = "sg-2"
    sg2.plano_nome = "Plano vigente B"
    base.subgrupos_atuais.append(sg2)
    for i, vida in enumerate(base.vidas):
        if i >= len(base.vidas) // 2:
            vida.subgrupo_atual_id = "sg-2"
    base.cenarios = []
    return base


def _cenario_misto_gabarito(rascunho: RascunhoEstudo) -> CenarioRascunho:
    return CenarioRascunho(
        id="c-misto",
        rotulo=None,
        atribuicoes=[
            AtribuicaoRascunho(
                id="a-sg-a",
                alvo_tipo="subgrupo",
                alvo_id="sg-a",
                opcao_plano_id="op-prata",
            ),
            AtribuicaoRascunho(
                id="a-sg-b",
                alvo_tipo="subgrupo",
                alvo_id="sg-b",
                opcao_plano_id="op-ouro",
            ),
        ],
    )


@pytest.fixture
def repo(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "etapa4.db")


@pytest.fixture
def client(repo: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo, seed_demos=False))


def test_01_multi_sync_nao_cria_cenario_etapa_abre_vazia(repo):
    """2 planos + 5 cotações: sync não pré-preenche (etapa 4 monta o vazio)."""
    rascunho = _multi_vazio(5)
    sincronizar_cenarios(rascunho)
    assert rascunho.cenarios == []
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert salvo.cenarios == []
    assert not cenarios_sincronizados(salvo)
    assert any(p.codigo == "APP-ET4-001" for p in pendencias_compilacao(salvo))


def test_02_cenario_misto_vira_uma_coluna_por_cenario():
    """Cenário misto: uma coluna, e cada grupo com o plano que o cenário lhe deu.

    Reescrito na FASE 3. A versão anterior afirmava o defeito: exigia que a
    coluna do prata trouxesse 610.061 para o sg-b, que recebeu ouro. Era um
    teste protegendo o comportamento errado.
    """
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [_cenario_misto_gabarito(rascunho)]
    assert cenarios_sincronizados(rascunho)
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 1
    coluna = matriz.propostas[0]
    assert coluna.cenario_id == "c-misto"
    assert coluna.plano_nome == "Proposta prata + Proposta ouro"
    por_sg = {s.subgrupo_id: s.proposta_centavos for s in coluna.subgrupos}
    # Valores de gabarito intactos: prata no sg-a, ouro no sg-b.
    assert por_sg["sg-a"] == 2_360_717
    assert por_sg["sg-b"] == 710_988
    # E o que o defeito produzia não aparece em nenhuma célula.
    assert 610_061 not in por_sg.values()
    assert 2_751_249 not in por_sg.values()
    assert coluna.numerico.proposta_mensal_centavos == 2_360_717 + 710_988


def test_03_dois_cenarios_viram_duas_colunas():
    """Dois cenários, duas colunas — sem dedupe por plano.

    Antes, o ouro usado nos dois cenários rendia uma coluna só, e o cenário
    misto desaparecia como cenário. Agora cada cenário é uma coluna.
    """
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    c1 = _cenario_misto_gabarito(rascunho)
    c2 = CenarioRascunho(
        id="c-uniforme-ouro",
        rotulo=None,
        atribuicoes=[
            AtribuicaoRascunho(
                id="a2a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-ouro"
            ),
            AtribuicaoRascunho(
                id="a2b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
            ),
        ],
    )
    rascunho.cenarios = [c1, c2]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 2
    assert [p.cenario_id for p in matriz.propostas] == ["c-misto", "c-uniforme-ouro"]
    misto, uniforme = matriz.propostas
    assert misto.numerico.proposta_mensal_centavos == 2_360_717 + 710_988
    # Cenário uniforme: consolidado igual ao que a coluna por plano dava antes.
    assert uniforme.numerico.proposta_mensal_centavos == 3_462_237
    assert uniforme.plano_nome == "Proposta ouro"
    assert " + " not in uniforme.plano_nome


def test_04_cenario_incompleto_nao_sincroniza_e_pendencia():
    rascunho = _multi_vazio(2)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-inc",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-1",
                    opcao_plano_id="op-1",
                ),
                AtribuicaoRascunho(
                    id="a2",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-2",
                    opcao_plano_id="",
                ),
            ],
        )
    ]
    assert not cenarios_sincronizados(rascunho)
    assert any(p.codigo == "APP-ET4-001" for p in pendencias_compilacao(rascunho))
    faltando = "sg-2"
    assert faltando in {a.alvo_id for a in rascunho.cenarios[0].atribuicoes if not a.opcao_plano_id}


def test_05_matriz_e_documento_usam_nome_do_plano(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [_cenario_misto_gabarito(rascunho)]
    # Etapa 4 ainda deriva rótulo composto do cenário
    assert rotulo_cenario(rascunho, rascunho.cenarios[0]) == "Proposta prata + Proposta ouro"
    matriz, _ = _calcular_matriz(rascunho)
    # Uma coluna por cenário: o rótulo da coluna é o do cenário, e o cenário
    # misto se chama pelos dois planos que o compõem.
    nomes = [p.plano_nome for p in matriz.propostas]
    assert nomes == ["Proposta prata + Proposta ouro"]
    snap = _aprovar(tmp_path, rascunho)
    ids = [p.opcao_id for p in matriz.propostas]
    for modo in ("faixas", "grupo_familiar", "resumo"):
        vm = construir_view_model(snap, modo=modo, propostas_selecionadas=ids)
        html = render_html(vm)
        if modo == "resumo":
            assert "Proposta prata + Proposta ouro" in html
        else:
            assert "Proposta prata" in html
            assert "Proposta ouro" in html
            assert "Proposta prata + Proposta ouro" not in html


def test_05b_linhas_matriz_completas_por_coluna():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    rascunho.cenarios = [_cenario_misto_gabarito(rascunho)]
    matriz, _ = _calcular_matriz(rascunho)
    for prop in matriz.propostas:
        assert prop.acomodacao is not None or prop.operadora
        assert prop.regime_coparticipacao
        assert prop.numerico is not None
        assert prop.numerico.proposta_mensal_centavos is not None
        assert prop.numerico.diff_mes_centavos is not None
        assert prop.numerico.diff_ano_centavos is not None
        assert prop.totais is not None
        assert prop.totais.proposta_mensal_reais
        assert len(prop.subgrupos) == 2
        # Fixture Anistia tem validade; se ausente, o campo fica None sem quebrar.
        assert prop.validade_oficial is None or isinstance(prop.validade_oficial, str)
        assert prop.diferenca_percentual is not None


def test_05c_acomodacao_do_cenario_e_invariante_a_ordem():
    """Acomodação da coluna agrega as atribuições, e a ordem delas não muda nada.

    Este é o teste do §12, adaptado e não substituído. Com coluna = plano a
    acomodação vinha da própria opção; com coluna = cenário ela é agregada, como
    já era a coparticipação. O que o §12 protege continua de pé: reordenar as
    atribuições de um cenário misto não pode mexer no que se exibe.
    """
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
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
            ],
        )
    ]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 1
    # Acomodações divergem entre os grupos: a coluna não escolhe uma das duas.
    assert matriz.propostas[0].acomodacao == "misto"

    rascunho.cenarios[0].atribuicoes.reverse()
    matriz2, _ = _calcular_matriz(rascunho)
    assert len(matriz2.propostas) == 1
    depois = matriz2.propostas[0]
    antes = matriz.propostas[0]
    assert depois.acomodacao == antes.acomodacao
    assert depois.plano_nome == antes.plano_nome
    assert depois.regime_coparticipacao == antes.regime_coparticipacao
    assert (
        depois.numerico.proposta_mensal_centavos
        == antes.numerico.proposta_mensal_centavos
    )
    assert {s.subgrupo_id: s.proposta_centavos for s in depois.subgrupos} == {
        s.subgrupo_id: s.proposta_centavos for s in antes.subgrupos
    }


def test_05c2_rotulo_misto_ordem_pelos_grupos_nao_catalogo():
    """Rótulo misto segue sg-a → sg-b, não a ordem do catálogo da etapa 3."""
    from tests.test_correcao_resumo_regime import _rascunho_anistia_seis

    rascunho = _rascunho_anistia_seis()
    por_id = {op.id: op for op in rascunho.opcoes_proposta}
    # Catálogo invertido: Especial antes de Ouro no JSON da etapa 3.
    rascunho.opcoes_proposta = [
        por_id["op-especial"],
        por_id["op-ouro"],
        por_id["op-bronze"],
        por_id["op-prata"],
        por_id["op-direto"],
        por_id["op-executivo"],
    ]
    cenario = CenarioRascunho(
        id="c-misto",
        atribuicoes=[
            AtribuicaoRascunho(
                id="a1", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-especial"
            ),
            AtribuicaoRascunho(
                id="a2", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-ouro"
            ),
        ],
    )
    rotulo = rotulo_cenario(rascunho, cenario)
    assert rotulo == "OURO MAIS I Q + Especial 100 R1 — Apartamento (Nacional / RJ Capital)"
    cenario.atribuicoes.reverse()
    assert rotulo_cenario(rascunho, cenario) == rotulo


def test_05d_acomodacao_unica_nao_vira_misto():
    """Cenário uniforme: acomodação única, sem «misto»."""
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    for op in rascunho.opcoes_proposta:
        op.acomodacao = "Apartamento"
    rascunho.cenarios = [_cenario_misto_gabarito(rascunho)]
    matriz, _ = _calcular_matriz(rascunho)
    assert matriz.propostas[0].acomodacao == "Apartamento"


def test_06_um_plano_vigente_sync_automatico_sem_etapa4(repo):
    rascunho = rascunho_demo_12_vidas()
    rascunho.cenarios = []
    assert len(rascunho.subgrupos_atuais) == 1
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert cenarios_sincronizados(salvo)
    assert len(salvo.cenarios) == len(salvo.opcoes_proposta)
    assert all(len(c.atribuicoes) == 1 for c in salvo.cenarios)


def test_07_seguro_novo_sync_inalterado(repo):
    rascunho = _rascunho_seguro_novo(12, 2)
    rascunho.cenarios = []
    sincronizar_cenarios(rascunho)
    assert cenarios_sincronizados(rascunho)
    assert len(rascunho.cenarios) == 2
    assert sum(len(c.atribuicoes) for c in rascunho.cenarios) == 24
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo is not None
    assert cenarios_sincronizados(salvo)
    assert all(a.alvo_tipo == "vida" for c in salvo.cenarios for a in c.atribuicoes)


def test_08_cenarios_gravados_permanecem_ao_reabrir(repo):
    rascunho = _rascunho_dois_subgrupos(3)
    ids_antes = [c.id for c in rascunho.cenarios]
    atrib_antes = [
        [(a.alvo_id, a.opcao_plano_id) for a in c.atribuicoes] for c in rascunho.cenarios
    ]
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert [c.id for c in salvo.cenarios] == ids_antes
    assert [
        [(a.alvo_id, a.opcao_plano_id) for a in c.atribuicoes] for c in salvo.cenarios
    ] == atrib_antes


def test_09_snapshot_aprovado_continua_legivel(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    assert snap is not None
    assert snap.payload
    ids = [op.id for op in rascunho.opcoes_proposta]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert vm.secoes_regime
    html = render_html(vm)
    assert "Proposta prata" in html or "prata" in html.lower()


def test_10_grade_paridade_36_celulas():
    from tests.gerador_celulas_estruturais import (
        enumerar_celulas_invalidas,
        enumerar_celulas_totais,
        enumerar_celulas_validas,
        gerar_rascunho,
    )

    assert len(enumerar_celulas_totais()) == 48
    assert len(enumerar_celulas_validas()) == 36
    assert len(enumerar_celulas_invalidas()) == 12
    for celula in enumerar_celulas_validas():
        r = gerar_rascunho(celula)
        assert cenarios_sincronizados(r), celula.nome


def test_11_gabarito_anistia_uniforme_prata():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    prata = next(
        c
        for c in rascunho.cenarios
        if all(a.opcao_plano_id == "op-prata" for a in c.atribuicoes)
    )
    rascunho.cenarios = [prata]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 1
    assert matriz.propostas[0].plano_nome == "Proposta prata"
    por_sg = {s.subgrupo_id: s.proposta_centavos for s in matriz.propostas[0].subgrupos}
    assert por_sg["sg-a"] == 2_360_717
    assert por_sg["sg-b"] == 610_061
    assert matriz.propostas[0].numerico.proposta_mensal_centavos == 2_970_778


def test_11b_anistia_seis_dois_cenarios_duas_colunas():
    """Seis na etapa 3, quatro usados em dois cenários → duas colunas; dois ficam fora."""
    from tests.test_correcao_resumo_regime import _rascunho_anistia_seis

    rascunho = _rascunho_anistia_seis()
    assert len(rascunho.opcoes_proposta) == 6
    # Dois cenários mistos com quatro planos distintos
    ops = [op.id for op in rascunho.opcoes_proposta]
    rascunho.cenarios = [
        CenarioRascunho(
            id="c1",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id=ops[0]
                ),
                AtribuicaoRascunho(
                    id="a1b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id=ops[1]
                ),
            ],
        ),
        CenarioRascunho(
            id="c2",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a2a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id=ops[2]
                ),
                AtribuicaoRascunho(
                    id="a2b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id=ops[3]
                ),
            ],
        ),
    ]
    matriz, _ = _calcular_matriz(rascunho)
    assert len(matriz.propostas) == 2
    assert [p.cenario_id for p in matriz.propostas] == ["c1", "c2"]
    # Cada cenário é misto, então cada coluna se chama pelos dois planos dela.
    assert all(" + " in p.plano_nome for p in matriz.propostas)
    fora = {ops[4], ops[5]}
    assert all(p.opcao_id not in fora for p in matriz.propostas)
    assert any(p.codigo == "APP-ET4-002" for p in matriz.pendencias)
    for prop in matriz.propostas:
        por_sg = {s.subgrupo_id: s.proposta_centavos for s in prop.subgrupos}
        assert por_sg["sg-a"] is not None
        assert por_sg["sg-b"] is not None
        assert prop.numerico.proposta_mensal_centavos == por_sg["sg-a"] + por_sg["sg-b"]


def test_13_estudo_uniforme_gravado_sync_nao_recria_nem_apaga(repo):
    rascunho = _rascunho_dois_subgrupos(2)
    assert len(rascunho.cenarios) == 2
    fingerprint = json.dumps(
        [
            {
                "id": c.id,
                "rotulo": c.rotulo,
                "atribuicoes": [
                    (a.id, a.alvo_id, a.opcao_plano_id) for a in c.atribuicoes
                ],
            }
            for c in rascunho.cenarios
        ],
        sort_keys=True,
    )
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    sincronizar_cenarios(salvo)
    depois = json.dumps(
        [
            {
                "id": c.id,
                "rotulo": c.rotulo,
                "atribuicoes": [
                    (a.id, a.alvo_id, a.opcao_plano_id) for a in c.atribuicoes
                ],
            }
            for c in salvo.cenarios
        ],
        sort_keys=True,
    )
    assert depois == fingerprint


def test_14_cenario_misto_gravado_abre_integro_rotulo_a_mais_b(repo, tmp_path: Path):
    origem = Path(".data/newport_app.db")
    if origem.is_file():
        con = sqlite3.connect(str(origem))
        row = con.execute(
            "SELECT id, payload FROM rascunhos WHERE id IN (?, ?)",
            ("est-629bfca67e", "est-e1862b46be"),
        ).fetchone()
        con.close()
        if row:
            rid, payload = row
            data = json.loads(payload)
            # Isola no banco de teste
            db = tmp_path / "misto.db"
            repo_m = SQLiteStudyRepository(db)
            rascunho = RascunhoEstudo.model_validate(data)
            # Garante rótulo misto presente
            mistos = [
                c
                for c in rascunho.cenarios
                if len({a.opcao_plano_id for a in c.atribuicoes if a.opcao_plano_id}) > 1
            ]
            assert mistos, "estudo lunvox/teste20 deveria ter cenário misto"
            rotulo_antes = mistos[0].rotulo or rotulo_cenario(rascunho, mistos[0])
            assert " + " in rotulo_antes
            repo_m.salvar_rascunho(rascunho)
            salvo = repo_m.obter_rascunho(rascunho.id)
            assert salvo is not None
            mistos_depois = [
                c
                for c in salvo.cenarios
                if len({a.opcao_plano_id for a in c.atribuicoes if a.opcao_plano_id}) > 1
            ]
            assert mistos_depois
            assert (mistos_depois[0].rotulo or rotulo_cenario(salvo, mistos_depois[0])) == rotulo_antes
            return

    # Fallback sintético
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    c = _cenario_misto_gabarito(rascunho)
    c = c.model_copy(update={"rotulo": rotulo_cenario(rascunho, c)})
    assert " + " in c.rotulo
    rascunho.cenarios = [c]
    repo.salvar_rascunho(rascunho)
    salvo = repo.obter_rascunho(rascunho.id)
    assert salvo.cenarios[0].rotulo == c.rotulo
    assert " + " in (salvo.cenarios[0].rotulo or "")


def test_podar_orfaos_remove_atribuicao_sem_apagar_slots_vazios():
    rascunho = _multi_vazio(2)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c1",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-1",
                    opcao_plano_id="op-1",
                ),
                AtribuicaoRascunho(
                    id="a2",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-2",
                    opcao_plano_id="op-gone",
                ),
                AtribuicaoRascunho(
                    id="a3",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-2",
                    opcao_plano_id="",
                ),
            ],
        )
    ]
    # Remover op-gone da seleção (já não está); poda remove só órfão
    podar_cenarios_orfaos(rascunho)
    ops = {a.opcao_plano_id for a in rascunho.cenarios[0].atribuicoes}
    assert "op-gone" not in ops
    assert "" in ops
    assert "op-1" in ops


def _cenario_completo(rascunho: RascunhoEstudo, cid: str, op_a: str, op_b: str) -> CenarioRascunho:
    sgs = [sg.id for sg in rascunho.subgrupos_atuais]
    return CenarioRascunho(
        id=cid,
        atribuicoes=[
            AtribuicaoRascunho(
                id=f"a-{cid}-0",
                alvo_tipo="subgrupo",
                alvo_id=sgs[0],
                opcao_plano_id=op_a,
            ),
            AtribuicaoRascunho(
                id=f"a-{cid}-1",
                alvo_tipo="subgrupo",
                alvo_id=sgs[1],
                opcao_plano_id=op_b,
            ),
        ],
    )


def test_15_cinco_propostas_dois_cenarios_calcula():
    from newport_app.adapters.motor_out import motor_result_para_comparativo
    from newport_app.draft_compiler import compile
    from newport_motor.engine import calcular

    rascunho = _multi_vazio(5)
    rascunho.cenarios = [
        _cenario_completo(rascunho, "c1", "op-1", "op-2"),
        _cenario_completo(rascunho, "c2", "op-3", "op-3"),
    ]
    assert cenarios_sincronizados(rascunho)
    compilado = compile(rascunho)
    assert compilado.compilavel
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    resp = motor_result_para_comparativo(rascunho, motor)
    assert resp.calculo_realizado is True
    assert resp.consistencia.consistente is True
    # Dois cenários, duas colunas. Antes eram três: os planos usados, deduplicados.
    assert len(resp.propostas) == 2
    assert [p.cenario_id for p in resp.propostas] == ["c1", "c2"]
    assert resp.propostas[0].plano_nome == "Cotação 1 + Cotação 2"
    assert resp.propostas[1].plano_nome == "Cotação 3"
    assert resp.consistencia.cenarios_configurados == 2
    assert resp.consistencia.propostas_selecionadas == 5
    assert not any(p.codigo == "APP-CMP-001" for p in resp.pendencias)
    assert any(p.codigo == "APP-ET4-002" for p in resp.pendencias)


def test_16_um_cenario_completo_calcula():
    from newport_app.adapters.motor_out import motor_result_para_comparativo
    from newport_app.draft_compiler import compile
    from newport_motor.engine import calcular

    rascunho = _multi_vazio(5)
    rascunho.cenarios = [_cenario_completo(rascunho, "c1", "op-1", "op-1")]
    compilado = compile(rascunho)
    motor = calcular(compilado.compilado.estudo_input, compilado.compilado.effective_policy)
    resp = motor_result_para_comparativo(rascunho, motor)
    assert resp.calculo_realizado is True
    assert len(resp.propostas) == 1


def test_17_cenario_incompleto_bloqueia_com_lacuna():
    rascunho = _multi_vazio(2)
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-inc",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-1",
                    opcao_plano_id="op-1",
                ),
                AtribuicaoRascunho(
                    id="a2",
                    alvo_tipo="subgrupo",
                    alvo_id="sg-2",
                    opcao_plano_id="",
                ),
            ],
        )
    ]
    assert not cenarios_sincronizados(rascunho)
    pend = pendencias_compilacao(rascunho)
    et4 = next(p for p in pend if p.codigo == "APP-ET4-001")
    assert "Plano vigente B" in et4.descricao or "sg-2" in et4.descricao
    assert "Planos selecionados" not in (et4.acao_sugerida or "")


def test_18_zero_cenarios_bloqueia():
    from newport_app.adapters.motor_out import motor_result_para_comparativo
    from newport_motor.result import MotorResult

    rascunho = _multi_vazio(3)
    assert rascunho.cenarios == []
    assert any(p.codigo == "APP-ET4-001" for p in pendencias_compilacao(rascunho))
    motor = MotorResult(
        estudo_id=rascunho.id,
        cenarios=[],
        validacoes=[],
        politicas_efetivas={},
        bloqueios_abertos=[],
    )
    resp = motor_result_para_comparativo(rascunho, motor)
    assert resp.calculo_realizado is False
    assert resp.consistencia.consistente is False
    assert "Nenhum cenário" in (resp.consistencia.mensagem or "")
    assert "Correspondência" in (resp.consistencia.mensagem or "")

