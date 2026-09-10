"""Frente 2.1 — reajuste percentual na exibição (fora do hash)."""

from __future__ import annotations

from copy import deepcopy

from newport_app.models.draft import SelecaoApresentacaoRascunho
from newport_app.models.presentation import (
    PlanoAtualApresentacao,
    PresentationViewModel,
    SecaoRegimeApresentacao,
    TotaisGeraisApresentacao,
    TotaisSecaoApresentacao,
)
from newport_app.models.responses import ComparativoResponse
from newport_app.policy.registry import default_registry
from newport_app.presentation.html_renderer import render_html
from newport_app.presentation.reajuste import (
    anexar_exibicao_reajuste,
    bps_variacao,
    formatar_rotulo_reajuste_bps,
    rotulo_reajuste_consolidado,
    rotulo_reajuste_exibicao,
)
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito


def test_bps_variacao_half_up_nao_bankers():
    assert bps_variacao(20_000, 20_001) == 1
    assert formatar_rotulo_reajuste_bps(0) == "0%"
    assert formatar_rotulo_reajuste_bps(1200) == "+12%"
    assert formatar_rotulo_reajuste_bps(1198) == "+11,98%"


def test_rotulo_ausente_vs_zero():
    assert (
        rotulo_reajuste_exibicao(
            vigente_centavos=1000,
            reajustado_centavos=1000,
            reajuste_bps_informado=None,
        )
        is None
    )
    assert (
        rotulo_reajuste_exibicao(
            vigente_centavos=1000,
            reajustado_centavos=1000,
            reajuste_bps_informado=0,
        )
        == "0%"
    )
    assert (
        rotulo_reajuste_exibicao(
            vigente_centavos=4_328_514,
            reajustado_centavos=4_847_931,
            reajuste_bps_informado=1200,
        )
        == "+12%"
    )


def test_consolidado_todos_nulos_omite():
    assert (
        rotulo_reajuste_consolidado(
            vigente_centavos=100,
            reajustado_centavos=100,
            reajustes_informados=[None, None],
        )
        is None
    )


def test_consolidado_percentuais_diferentes_efetivo():
    rotulo = rotulo_reajuste_consolidado(
        vigente_centavos=2000,
        reajustado_centavos=2300,
        reajustes_informados=[1000, 2000],
    )
    assert rotulo == "+15%"
    assert rotulo != "+10%"
    assert rotulo != "+20%"


def test_anexar_nao_altera_dump_hasheavel():
    r = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    ops = [o.id for o in r.opcoes_proposta[:2]]
    r.selecao_apresentacao = SelecaoApresentacaoRascunho(opcao_ids=ops, ordem=ops)
    comp, nucleo, _ = montar_payload_nucleo_congelamento(r, default_registry)
    h1 = hash_snapshot_canonico(nucleo)

    tela = anexar_exibicao_reajuste(comp, r)
    assert tela.reajuste_consolidado_percentual_exibicao == "+12%"
    assert all(p.reajuste_percentual_exibicao == "+12%" for p in tela.planos_atuais)

    nucleo2 = deepcopy(nucleo)
    h2 = hash_snapshot_canonico(nucleo2)
    assert h1 == h2

    dump = ComparativoResponse.model_validate(comp.model_dump()).model_dump(mode="json")
    assert "reajuste_consolidado_percentual_exibicao" not in dump
    for p in dump["planos_atuais"]:
        assert "reajuste_percentual_exibicao" not in p


def test_hash_antes_depois_mesma_passagem():
    r = rascunho_demo_12_vidas()
    ops = [o.id for o in r.opcoes_proposta[:1]]
    r.selecao_apresentacao = SelecaoApresentacaoRascunho(opcao_ids=ops, ordem=ops)
    _, nucleo_a, _ = montar_payload_nucleo_congelamento(r, default_registry)
    h_a = hash_snapshot_canonico(nucleo_a)
    _, nucleo_b, _ = montar_payload_nucleo_congelamento(r, default_registry)
    h_b = hash_snapshot_canonico(nucleo_b)
    assert h_a == h_b
    assert "reajuste_percentual_exibicao" not in str(nucleo_a["comparativo"])
    print(f"HASH_ANTES={h_a}")
    print(f"HASH_DEPOIS={h_b}")


def test_html_resumo_sem_vigente_com_percentual():
    from newport_app.models.presentation import PaginaFaixasApresentacao

    vm = PresentationViewModel(
        titulo="T",
        data_apresentacao="01/01/2026",
        estudo_id="est-x",
        modo="resumo",
        propostas_selecionadas=["op-1"],
        reajuste_consolidado_percentual_exibicao="+12%",
        totais_gerais=TotaisGeraisApresentacao(propostas={"op-1": 100}),
        secoes_regime=[
            SecaoRegimeApresentacao(
                regime_rotulo="Sem coparticipação",
                regime_tipo="sem",
                planos_atuais=[
                    PlanoAtualApresentacao(
                        subgrupo_id="sg-a",
                        operadora="Amil",
                        plano_nome="AMIL S750 - Apto.",
                        subtotal_vigente_centavos=2_623_822,
                        subtotal_reajustado_centavos=2_938_676,
                        reajuste_percentual_exibicao="+12%",
                    )
                ],
                totais=TotaisSecaoApresentacao(propostas={"op-1": 100}),
                paginas_faixas=[PaginaFaixasApresentacao(indice=0, propostas_ids=["op-1"])],
            )
        ],
    )
    html_doc = render_html(vm)
    assert "R$ 29.386,76" in html_doc
    assert "Contrato atual 12%" in html_doc
    assert "class='ajuste'" not in html_doc
    assert " vigente" not in html_doc
    assert "reajustado</small>" not in html_doc
