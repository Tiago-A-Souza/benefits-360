"""Rede na etapa 5 — alternativa ao sandbox HTML (branch rede-etapa5-alternativa)."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import RascunhoEstudo
from newport_app.models.presentation import (
    BlocoRedeApresentacao,
    ColunaRedeApresentacao,
    LinhaRedeApresentacao,
    RedeApresentacaoDocumento,
    SecaoRedeApresentacao,
)
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import (
    _id_linha_rede,
    contagem_coberturas_bloco,
    montar_rede_apresentacao,
)
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.services.rede_selecao import (
    aplicar_exclusoes_rede_documento,
    excluidos_rede,
    salvar_selecao_rede,
    sanitizar_selecao_rede,
)
from newport_app.models.draft import AtribuicaoRascunho, CenarioRascunho

from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"


def _texto_td(td_html: str) -> str:
    return re.sub(r"<[^>]+>", "", td_html, flags=re.S).strip()


def _valores_cont_rede_tabelas(html: str) -> list[list[str]]:
    rede = html.split('id="visao-rede"', 1)[-1]
    out: list[list[str]] = []
    for table in re.findall(r"<table class='tabela-rede[^>]*>.*?</table>", rede, re.S):
        for inner in re.findall(
            r"<tr class=['\"]cont-rede['\"][^>]*>(.*?)</tr>", table, re.S
        ):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", inner, re.S)
            vals = [_texto_td(t) for t in tds[1:]]
            out.append(vals)
    return out


def _contagens_esperadas_doc(doc) -> list[list[str]]:
    rows: list[list[str]] = []
    for sec in doc.secoes:
        cols = sec.colunas
        for bloco in sec.blocos:
            c = contagem_coberturas_bloco(bloco.linhas, cols)
            rows.append([str(c[col.chave]) for col in cols])
    return rows


def _html_completo_etapa5(tmp_path: Path, rascunho: RascunhoEstudo, cen_id: str):
    snap = _aprovar_anistia(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    excl = excluidos_rede(rascunho)
    rede = montar_rede_apresentacao(
        rascunho, [cen_id], excluidos=excl
    )
    html = render_html_completo(vm, vm, vm, rede=rede)
    return html, rede


@pytest.fixture
def repo_etapa5(tmp_path: Path) -> SQLiteStudyRepository:
    return SQLiteStudyRepository(tmp_path / "rede_etapa5.db")


@pytest.fixture
def client_etapa5(repo_etapa5: SQLiteStudyRepository) -> TestClient:
    return TestClient(create_app(repo=repo_etapa5, seed_demos=False))


def _gravar_rascunho(repo: SQLiteStudyRepository, rascunho: RascunhoEstudo) -> None:
    rascunho = rascunho.model_copy(update={"id": "est-rede-etapa5"})
    repo.salvar_rascunho(rascunho)


def test_00_linha_id_unica_por_subgrupo_e_local():
    barra_sg1 = _id_linha_rede(
        "HOSP SAMARITANO",
        "RJ.RIO DE JANEIRO",
        "BARRA DA TIJUCA",
        subgrupo_id="sg-a",
    )
    botafogo_sg1 = _id_linha_rede(
        "HOSP SAMARITANO",
        "RJ.RIO DE JANEIRO",
        "BOTAFOGO",
        subgrupo_id="sg-a",
    )
    barra_sg2 = _id_linha_rede(
        "HOSP SAMARITANO",
        "RJ.RIO DE JANEIRO",
        "BARRA DA TIJUCA",
        subgrupo_id="sg-b",
    )
    assert barra_sg1 != botafogo_sg1
    assert barra_sg1 != barra_sg2


def test_00c_excluir_samaritano_barra_mantem_botafogo():
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc
    sam = [
        (ln.linha_id, ln.bairro)
        for sec in doc.secoes
        for bl in sec.blocos
        for ln in bl.linhas
        if "SAMARITANO" in ln.prestador.upper()
    ]
    assert len(sam) >= 2
    barra_id = next(lid for lid, b in sam if "BARRA" in (b or "").upper())
    botafogo_id = next(lid for lid, b in sam if "BOTAFOGO" in (b or "").upper())
    assert barra_id != botafogo_id
    salvar_selecao_rede(rascunho, [barra_id], revisada=True)
    doc2 = montar_rede_apresentacao(
        rascunho, [cen_id], excluidos=excluidos_rede(rascunho)
    )
    restantes = {
        ln.linha_id
        for sec in doc2.secoes
        for bl in sec.blocos
        for ln in bl.linhas
        if "SAMARITANO" in ln.prestador.upper()
    }
    assert botafogo_id in restantes
    assert barra_id not in restantes


def test_00b_dois_grupos_mesmo_prestador_ids_distintos_na_ui():
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc and len(doc.secoes) >= 2
    ids = [
        ln.linha_id
        for sec in doc.secoes
        for bl in sec.blocos
        for ln in bl.linhas
        if "SAMARITANO" in ln.prestador.upper()
        and ln.chave_municipio == "RJ.RIO DE JANEIRO"
    ]
    assert len(ids) >= 2
    assert len(set(ids)) == len(ids)


def test_01_passos_incluem_rede_antes_do_comparativo():
    src = (ROOT / "web" / "src" / "fluxo" / "passos.js").read_text(encoding="utf-8")
    assert '{ chave: "rede"' in src
    idx_rede = src.index('"rede"')
    idx_cmp = src.index('"comparativo"')
    assert idx_rede < idx_cmp


def test_02_documento_gerado_sem_sandbox_na_rede(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    html, _ = _html_completo_etapa5(tmp_path, rascunho, cen_id)
    assert "<script" not in html.lower()
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-btn-confirmar" not in rede
    assert "rede-sandbox-bar" not in rede


def test_03_exclusao_remove_prestador_do_documento(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc and doc.secoes[0].blocos
    lid = doc.secoes[0].blocos[0].linhas[0].linha_id
    salvar_selecao_rede(rascunho, [lid], revisada=True)
    html, _ = _html_completo_etapa5(tmp_path, rascunho, cen_id)
    assert f"data-rede-id='{lid}'" not in html and f'data-rede-id="{lid}"' not in html


def test_04_selecao_rede_persiste_no_rascunho():
    r = RascunhoEstudo.model_validate(
        {
            "rascunho_versao": "1.0",
            "policy_set_versao": "1",
            "id": "x",
            "titulo": "t",
            "vidas": [],
        }
    )
    salvar_selecao_rede(r, ["id-a", "id-b"], revisada=True, ids_validos={"id-a", "id-b", "id-c"})
    assert r.selecao_rede
    assert r.selecao_rede.excluidos == ["id-a", "id-b"]
    assert r.selecao_rede.revisada is True


def test_05_selecao_padrao_sem_exclusao_igual_rede_completa(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    doc2 = montar_rede_apresentacao(rascunho, [cen_id], excluidos=excluidos_rede(rascunho))
    assert doc and doc2
    n1 = sum(len(b.linhas) for s in doc.secoes for b in s.blocos)
    n2 = sum(len(b.linhas) for s in doc2.secoes for b in s.blocos)
    assert n1 == n2


def _rascunho_s750_one_atribuicoes_distintas():
    """Dois grupos (S750 × ONE vigentes), propostas diferentes por subgrupo."""
    rascunho = _rascunho_anistia_seis()
    vidas = []
    for v in rascunho.vidas:
        uf, cidade = "RJ", "RIO DE JANEIRO"
        if v.subgrupo_atual_id == "sg-b":
            uf, cidade = "SP", "SAO PAULO"
        vidas.append(v.model_copy(update={"uf": uf, "cidade": cidade}))
    op_sg_a = next(o for o in rascunho.opcoes_proposta if "PRATA MAIS" in o.plano_nome)
    op_sg_b = next(o for o in rascunho.opcoes_proposta if "OURO MAIS" in o.plano_nome)
    cen = CenarioRascunho(
        id="c-s750-one",
        rotulo="S750 × ONE distintos",
        atribuicoes=[
            AtribuicaoRascunho(
                id="atr-a",
                alvo_tipo="subgrupo",
                alvo_id="sg-a",
                opcao_plano_id=op_sg_a.id,
            ),
            AtribuicaoRascunho(
                id="atr-b",
                alvo_tipo="subgrupo",
                alvo_id="sg-b",
                opcao_plano_id=op_sg_b.id,
            ),
        ],
    )
    rasc = rascunho.model_copy(update={"vidas": vidas, "cenarios": [cen]})
    return rasc, cen.id, op_sg_a, op_sg_b


def test_06d_secao_s750_nao_mostra_proposta_do_one():
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from newport_app.services.rede_selecao_ui import montar_rede_selecao_ui

    rasc, cen_id, op_a, op_b = _rascunho_s750_one_atribuicoes_distintas()
    ui = montar_rede_selecao_ui(rasc)
    doc = montar_rede_apresentacao(rasc, [cen_id])
    assert len(ui.secoes) == 2
    sec_s750 = next(s for s in ui.secoes if "S750" in s.rotulo)
    sec_one = next(s for s in ui.secoes if "ONE" in s.rotulo.upper())
    doc_s750 = next(s for s in doc.secoes if "S750" in s.rotulo)
    doc_one = next(s for s in doc.secoes if "ONE" in s.rotulo.upper())

    def nomes_proposta_ui(sec):
        return {c.plano_nome for c in sec.colunas if not c.contrato_atual}

    def nomes_proposta_doc(sec):
        return {c.plano_nome for c in sec.colunas if c.chave != "rede-atual"}

    prop_s750 = nomes_proposta_ui(sec_s750)
    prop_one = nomes_proposta_ui(sec_one)
    assert op_a.plano_nome in prop_s750
    assert op_b.plano_nome in prop_one
    assert op_b.plano_nome not in prop_s750, (
        f"seção S750 não deve listar proposta do ONE: {prop_s750}"
    )
    assert op_a.plano_nome not in prop_one, (
        f"seção ONE não deve listar proposta do S750: {prop_one}"
    )
    assert "ONE S2500" not in prop_s750
    assert "S750" not in prop_one or all("S750" not in n for n in prop_one)
    assert nomes_proposta_doc(doc_s750) == prop_s750
    assert nomes_proposta_doc(doc_one) == prop_one


def test_06e_proposta_so_do_outro_grupo_nao_vaza_na_secao():
    """Paridade com estudo real: 2 cenários; coluna só entra se atribuída ao subgrupo."""
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from newport_app.services.rede_selecao_ui import montar_rede_selecao_ui

    rasc = _rascunho_anistia_seis()
    vidas = []
    for v in rasc.vidas:
        uf, cidade = "RJ", "RIO DE JANEIRO"
        if v.subgrupo_atual_id == "sg-b":
            uf, cidade = "SP", "SAO PAULO"
        vidas.append(v.model_copy(update={"uf": uf, "cidade": cidade}))
    op_prata = next(o for o in rasc.opcoes_proposta if "PRATA MAIS" in o.plano_nome)
    op_ouro = next(o for o in rasc.opcoes_proposta if "OURO MAIS" in o.plano_nome)
    op_exec = next(o for o in rasc.opcoes_proposta if "Executivo R1" in o.plano_nome)
    op_one2 = next(o for o in rasc.opcoes_proposta if "Especial 100 R1" in o.plano_nome)
    cen1 = CenarioRascunho(
        id="c1",
        rotulo="C1",
        atribuicoes=[
            AtribuicaoRascunho(id="a1a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id=op_prata.id),
            AtribuicaoRascunho(id="a1b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id=op_exec.id),
        ],
    )
    cen2 = CenarioRascunho(
        id="c2",
        rotulo="C2",
        atribuicoes=[
            AtribuicaoRascunho(id="a2a", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id=op_ouro.id),
            AtribuicaoRascunho(id="a2b", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id=op_one2.id),
        ],
    )
    rasc = rasc.model_copy(update={"vidas": vidas, "cenarios": [cen1, cen2]})
    ui = montar_rede_selecao_ui(rasc)
    sec_s750 = next(s for s in ui.secoes if "S750" in s.rotulo)
    sec_one = next(s for s in ui.secoes if "ONE" in s.rotulo.upper())
    props_s750 = {c.plano_nome for c in sec_s750.colunas if not c.contrato_atual}
    props_one = {c.plano_nome for c in sec_one.colunas if not c.contrato_atual}
    assert op_prata.plano_nome in props_s750 and op_ouro.plano_nome in props_s750
    assert op_exec.plano_nome not in props_s750
    assert op_one2.plano_nome not in props_s750
    assert any("Executivo" in p for p in props_one)
    assert any("Especial 100" in p for p in props_one)
    assert op_prata.plano_nome not in props_one
    assert op_ouro.plano_nome not in props_one


def test_06b_ui_api_colunas_por_secao_e_cobertura():
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from newport_app.services.rede_selecao_ui import montar_rede_selecao_ui

    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    ui = montar_rede_selecao_ui(rascunho)
    assert ui.secoes
    assert len(ui.secoes) >= 2
    sets_col = [frozenset(c.chave for c in sec.colunas) for sec in ui.secoes]
    assert sets_col[0] and sets_col[1]
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert [tuple(c.chave for c in s.colunas) for s in doc.secoes] == [
        tuple(c.chave for c in s.colunas) for s in ui.secoes
    ]
    achou_codigo = False
    for sec in ui.secoes:
        assert sec.colunas, "cada seção deve expor colunas de plano"
        for bl in sec.blocos:
            for ln in bl.linhas:
                assert ln.prestador_nome
                for v in ln.celulas.values():
                    if v and v.strip() not in ("", "—"):
                        achou_codigo = True
    assert achou_codigo


def test_06c_css_colunas_plano_largura_fixa():
    css = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    assert ".rede-selecao-tabela.tabela-rede .rede-col-plano" in css
    assert "112px" in css


def test_07_persistencia_api_sair_e_voltar(
    client_etapa5: TestClient, repo_etapa5: SQLiteStudyRepository
):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, _, _ = _rascunho_dois_grupos_um_cenario()
    _gravar_rascunho(repo_etapa5, rascunho)
    eid = "est-rede-etapa5"
    get0 = client_etapa5.get(f"/api/estudos/{eid}/rede-selecao")
    assert get0.status_code == 200
    linhas = [
        ln
        for sec in get0.json()["secoes"]
        for bl in sec["blocos"]
        for ln in bl["linhas"]
    ]
    assert linhas
    excl = [linhas[0]["linha_id"]]
    put = client_etapa5.put(
        f"/api/estudos/{eid}/rede-selecao",
        json={"excluidos": excl, "revisada": True},
    )
    assert put.status_code == 200
    r2 = client_etapa5.get(f"/api/estudos/{eid}/rascunho")
    assert r2.status_code == 200
    assert excl[0] in (r2.json().get("selecao_rede") or {}).get("excluidos", [])
    get1 = client_etapa5.get(f"/api/estudos/{eid}/rede-selecao")
    assert excl[0] in get1.json()["excluidos"]
    assert get1.json()["revisada"] is True


def test_08_nova_linha_nao_herda_exclusao_antiga():
    col = ColunaRedeApresentacao(
        chave="p1", operadora="Op", plano_nome="Plano", rede_nao_mapeada=False
    )
    lin_a = LinhaRedeApresentacao(
        linha_id="id-antigo",
        prestador="H A",
        chave_municipio="RJ.X",
        bairro="",
        zona="",
        celulas={"p1": "H"},
    )
    lin_n = LinhaRedeApresentacao(
        linha_id="id-novo-base",
        prestador="H N",
        chave_municipio="RJ.X",
        bairro="",
        zona="",
        celulas={"p1": "H"},
    )
    bloco = BlocoRedeApresentacao(titulo="Bloco", linhas=[lin_a, lin_n])
    sec = SecaoRedeApresentacao(
        subgrupo_id="sg",
        rotulo="Sec",
        colunas=[col],
        blocos=[bloco],
        paginas=[],
        total_linhas=2,
    )
    doc = RedeApresentacaoDocumento(data_base_rede="01/01/2025", secoes=[sec])
    filtrado = aplicar_exclusoes_rede_documento(doc, {"id-antigo"})
    ids = {ln.linha_id for ln in filtrado.secoes[0].blocos[0].linhas}
    assert ids == {"id-novo-base"}


def test_08b_sanitizar_tira_exclusao_de_id_que_saiu_da_base():
    r = RascunhoEstudo.model_validate(
        {
            "rascunho_versao": "1.0",
            "policy_set_versao": "1",
            "id": "x",
            "titulo": "t",
            "vidas": [],
            "selecao_rede": {
                "excluidos": ["fantasma", "real"],
                "revisada": True,
            },
        }
    )
    sanitizar_selecao_rede(r, {"real", "outro"})
    assert r.selecao_rede
    assert r.selecao_rede.excluidos == ["real"]


def test_13_cobertos_reflete_linhas_apos_exclusao(tmp_path: Path):
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    doc = montar_rede_apresentacao(rascunho, [cen_id])
    assert doc
    bloco = doc.secoes[0].blocos[0]
    excluir = [bloco.linhas[0].linha_id, bloco.linhas[1].linha_id]
    salvar_selecao_rede(rascunho, excluir, revisada=True)
    doc_filt = montar_rede_apresentacao(
        rascunho, [cen_id], excluidos=excluidos_rede(rascunho)
    )
    html, _ = _html_completo_etapa5(tmp_path, rascunho, cen_id)
    html_vals = _valores_cont_rede_tabelas(html)
    esperado = _contagens_esperadas_doc(doc_filt)
    assert html_vals == esperado
    assert html_vals
    for row in html_vals:
        assert row
        assert not (len(row) >= 2 and row[0] == "0" and row[1] != "0")


def test_14_etapa6_avisa_rede_nao_revisada():
    src = (ROOT / "web" / "src" / "ComparativoPanel.jsx").read_text(encoding="utf-8")
    assert "Rede credenciada não revisada" in src
    assert "selecao_rede" in src


def test_15_gabaritos_valor_por_valor(tmp_path: Path):
    from tests.test_fase5_faixas_por_grupo import test_12_gabaritos_valor_por_valor

    test_12_gabaritos_valor_por_valor(tmp_path)


def test_16_quatro_abas_anteriores_inalteradas(tmp_path: Path):
    from tests.test_rede_documento_estatico import test_05_quatro_abas_anteriores_intactas

    test_05_quatro_abas_anteriores_intactas(tmp_path)


def test_17_rascunhos_demo_carregam():
    r = subprocess.run(
        [sys.executable, "scripts/verificar_rascunhos_do_banco.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FALHAM_CARGA=0" in r.stdout


def test_18_hashes_snapshot_intactos():
    r = subprocess.run(
        [sys.executable, "scripts/verificar_hashes_snapshots.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "HASH_DIVERGENTE=0" in r.stdout


def test_19_fases_rede_abc_d1_montagem():
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from tests.test_rede_fase_d1 import test_01_duas_secoes_dois_grupos

    test_01_duas_secoes_dois_grupos()


def test_20_apresentacao_service_sem_sandbox_no_html(tmp_path: Path):
    """Gerar via serviço (etapa 6) — rede entrega cliente."""
    if not _XLSX.is_file():
        pytest.skip("base SiscorNet ausente")
    from tests.test_fase2_tarefa2 import _aprovar, _stack

    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": "est-apres-et5"})
    repo, _, snap_svc, apres = _stack(tmp_path, "et5-apres")
    snap = _aprovar(repo, snap_svc, rascunho)
    req = GerarApresentacaoRequest(
        modo="completo",
        propostas_selecionadas=[cen_id],
        ressalvas=[],
    )
    res = apres.gerar_html(rascunho.id, snap.id, req)
    assert "_para_cliente" not in res.caminho_relativo
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    assert "<script" not in html.lower()
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-btn-confirmar" not in rede
