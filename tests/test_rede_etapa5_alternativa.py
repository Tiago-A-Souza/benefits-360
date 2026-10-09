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
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
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
    html = render_html_completo(
        vm, vm, vm, rede=rede, rede_entrega_cliente=True
    )
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
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-btn-confirmar" not in rede
    assert "rede-sandbox-bar" not in rede.split("</style>", 1)[-1]
    assert not re.search(r"<script(?![^>]*application/json)", rede, re.I)


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
    from tests.test_rede_fase_d2 import test_17_quatro_abas_inalteradas

    test_17_quatro_abas_inalteradas(tmp_path)


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
    html = (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")
    rede = html.split('id="visao-rede"', 1)[-1]
    assert "rede-btn-confirmar" not in rede.split("</style>", 1)[-1]
