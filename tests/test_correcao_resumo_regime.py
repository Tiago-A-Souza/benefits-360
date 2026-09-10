"""Correção: modo resumo deixa de perder valor por plano em outro regime."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    ComponenteFinanceiroRascunho,
    EscolhasEstudo,
    ModalidadeRascunho,
    OpcaoPropostaRascunho,
    OrigemValorRascunho,
    ParentescoRascunho,
    PriceBasisRascunho,
    ProvenienciaRascunho,
    RASCUNHO_VERSAO_ATUAL,
    RascunhoEstudo,
    RegimeCopartRascunho,
    SubgrupoAtualRascunho,
    VidaRascunho,
)
from newport_app.models.snapshot import AprovarSnapshotRequest
from newport_app.policy.registry import POLICY_SET_VERSAO_PADRAO
from newport_app.presentation.builder import MAX_PROPOSTAS_POR_PAGINA, construir_view_model
from newport_app.presentation.colisao_coluna import id_coluna_vm
from newport_app.presentation.formatacao import formatar_reais
from newport_app.presentation.html_renderer import _subtotal_proposta_plano, render_html
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.repository.historico import HistoricoRepository
from newport_app.repository.snapshot import SnapshotRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.snapshot import SnapshotService
from tests.test_comparativo_seguro_novo import _rascunho_ivtec_novo
from tests.test_paridade_matriz_html import (
    _rascunho_dois_planos_gabarito,
    _nascimento_faixa,
    _tabela,
)

_FIXTURE_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)


def _prov() -> ProvenienciaRascunho:
    return ProvenienciaRascunho(
        origem=OrigemValorRascunho.MANUAL, extrator_versao="manual", confirmado=True
    )


def _aprovar(tmp_path: Path, rascunho):
    db = tmp_path / f"resumo-regime-{rascunho.id}.db"
    repo = SQLiteStudyRepository(db)
    historico = HistoricoRepository(db)
    snap_repo = SnapshotRepository(db)
    snap_svc = SnapshotService(repo, snap_repo, historico)
    repo.salvar_rascunho(rascunho)
    g = snap_svc.gerar_snapshot_candidato(rascunho.id)
    snap_svc.aprovar_snapshot(
        rascunho.id,
        g.snapshot_id,
        AprovarSnapshotRequest(revisor_nome="Ana", confirmo_conteudo=True),
    )
    return snap_svc.obter_snapshot(g.snapshot_id)


def _ids(snap) -> list[str]:
    from newport_app.snapshot.comparativo import ler_comparativo_congelado

    matriz = ler_comparativo_congelado(snap.payload)
    from newport_app.presentation.colisao_coluna import chave_de_coluna

    return [chave_de_coluna(p) for p in matriz.propostas if p.calculo_realizado]


def _strip_tags(texto: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", texto).split())


def _tabelas_resumo(html: str) -> list[tuple[str, list[list[str]]]]:
    """Pares (rótulo de regime no h2, linhas da tabela) das seções de resumo."""
    saida: list[tuple[str, list[list[str]]]] = []
    for secao in re.findall(r"<section class='secao-regime'>(.*?)</section>", html, re.S):
        h2 = re.search(r"<h2>(.*?)</h2>", secao, re.S)
        if not h2 or "Resumo executivo" not in h2.group(1):
            continue
        rotulo = _strip_tags(h2.group(1))
        for bloco in re.findall(r"<table[^>]*>(.*?)</table>", secao, re.S):
            linhas: list[list[str]] = []
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", bloco, re.S):
                cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)
                linhas.append([_strip_tags(c) for c in cells])
            saida.append((rotulo, linhas))
    return saida


def _celula_resumo(
    tabelas: list[tuple[str, list[list[str]]]],
    plano_nome: str,
    proposta_nome: str,
) -> str:
    for _rotulo, linhas in tabelas:
        if not linhas:
            continue
        cab = None
        for linha in linhas:
            if proposta_nome in linha:
                cab = linha
                break
        if cab is None:
            continue
        col = cab.index(proposta_nome)
        for linha in linhas:
            if linha is cab or proposta_nome in linha:
                continue
            if linha and linha[0] == plano_nome:
                if len(linha) == len(cab):
                    bruto = linha[col]
                elif len(linha) == len(cab) + 1:
                    bruto = linha[col + 1]
                elif col < len(linha):
                    bruto = linha[col]
                else:
                    continue
                dinheiro = re.search(r"R\$\s*-?[\d.]+,\d{2}", bruto)
                return dinheiro.group(0) if dinheiro else bruto
    raise AssertionError(f"célula não encontrada: {plano_nome!r} × {proposta_nome!r}")


def _rascunho_anistia_seis() -> RascunhoEstudo:
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    data_ref = date.fromisoformat(spec["data_referencia"])
    vidas: list[VidaRascunho] = []
    for i, vida in enumerate(spec["vidas"]):
        pb = PriceBasisRascunho(vida["price_basis"])
        vidas.append(
            VidaRascunho(
                id=f"v{i}",
                nome=f"Beneficiário {i + 1}",
                nascimento=_nascimento_faixa(vida["faixa"], data_ref),
                parentesco=ParentescoRascunho(vida["parentesco"]),
                incluida=True,
                subgrupo_atual_id=vida["subgrupo_id"],
                valor_fatura=ComponenteFinanceiroRascunho(
                    centavos=vida["centavos"],
                    price_basis=pb,
                    proveniencia=_prov(),
                ),
            )
        )
    subgrupos = []
    for pl in spec["planos"]:
        subgrupos.append(
            SubgrupoAtualRascunho(
                id=pl["subgrupo_id"],
                operadora=pl["operadora"],
                plano_nome=pl["plano_nome"],
                regime_copart_id="regime-sem",
                tipo_fiscal="operadora",
                modalidade=ModalidadeRascunho.COMPULSORIO,
                reajuste_bps=spec["reajuste_bps"],
                fatura_price_basis=PriceBasisRascunho.NAO_APLICA,
                tabela_atual=[],
            )
        )
    opcoes = []
    tem_percentual = False
    for pr in spec["propostas"]:
        regime_id = "regime-percentual-30" if pr["regime_tipo"] == "percentual" else "regime-sem"
        if pr["regime_tipo"] == "percentual":
            tem_percentual = True
        valores = {i: v for i, v in enumerate(pr["tabela"])}
        opcoes.append(
            OpcaoPropostaRascunho(
                id=pr["id"],
                operadora=pr["operadora"],
                plano_nome=pr["plano_nome"],
                regime_copart_id=regime_id,
                tipo_fiscal=pr.get("tipo_fiscal") or "operadora",
                acomodacao="Apartamento",
                tabela=_tabela(valores),
            )
        )
    regimes = [RegimeCopartRascunho(id="regime-sem", tipo="sem")]
    if tem_percentual:
        regimes.append(
            RegimeCopartRascunho(
                id="regime-percentual-30", tipo="percentual", percentual=30
            )
        )
    rascunho = RascunhoEstudo(
        rascunho_versao=RASCUNHO_VERSAO_ATUAL,
        policy_set_versao=POLICY_SET_VERSAO_PADRAO,
        id="anistia-seis-propostas",
        titulo="Anistia seis propostas",
        formato="renovacao",
        vidas=vidas,
        subgrupos_atuais=subgrupos,
        opcoes_proposta=opcoes,
        regimes_copart=regimes,
        cenarios=[],
        escolhas=EscolhasEstudo(
            data_referencia_idade=data_ref,
            baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
            precedencia_atual_vida=CampoConfirmavelPrecedencia(
                valor="valor_fatura", confirmado=True
            ),
        ),
    )
    sincronizar_cenarios(rascunho)
    from newport_app.rascunho.cenarios_sync import garantir_cenarios_uniformes_multi

    garantir_cenarios_uniformes_multi(rascunho)
    return rascunho


def test_01_resumo_exibe_valor_por_plano_em_todos_os_regimes(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    assert len(vm.secoes_regime) == 2
    html = render_html(vm)
    tabelas = _tabelas_resumo(html)
    assert "Sem coparticipação" in html
    assert "Coparticipação 30%" in html or "coparticipação" in html.lower()
    for secao in vm.secoes_regime:
        for plano in secao.planos_atuais:
            if plano.subgrupo_id == "vidas-incluidas":
                continue
            for prop in secao.propostas:
                valor = _subtotal_proposta_plano(plano, id_coluna_vm(prop))
                assert valor is not None, (plano.plano_nome, prop.plano_nome)
                cel = _celula_resumo(tabelas, plano.plano_nome, prop.plano_nome)
                assert cel == formatar_reais(valor)
                assert cel != "—"
                assert "outro regime" not in cel.lower()


def test_02_soma_por_plano_igual_ao_consolidado_resumo(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    tabelas = _tabelas_resumo(html)
    for secao in vm.secoes_regime:
        for prop in secao.propostas:
            soma = 0
            for plano in secao.planos_atuais:
                if plano.subgrupo_id == "vidas-incluidas":
                    continue
                valor = _subtotal_proposta_plano(plano, id_coluna_vm(prop))
                assert valor is not None
                soma += valor
            consolidado = secao.totais.propostas.get(prop.opcao_id)
            assert soma == consolidado
            cel = _celula_resumo(tabelas, "Consolidado", prop.plano_nome)
            assert cel == formatar_reais(consolidado)


def test_03_paridade_resumo_faixas_por_subgrupo_e_opcao(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm_resumo = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_faixas = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    assert [s.regime_tipo for s in vm_resumo.secoes_regime] == [
        s.regime_tipo for s in vm_faixas.secoes_regime
    ]
    for secao_r, secao_f in zip(vm_resumo.secoes_regime, vm_faixas.secoes_regime, strict=True):
        planos_r = {p.subgrupo_id: p for p in secao_r.planos_atuais}
        planos_f = {p.subgrupo_id: p for p in secao_f.planos_atuais}
        assert set(planos_r) == set(planos_f)
        for sg_id, plano_r in planos_r.items():
            plano_f = planos_f[sg_id]
            for prop in secao_r.propostas:
                assert _subtotal_proposta_plano(plano_r, prop.opcao_id) == (
                    _subtotal_proposta_plano(plano_f, prop.opcao_id)
                )


def test_04_gabarito_anistia_seis_propostas(tmp_path: Path):
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar(tmp_path, rascunho)
    ids = [p["id"] for p in spec["propostas"]]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    tabelas = _tabelas_resumo(html)
    nomes = [p["plano_nome"] for p in spec["propostas"]]
    for nome in nomes:
        assert nome in html
    s750 = spec["planos"][0]["plano_nome"]
    one = spec["planos"][1]["plano_nome"]
    rotulos = {p["id"]: p["plano_nome"] for p in spec["propostas"]}
    for gab in spec["gabarito"]:
        nome = rotulos[gab["opcao_id"]]
        assert _celula_resumo(tabelas, s750, nome) == formatar_reais(gab["s750"])
        assert _celula_resumo(tabelas, one, nome) == formatar_reais(gab["one"])
        assert _celula_resumo(tabelas, "Consolidado", nome) == formatar_reais(
            gab["consolidado"]
        )
        assert gab["s750"] + gab["one"] == gab["consolidado"]
    assert MAX_PROPOSTAS_POR_PAGINA == 3
    for _rotulo, linhas in tabelas:
        assert len(linhas[0]) <= 2 + MAX_PROPOSTAS_POR_PAGINA


def test_05_unico_regime_inalterado(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    rascunho.id = "resumo-um-regime"
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    assert len(vm.secoes_regime) == 1
    html = render_html(vm)
    tabelas = _tabelas_resumo(html)
    assert tabelas
    for secao in vm.secoes_regime:
        for plano in secao.planos_atuais:
            if plano.subgrupo_id == "vidas-incluidas":
                continue
            for prop in secao.propostas:
                valor = _subtotal_proposta_plano(plano, id_coluna_vm(prop))
                assert valor is not None
                cel = _celula_resumo(tabelas, plano.plano_nome, prop.plano_nome)
                assert cel == formatar_reais(valor)


def test_06_seguro_novo_inalterado(tmp_path: Path):
    rascunho = _rascunho_ivtec_novo()
    snap = _aprovar(tmp_path, rascunho)
    ids = _ids(snap)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    html = render_html(vm)
    assert "Contrato atual" not in html
    assert "Atual vigente" not in html
    assert vm.totais_gerais.atual_centavos is None
    for secao in vm.secoes_regime:
        assert all(p.subgrupo_id == "vidas-incluidas" for p in secao.planos_atuais)
    assert "Diferença vs menor" in html
