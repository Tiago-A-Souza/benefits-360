"""FASE 1 — seleção de planos por grupo de beneficiários.

A regra que sustenta tudo é de leitura: subgrupo sem entrada própria vale como
«todo o catálogo». É isso que mantém os 93 rascunhos e os 58 com cenário
funcionando sem migração de dados.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
    OpcaoPropostaRascunho,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.rascunho.selecao_grupo import (
    definir_selecao_do_subgrupo,
    opcoes_do_subgrupo,
    sanear_selecao_por_grupo,
    tem_selecao_propria,
    uniao_das_selecoes,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.selecao_grupo import (
    SelecaoRemocaoExigeConfirmacaoError,
    aplicar_selecao_do_grupo,
    montar_selecao_por_grupo,
)
from newport_app.siscor_mapper.apply import rascunho_vazio

_PLANO_A = "AMIL S750 - Apto."
_PLANO_B = "AMIL ONE S2500 - Apto."


def _rascunho(*, dois_grupos: bool = True, n_opcoes: int = 5):
    r = rascunho_vazio("est-fase1", "Estudo de teste")
    r.regimes_copart.append(RegimeCopartRascunho(id="regime-sem", tipo="sem"))
    r.subgrupos_atuais.append(
        SubgrupoAtualRascunho(id="sg-1", operadora="Amil", plano_nome=_PLANO_A)
    )
    r.vidas.append(
        VidaRascunho(
            id="v-1", nome="Vida 1", nascimento=date(1990, 1, 1), subgrupo_atual_id="sg-1"
        )
    )
    if dois_grupos:
        r.subgrupos_atuais.append(
            SubgrupoAtualRascunho(id="sg-2", operadora="Amil", plano_nome=_PLANO_B)
        )
        r.vidas.append(
            VidaRascunho(
                id="v-2",
                nome="Vida 2",
                nascimento=date(1985, 1, 1),
                subgrupo_atual_id="sg-2",
            )
        )
    for i in range(n_opcoes):
        r.opcoes_proposta.append(
            OpcaoPropostaRascunho(
                id=f"op-{i + 1}",
                operadora="Porto Seguro",
                plano_nome=f"Plano {chr(65 + i)}",
                regime_copart_id="regime-sem",
                tipo_fiscal="seguradora",
            )
        )
    return r


def _cenario(r, *, sg1: str, sg2: str | None) -> None:
    atribs = [
        AtribuicaoRascunho(
            id="atr-1", alvo_tipo="subgrupo", alvo_id="sg-1", opcao_plano_id=sg1
        )
    ]
    if sg2:
        atribs.append(
            AtribuicaoRascunho(
                id="atr-2", alvo_tipo="subgrupo", alvo_id="sg-2", opcao_plano_id=sg2
            )
        )
    r.cenarios.append(CenarioRascunho(id="cen-1", nome="Cenário", atribuicoes=atribs))


# ---------------------------------------------------------------------------
# 1 a 4 — o campo e a derivação
# ---------------------------------------------------------------------------


def test_01_selecoes_dos_dois_grupos_coexistem():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2", "op-3"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    assert opcoes_do_subgrupo(r, "sg-1") == ["op-1", "op-2", "op-3"]
    assert opcoes_do_subgrupo(r, "sg-2") == ["op-4", "op-5"]
    assert len(r.selecao_planos_por_grupo) == 2


def test_02_opcoes_proposta_e_a_uniao_sem_duplicata():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2", "op-3"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])
    assert uniao_das_selecoes(r) == ["op-1", "op-2", "op-3", "op-4", "op-5"]

    # Mesmo plano nos dois grupos entra uma vez só.
    definir_selecao_do_subgrupo(r, "sg-2", ["op-3", "op-4", "op-5"])
    assert uniao_das_selecoes(r) == ["op-1", "op-2", "op-3", "op-4", "op-5"]


def test_03_desmarcar_no_grupo_a_nao_afeta_o_grupo_b():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-1", "op-2"])

    definir_selecao_do_subgrupo(r, "sg-1", ["op-2"])

    assert opcoes_do_subgrupo(r, "sg-1") == ["op-2"]
    assert opcoes_do_subgrupo(r, "sg-2") == ["op-1", "op-2"]


def test_04_grupo_sem_entrada_herda_o_catalogo_inteiro():
    r = _rascunho()
    assert not tem_selecao_propria(r, "sg-1")
    assert opcoes_do_subgrupo(r, "sg-1") == ["op-1", "op-2", "op-3", "op-4", "op-5"]

    # Entrada vazia é diferente de ausência de entrada.
    definir_selecao_do_subgrupo(r, "sg-1", [])
    assert tem_selecao_propria(r, "sg-1")
    assert opcoes_do_subgrupo(r, "sg-1") == []
    assert opcoes_do_subgrupo(r, "sg-2") == ["op-1", "op-2", "op-3", "op-4", "op-5"]


def test_04e_atribuir_pdf_ao_grupo_a_nao_herda_no_b():
    from newport_app.rascunho.selecao_grupo import atribui_planos_do_pdf_ao_grupo

    r = _rascunho()
    for op in r.opcoes_proposta:
        if op.id in ("op-1", "op-2"):
            op.extracao_id = "ext-1"
            op.extracao_opcao_id = op.id

    atribui_planos_do_pdf_ao_grupo(r, "sg-1", "ext-1", ["op-1", "op-2"])

    assert opcoes_do_subgrupo(r, "sg-1") == ["op-1", "op-2"]
    assert tem_selecao_propria(r, "sg-2")
    assert opcoes_do_subgrupo(r, "sg-2") == []


def test_04f_segundo_grupo_escolhe_outros_planos_do_mesmo_pdf():
    from newport_app.rascunho.selecao_grupo import atribui_planos_do_pdf_ao_grupo

    r = _rascunho()
    for op in r.opcoes_proposta[:4]:
        op.extracao_id = "ext-1"
        op.extracao_opcao_id = op.id

    atribui_planos_do_pdf_ao_grupo(r, "sg-1", "ext-1", ["op-1", "op-2"])
    atribui_planos_do_pdf_ao_grupo(r, "sg-2", "ext-1", ["op-3", "op-4"])

    assert opcoes_do_subgrupo(r, "sg-1") == ["op-1", "op-2"]
    assert opcoes_do_subgrupo(r, "sg-2") == ["op-3", "op-4"]


def test_04b_grupo_sem_entrada_impede_a_uniao_de_podar():
    """Com um grupo herdando o catálogo, a união nunca fica menor que ele."""
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1"])
    assert not tem_selecao_propria(r, "sg-2")
    assert uniao_das_selecoes(r) == ["op-1", "op-2", "op-3", "op-4", "op-5"]


def test_04c_uniao_sem_nenhuma_entrada_e_o_catalogo():
    r = _rascunho()
    assert uniao_das_selecoes(r) == [op.id for op in r.opcoes_proposta]


def test_04d_saneamento_descarta_plano_que_saiu_do_catalogo():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2"])
    r.opcoes_proposta = [op for op in r.opcoes_proposta if op.id != "op-2"]

    sanear_selecao_por_grupo(r)

    assert opcoes_do_subgrupo(r, "sg-1") == ["op-1"]


# ---------------------------------------------------------------------------
# A poda passa pela porta da FASE 0
# ---------------------------------------------------------------------------


def test_poda_que_derruba_cenario_exige_confirmacao():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    # sg-1 fica só com op-2: op-1 e op-3 saem de todos os grupos.
    with pytest.raises(SelecaoRemocaoExigeConfirmacaoError) as exc:
        aplicar_selecao_do_grupo(r, "sg-1", ["op-2"])

    impacto = exc.value.impacto
    assert impacto.planos_removidos == ["Plano A", "Plano C"]
    assert [a.plano for a in impacto.atribuicoes_desfeitas] == ["Plano A"]
    assert impacto.cenarios_incompletos[0].alvos_sem_atribuicao == [_PLANO_A]

    # Nada foi gravado.
    assert not tem_selecao_propria(r, "sg-1")
    assert len(r.opcoes_proposta) == 5
    assert len(r.cenarios[0].atribuicoes) == 2


def test_poda_confirmada_remove_do_catalogo_e_poda_atribuicao():
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    impacto = aplicar_selecao_do_grupo(r, "sg-1", ["op-2"], confirmar_remocoes=True)

    assert impacto.planos_removidos == ["Plano A", "Plano C"]
    assert {op.id for op in r.opcoes_proposta} == {"op-2", "op-4", "op-5"}
    restantes = [a.opcao_plano_id for a in r.cenarios[0].atribuicoes]
    assert restantes == ["op-4"]


def test_poda_sem_cenario_envolvido_nao_pede_confirmacao():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    impacto = aplicar_selecao_do_grupo(r, "sg-1", ["op-1", "op-2"])

    assert impacto.planos_removidos == ["Plano C"]
    assert impacto.exige_confirmacao is False
    assert {op.id for op in r.opcoes_proposta} == {"op-1", "op-2", "op-4", "op-5"}


def test_selecao_que_nao_poda_nada_nao_relata_remocao():
    r = _rascunho()
    impacto = aplicar_selecao_do_grupo(r, "sg-1", ["op-1", "op-2"])
    assert impacto.houve_remocao is False
    assert len(r.opcoes_proposta) == 5


# ---------------------------------------------------------------------------
# 8 a 11 — o que a tela recebe
# ---------------------------------------------------------------------------


def test_08_grupos_com_nome_vidas_e_contagem_de_escolhidos():
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2", "op-3"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    resp = montar_selecao_por_grupo(r)

    assert [g.plano_nome for g in resp.grupos] == [_PLANO_A, _PLANO_B]
    assert [g.quantidade_beneficiarios for g in resp.grupos] == [1, 1]
    assert [g.escolhidos for g in resp.grupos] == [3, 2]
    assert resp.total_catalogo == 5


def test_08b_todos_os_planos_aparecem_nos_dois_grupos():
    """O que muda de grupo para grupo é quais estão marcados, não quais existem."""
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2", "op-3"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])

    resp = montar_selecao_por_grupo(r)

    for grupo in resp.grupos:
        assert len(grupo.planos) == 5
    marcados_a = {p.opcao_id for p in resp.grupos[0].planos if p.escolhido}
    marcados_b = {p.opcao_id for p in resp.grupos[1].planos if p.escolhido}
    assert marcados_a == {"op-1", "op-2", "op-3"}
    assert marcados_b == {"op-4", "op-5"}


def test_10_estudo_de_um_plano_vigente_tem_um_grupo_so():
    """Sem segundo grupo não há aba: a tela nova não se aplica."""
    r = _rascunho(dois_grupos=False)
    resp = montar_selecao_por_grupo(r)
    assert len(resp.grupos) == 1


def test_11_grupo_sem_entrada_chega_na_tela_com_tudo_marcado():
    r = _rascunho()
    resp = montar_selecao_por_grupo(r)
    for grupo in resp.grupos:
        assert grupo.selecao_propria is False
        assert grupo.escolhidos == 5
        assert all(p.escolhido for p in grupo.planos)


# ---------------------------------------------------------------------------
# 6 — estudo antigo com cenários abre sem erro e as atribuições seguem válidas
# ---------------------------------------------------------------------------


def test_06_estudo_antigo_com_cenarios_abre_e_mantem_atribuicoes(tmp_path: Path):
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    repo = SQLiteStudyRepository(tmp_path / "antigo.db")
    repo.salvar_rascunho(r)

    lido = repo.obter_rascunho("est-fase1")

    assert lido is not None
    assert lido.selecao_planos_por_grupo == []
    assert opcoes_do_subgrupo(lido, "sg-1") == [op.id for op in lido.opcoes_proposta]
    atribs = [(a.alvo_id, a.opcao_plano_id) for a in lido.cenarios[0].atribuicoes]
    assert atribs == [("sg-1", "op-1"), ("sg-2", "op-4")]


def test_06b_selecao_sobrevive_ao_ciclo_de_gravacao(tmp_path: Path):
    r = _rascunho()
    definir_selecao_do_subgrupo(r, "sg-1", ["op-1", "op-2"])
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4"])
    repo = SQLiteStudyRepository(tmp_path / "ciclo.db")
    repo.salvar_rascunho(r)

    lido = repo.obter_rascunho("est-fase1")

    assert opcoes_do_subgrupo(lido, "sg-1") == ["op-1", "op-2"]
    assert opcoes_do_subgrupo(lido, "sg-2") == ["op-4"]


# ---------------------------------------------------------------------------
# Contrato HTTP
# ---------------------------------------------------------------------------


def _client(tmp_path: Path, rascunho) -> tuple[TestClient, SQLiteStudyRepository]:
    repo = SQLiteStudyRepository(tmp_path / "api.db")
    repo.salvar_rascunho(rascunho)
    return TestClient(create_app(repo=repo, seed_demos=False)), repo


def test_endpoint_get_e_put_gravam_por_grupo(tmp_path: Path):
    client, repo = _client(tmp_path, _rascunho())
    url = "/api/estudos/est-fase1/selecao-planos-grupo"

    resp = client.get(url)
    assert resp.status_code == 200
    assert len(resp.json()["grupos"]) == 2

    resp = client.put(url, json={"subgrupo_id": "sg-1", "opcao_ids": ["op-1", "op-2"]})
    assert resp.status_code == 200
    grupos = {g["subgrupo_id"]: g for g in resp.json()["selecao"]["grupos"]}
    assert grupos["sg-1"]["escolhidos"] == 2
    assert grupos["sg-2"]["escolhidos"] == 5

    gravado = repo.obter_rascunho("est-fase1")
    assert opcoes_do_subgrupo(gravado, "sg-1") == ["op-1", "op-2"]


def test_endpoint_409_quando_a_poda_derruba_cenario(tmp_path: Path):
    r = _rascunho()
    _cenario(r, sg1="op-1", sg2="op-4")
    definir_selecao_do_subgrupo(r, "sg-2", ["op-4", "op-5"])
    client, repo = _client(tmp_path, r)
    url = "/api/estudos/est-fase1/selecao-planos-grupo"

    resp = client.put(url, json={"subgrupo_id": "sg-1", "opcao_ids": ["op-2"]})
    assert resp.status_code == 409
    detalhe = resp.json()["detail"]
    assert detalhe["codigo"] == "APP-SEL-001"
    assert detalhe["impacto_remocao"]["planos_removidos"] == ["Plano A", "Plano C"]

    intacto = repo.obter_rascunho("est-fase1")
    assert len(intacto.opcoes_proposta) == 5
    assert len(intacto.cenarios[0].atribuicoes) == 2

    resp_ok = client.put(
        url,
        json={"subgrupo_id": "sg-1", "opcao_ids": ["op-2"], "confirmar_remocoes": True},
    )
    assert resp_ok.status_code == 200
    assert resp_ok.json()["impacto_remocao"]["planos_removidos"] == ["Plano A", "Plano C"]

    depois = repo.obter_rascunho("est-fase1")
    assert {op.id for op in depois.opcoes_proposta} == {"op-2", "op-4", "op-5"}


def test_grupo_sem_marca_nao_bloqueia_tabela_extensa():
    """S750 vazio + ONE marcado: o vazio é escolha, não «levar todos»."""
    from datetime import datetime, timezone

    from newport_app.cotacao_pdf.apply import _ids_aplicaveis
    from newport_app.models.cotacao_pdf import (
        DocumentoCotacaoPDF,
        ExtracaoCotacaoCandidata,
        OpcaoCotacaoCandidata,
    )

    extracao = ExtracaoCotacaoCandidata(
        id="ext-sula",
        estudo_id="est-fase1",
        versao=1,
        documento=DocumentoCotacaoPDF(
            id="doc-sula",
            nome_arquivo="sula.pdf",
            hash_sha256="h",
            template_id="sulamerica-pme-v2",
        ),
        estado="extraido",
        criado_em=datetime.now(timezone.utc),
        opcoes=[
            OpcaoCotacaoCandidata(id=f"ex-{i}", selecionada_para_comparativo=False)
            for i in range(22)
        ],
    )
    ids, bloqueios, abortar = _ids_aplicaveis(
        [], extracao, selecao_vazia_nao_leva_todos=True
    )
    assert ids == set()
    assert bloqueios == []
    assert abortar is False

    ids_estudo, bloqueios_estudo, abortar_estudo = _ids_aplicaveis([], extracao)
    assert abortar_estudo is True
    assert "conscientemente" in bloqueios_estudo[0]["motivos"][0]


def test_endpoint_subgrupo_desconhecido_da_404(tmp_path: Path):
    client, _ = _client(tmp_path, _rascunho())
    resp = client.put(
        "/api/estudos/est-fase1/selecao-planos-grupo",
        json={"subgrupo_id": "sg-inexistente", "opcao_ids": []},
    )
    assert resp.status_code == 404
