"""FASE 2 — a etapa 4 respeita a seleção por grupo, e a validação que faltava.

Antes desta fase nada verificava que a cotação atribuída a um grupo estivesse
entre as escolhidas para ele: `APP-STR-002` e `B-05` só exigem existência no
catálogo. `APP-GRP-001` é essa trava.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from newport_app.draft_compiler import compile as compilar
from newport_app.draft_compiler.selecao_validation import validar_atribuicoes_na_selecao
from newport_app.rascunho.selecao_grupo import definir_selecao_do_subgrupo
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.matriz_estimativa import montar_matriz_estimativa
from newport_app.services.pendencias import pendencias_compilacao
from newport_app.services.resumo_plano_atual import montar_resumo_plano_atual
from newport_app.services.selecao_grupo import montar_selecao_por_grupo
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_selecao_planos_por_grupo import _cenario, _rascunho

_SG_A = "sg-a"
_SG_B = "sg-b"


def _ids_do_grupo(rascunho, subgrupo_id: str) -> list[str]:
    """O que o dropdown daquele grupo oferece: os pares que a matriz calculou."""
    matriz = montar_matriz_estimativa(rascunho)
    return [c.opcao_id for c in matriz.celulas if c.subgrupo_id == subgrupo_id]


def _anistia_com_selecao(tres: int = 3, dois: int = 2):
    r = _rascunho_anistia_seis()
    ids = [op.id for op in r.opcoes_proposta]
    definir_selecao_do_subgrupo(r, _SG_A, ids[:tres])
    definir_selecao_do_subgrupo(r, _SG_B, ids[tres : tres + dois])
    return r, ids


# ---------------------------------------------------------------------------
# O dropdown
# ---------------------------------------------------------------------------


def test_01_dropdown_de_cada_grupo_lista_so_o_que_foi_escolhido_para_ele():
    r, ids = _anistia_com_selecao()
    assert _ids_do_grupo(r, _SG_A) == ids[:3]
    assert _ids_do_grupo(r, _SG_B) == ids[3:5]


def test_02_plano_escolhido_nos_dois_grupos_aparece_nos_dois_dropdowns():
    r = _rascunho_anistia_seis()
    ids = [op.id for op in r.opcoes_proposta]
    definir_selecao_do_subgrupo(r, _SG_A, [ids[0], ids[1]])
    definir_selecao_do_subgrupo(r, _SG_B, [ids[1], ids[2]])

    assert ids[1] in _ids_do_grupo(r, _SG_A)
    assert ids[1] in _ids_do_grupo(r, _SG_B)


def test_03_grupo_sem_selecao_propria_lista_o_catalogo_inteiro():
    r = _rascunho_anistia_seis()
    ids = [op.id for op in r.opcoes_proposta]
    definir_selecao_do_subgrupo(r, _SG_A, ids[:2])

    assert _ids_do_grupo(r, _SG_A) == ids[:2]
    assert _ids_do_grupo(r, _SG_B) == ids


def test_04_diferenca_ao_lado_e_a_daquele_grupo():
    """A restrição não mexeu no número: mesma composição de antes, por grupo."""
    r, _ = _anistia_com_selecao()
    resumo = montar_resumo_plano_atual(r)
    referencias = {p.subgrupo_id: p.referencia_comparativo_centavos for p in resumo.planos}
    matriz = montar_matriz_estimativa(r)

    vistos = set()
    for cel in matriz.celulas:
        if cel.diff_centavos is None:
            continue
        esperado = cel.estimado_centavos - referencias[cel.subgrupo_id]
        assert cel.diff_centavos == esperado
        vistos.add(cel.subgrupo_id)
    assert vistos == {_SG_A, _SG_B}

    # O mesmo plano difere entre os grupos — é o ponto da comparação por grupo.
    comum = _rascunho_anistia_seis()
    ids = [op.id for op in comum.opcoes_proposta]
    definir_selecao_do_subgrupo(comum, _SG_A, [ids[0]])
    definir_selecao_do_subgrupo(comum, _SG_B, [ids[0]])
    celulas = {c.subgrupo_id: c for c in montar_matriz_estimativa(comum).celulas}
    assert celulas[_SG_A].diff_centavos != celulas[_SG_B].diff_centavos


def test_05_estimativa_calcula_so_os_pares_que_interessam():
    """6 planos × 2 grupos: 12 células antes, 5 com 3 e 2 escolhidos."""
    sem_selecao = _rascunho_anistia_seis()
    assert len(sem_selecao.opcoes_proposta) == 6
    assert len(montar_matriz_estimativa(sem_selecao).celulas) == 12

    com_selecao, _ = _anistia_com_selecao()
    assert len(montar_matriz_estimativa(com_selecao).celulas) == 5


def test_05b_tela_da_etapa_3_continua_vendo_todos_os_pares():
    """Lá o operador ainda está decidindo; restringir esconderia o valor."""
    r, _ = _anistia_com_selecao()
    assert len(montar_matriz_estimativa(r, restrita=False).celulas) == 12
    for grupo in montar_selecao_por_grupo(r).grupos:
        assert len(grupo.planos) == 6
        assert any(p.estimado_centavos is not None for p in grupo.planos)


# ---------------------------------------------------------------------------
# A validação
# ---------------------------------------------------------------------------


def test_06_atribuicao_fora_da_selecao_bloqueia_dizendo_qual():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-1", ["op-2", "op-3"])

    erros = validar_atribuicoes_na_selecao(r)

    assert len(erros) == 1
    erro = erros[0]
    assert erro.codigo == "APP-GRP-001"
    assert erro.severidade == "bloqueante"
    assert erro.caminho == "/cenarios/0/atribuicoes/0/opcao_plano_id"
    assert "AMIL S750 - Apto." in erro.mensagem  # qual grupo
    assert "Plano A" in erro.mensagem  # qual plano
    # Qual cenário: o mesmo rótulo que a etapa 4 mostra na tela.
    assert "No cenário «Plano A + Plano D»" in erro.mensagem


def test_06b_bloqueio_impede_a_compilacao():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-1", ["op-2"])

    resultado = compilar(r)

    assert resultado.compilado is None
    assert any(e.codigo == "APP-GRP-001" for e in resultado.erros)


def test_07_grupo_sem_selecao_propria_aceita_qualquer_plano_do_catalogo():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    assert validar_atribuicoes_na_selecao(r) == []

    # Basta um grupo ter escolha própria para ele ser cobrado; o outro não.
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4"])
    assert validar_atribuicoes_na_selecao(r) == []


def test_08_estudo_no_formato_anterior_a_fase_1_nao_ganha_bloqueio():
    """Sem seleção por grupo, todo grupo herda o catálogo — é o caso dos 58."""
    r = _rascunho()
    _cenario(r, sg1="op-5", sg2="op-3")
    assert r.selecao_planos_por_grupo == []
    assert validar_atribuicoes_na_selecao(r) == []


def test_09_b06_continua_exigindo_atribuicao_completa():
    """A validação nova é adicional; não afrouxa a que já existia."""
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4"])
    _cenario(r, sg1="op-1", sg2=None)

    assert validar_atribuicoes_na_selecao(r) == []
    resultado = compilar(r)
    assert resultado.compilado is None


def test_10_mudar_a_selecao_depois_avisa_e_bloqueia_sem_podar(tmp_path: Path):
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    repo = SQLiteStudyRepository(tmp_path / "muda.db")
    repo.salvar_rascunho(r)

    # A troca é gravada sem erro: op-1 continua no catálogo por causa do sg-2.
    gravado = repo.obter_rascunho("est-fase1")
    definir_selecao_do_subgrupo(gravado, "sg-1", ["op-2", "op-3"])
    repo.salvar_rascunho(gravado)

    depois = repo.obter_rascunho("est-fase1")
    atribs = [(a.alvo_id, a.opcao_plano_id) for a in depois.cenarios[0].atribuicoes]
    assert atribs == [("sg-1", "op-1"), ("sg-2", "op-4")]  # nada foi podado
    assert {op.id for op in depois.opcoes_proposta} == {f"op-{i}" for i in range(1, 6)}

    erros = validar_atribuicoes_na_selecao(depois)
    assert [e.codigo for e in erros] == ["APP-GRP-001"]
    assert "Plano A" in erros[0].mensagem


def test_10b_nenhum_plano_substituto_e_sugerido():
    """A mensagem aponta o problema e devolve a decisão; não escolhe por ninguém."""
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-1", ["op-2", "op-3"])

    mensagem = validar_atribuicoes_na_selecao(r)[0].mensagem
    assert "Plano B" not in mensagem
    assert "Plano C" not in mensagem


def test_pendencia_chega_a_tela_sem_perder_o_detalhe():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-1", ["op-2"])

    item = next(p for p in pendencias_compilacao(r) if p.codigo == "APP-GRP-001")

    assert item.tipo == "bloqueio"
    assert item.etapa == 4
    assert "AMIL S750 - Apto." in item.descricao
    assert "Plano A" in item.descricao


def test_16_estudo_de_um_plano_vigente_nao_ganha_restricao():
    r = _rascunho(dois_grupos=False)
    assert _ids_do_grupo(r, "sg-1") == [op.id for op in r.opcoes_proposta]
    assert validar_atribuicoes_na_selecao(r) == []
    assert len(montar_selecao_por_grupo(r).grupos) == 1


@pytest.mark.parametrize("restrita", [True, False])
def test_matriz_nao_muta_o_rascunho(restrita: bool):
    r, _ = _anistia_com_selecao()
    antes = r.model_dump_json()
    montar_matriz_estimativa(r, restrita=restrita)
    assert r.model_dump_json() == antes
