"""Defeitos de apresentação HTML: regime %, rótulos, datas e faixas vazias."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from newport_app.cotacao_pdf.apply import (
    _ensure_regime,
    _regime_id,
    opcao_candidata_para_rascunho,
)
from newport_app.cotacao_pdf.coords_extract import (
    classificar_regime_cabecalho,
    classificar_regime_plano_porto,
)
from newport_app.models.cotacao_pdf import FaixaExtraida, OpcaoCotacaoCandidata, ValorExtraido
from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho, RegimeCopartRascunho
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.presentation.builder import (
    _qualificar_rotulos_propostas,
    construir_view_model,
)
from newport_app.presentation.formatacao import formatar_data_br
from newport_app.presentation.html_renderer import render_html
from newport_app.models.presentation import PropostaApresentacao
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService
from newport_app.siscor_mapper.apply import rascunho_vazio


def _campo(texto: str | None = None, *, inteiro: int | None = None, confirmado: bool = True):
    return ValorExtraido(
        id="c",
        rotulo="campo",
        texto=texto,
        inteiro=inteiro,
        confirmado=confirmado,
        estado="confirmar",
    )


def test_porto_copar_classifica_percentual_30():
    regime, pct, rotulo = classificar_regime_plano_porto(
        "P220 Q COPAR",
        "Tabela Geral de Prêmios sem coparticipação",
    )
    assert regime == "percentual"
    assert pct == 30
    assert rotulo == "Coparticipação 30%"


def test_sulamerica_cabecalho_com_copart_percentual():
    regime, pct, rotulo = classificar_regime_cabecalho(
        "Valores apresentados com 30% de coparticipação"
    )
    assert regime == "percentual"
    assert pct == 30
    assert "30%" in rotulo


def test_sulamerica_sem_copart_inalterado():
    regime, pct, rotulo = classificar_regime_cabecalho(
        "Tabela de prêmios sem coparticipação — Direto Nacional"
    )
    assert regime == "sem"
    assert pct is None
    assert rotulo == "Sem coparticipação"


def test_parcial_real_sem_percentual_permanece_parcial():
    rid = _regime_id(_campo("parcial"), None)
    assert rid == "regime-parcial"
    rascunho = rascunho_vazio("est-p", "t")
    _ensure_regime(rascunho, rid)
    assert rascunho.regimes_copart[0].tipo == "parcial"
    assert rascunho.regimes_copart[0].percentual is None


def test_apply_preserva_percentual_ate_rascunho():
    op = OpcaoCotacaoCandidata(
        id="op-p220",
        operadora=_campo("Porto Seguro"),
        plano_nome=_campo("P220 Q COPAR"),
        tipo_fiscal=_campo("seguradora"),
        regime_copart=_campo("percentual"),
        copart_percentual=_campo(inteiro=30),
        tabela=[
            FaixaExtraida(
                faixa=i,
                valor=ValorExtraido(
                    id=f"v{i}",
                    rotulo="v",
                    centavos=20_000 + i,
                    confirmado=True,
                    estado="confirmar",
                ),
                quantidade=ValorExtraido(id=f"q{i}", rotulo="q", inteiro=0, confirmado=True),
            )
            for i in range(10)
        ],
    )
    rascunho = rascunho_vazio("est-pct", "t")
    rid = _regime_id(op.regime_copart, 30)
    _ensure_regime(rascunho, rid, percentual=30)
    assert rid == "regime-percentual-30"
    assert rascunho.regimes_copart[0].tipo == "percentual"
    assert rascunho.regimes_copart[0].percentual == 30

    opcao = opcao_candidata_para_rascunho(
        op,
        extracao_id="ext-1",
        documento_id="doc-1",
        documento_hash="h",
        parser_versao="t",
    )
    assert opcao is not None
    assert opcao.regime_copart_id == "regime-percentual-30"


def test_apply_normaliza_parcial_com_pct_para_percentual():
    """Extrações antigas com texto=parcial + 30% viram percentual no apply."""
    rid = _regime_id(_campo("parcial"), 30)
    assert rid == "regime-percentual-30"


def test_formatar_data_br_iso_e_date():
    assert formatar_data_br("2026-08-14") == "14/08/2026"
    assert formatar_data_br(date(2026, 8, 14)) == "14/08/2026"


def test_rotulos_duplicados_qualificados_por_regime():
    rascunho = rascunho_demo_12_vidas()
    rascunho.regimes_copart = [
        RegimeCopartRascunho(id="regime-sem", tipo="sem"),
        RegimeCopartRascunho(id="regime-percentual-30", tipo="percentual", percentual=30),
    ]
    rascunho.opcoes_proposta[0].plano_nome = "Direto Nacional — Apartamento"
    rascunho.opcoes_proposta[0].regime_copart_id = "regime-percentual-30"
    op2 = rascunho.opcoes_proposta[0].model_copy(
        update={
            "id": "op-sa-sem",
            "plano_nome": "Direto Nacional — Apartamento",
            "regime_copart_id": "regime-sem",
        }
    )
    rascunho.opcoes_proposta.append(op2)
    props = [
        PropostaApresentacao(
            opcao_id=rascunho.opcoes_proposta[0].id,
            operadora="SulAmérica",
            plano_nome="Direto Nacional — Apartamento",
            regime_rotulo="Coparticipação 30%",
            regime_tipo="percentual",
        ),
        PropostaApresentacao(
            opcao_id="op-sa-sem",
            operadora="SulAmérica",
            plano_nome="Direto Nacional — Apartamento",
            regime_rotulo="Sem coparticipação",
            regime_tipo="sem",
        ),
    ]
    _qualificar_rotulos_propostas(rascunho, props)
    nomes = {p.plano_nome for p in props}
    assert len(nomes) == 2
    assert any("copart 30%" in n for n in nomes)
    assert any("sem copart" in n for n in nomes)


def test_rotulos_identicos_recebem_sufixo_numerico():
    rascunho = rascunho_demo_12_vidas()
    op2 = rascunho.opcoes_proposta[0].model_copy(update={"id": "op-clone"})
    rascunho.opcoes_proposta.append(op2)
    nome = rascunho.opcoes_proposta[0].plano_nome
    props = [
        PropostaApresentacao(
            opcao_id=rascunho.opcoes_proposta[0].id,
            operadora="X",
            plano_nome=nome,
            regime_rotulo="Sem coparticipação",
            regime_tipo="sem",
        ),
        PropostaApresentacao(
            opcao_id="op-clone",
            operadora="X",
            plano_nome=nome,
            regime_rotulo="Sem coparticipação",
            regime_tipo="sem",
        ),
    ]
    _qualificar_rotulos_propostas(rascunho, props)
    assert props[0].plano_nome == f"{nome} (1)"
    assert props[1].plano_nome == f"{nome} (2)"


def test_rotulos_distintos_inalterados():
    rascunho = rascunho_demo_12_vidas()
    props = [
        PropostaApresentacao(
            opcao_id=rascunho.opcoes_proposta[0].id,
            operadora="X",
            plano_nome="Plano A",
            regime_rotulo="Sem coparticipação",
            regime_tipo="sem",
        ),
        PropostaApresentacao(
            opcao_id="op-b",
            operadora="X",
            plano_nome="Plano B",
            regime_rotulo="Sem coparticipação",
            regime_tipo="sem",
        ),
    ]
    _qualificar_rotulos_propostas(rascunho, props)
    assert props[0].plano_nome == "Plano A"
    assert props[1].plano_nome == "Plano B"


def _stack(tmp_path: Path):
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    return repo, snap_svc


def _aprovar(repo, snap_svc, rascunho):
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(
            revisor_nome="Ana",
            confirmo_conteudo=True,
            auto_aprovacao=False,
        ),
    )
    return g.snapshot_id


def test_html_percentual_rotulo_validade_e_faixas(tmp_path):
    repo, snap_svc = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    # 3 vidas em 3 faixas distintas
    r.vidas = r.vidas[:3]
    r.vidas[0] = r.vidas[0].model_copy(update={"nascimento": date(2010, 1, 1)})
    r.vidas[1] = r.vidas[1].model_copy(update={"nascimento": date(1990, 1, 1)})
    r.vidas[2] = r.vidas[2].model_copy(update={"nascimento": date(1970, 1, 1)})

    r.regimes_copart = [
        RegimeCopartRascunho(id="regime-sem", tipo="sem"),
        RegimeCopartRascunho(id="regime-percentual-30", tipo="percentual", percentual=30),
    ]
    op = r.opcoes_proposta[0].model_copy(
        update={
            "plano_nome": "P220 Q COPAR",
            "regime_copart_id": "regime-percentual-30",
            "validade_oficial": date(2026, 8, 14),
        }
    )
    r.opcoes_proposta = [op]
    r.cenarios = [
        CenarioRascunho(
            id="c1",
            rotulo="C1",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1",
                    alvo_tipo="subgrupo",
                    alvo_id=r.subgrupos_atuais[0].id,
                    opcao_plano_id=op.id,
                )
            ],
        )
    ]

    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=[op.id])

    assert any(s.regime_tipo == "percentual" for s in vm.secoes_regime)
    sec = next(s for s in vm.secoes_regime if s.regime_tipo == "percentual")
    assert sec.regime_rotulo == "Coparticipação 30%"
    assert sec.propostas[0].copart_descricao == "Coparticipação 30%"
    assert sec.propostas[0].validade == "14/08/2026"

    plano = sec.planos_atuais[0]
    assert len(plano.faixas) == 3

    vm_todas = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=[op.id],
        exibir_todas_faixas=True,
    )
    assert len(vm_todas.secoes_regime[0].planos_atuais[0].faixas) == 10

    html = render_html(vm)
    assert "Coparticipação 30%" in html
    assert "Validade: 14/08/2026" in html
    assert "2026-08-14" not in html


def test_estudo_com_vidas_em_todas_faixas_inalterado(tmp_path):
    repo, snap_svc = _stack(tmp_path)
    r = rascunho_demo_12_vidas()
    snap_id = _aprovar(repo, snap_svc, r)
    snap = snap_svc.obter_snapshot(snap_id)
    vm = construir_view_model(
        snap, modo="faixas", propostas_selecionadas=[r.opcoes_proposta[0].id]
    )
    # demo 12 vidas cobre várias faixas; filtragem não deve esvaziar tabela
    n = len(vm.secoes_regime[0].planos_atuais[0].faixas)
    assert n >= 1
    vm_full = construir_view_model(
        snap,
        modo="faixas",
        propostas_selecionadas=[r.opcoes_proposta[0].id],
        exibir_todas_faixas=True,
    )
    assert len(vm_full.secoes_regime[0].planos_atuais[0].faixas) == 10
