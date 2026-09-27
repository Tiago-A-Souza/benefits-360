"""REDE fase B — UF/CIDADE opcionais na importação SISCOR."""

from __future__ import annotations

import json
from collections import Counter
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS
from newport_app.siscor_importer.normalize import normalizar_cabecalho
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.fixtures.siscor.xlsx_builder import (
    CABECALHO_COMPLETO_50,
    planilha_12_vidas,
    planilha_anistia_41_cabecalho_nbsp,
    planilha_anistia_41_sintetica,
    _linhas_anistia_41,
    gerar_planilha_siscor_completa,
)
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)
from newport_app.presentation.planos_rede import (
    EstadoCasamentoRede,
    caminho_base_rede_padrao,
    carregar_aliases_rede,
    carregar_colunas_rede_xlsx,
    resolver_casamento_rede,
)
from newport_app.presentation.regras_comerciais import carregar_aliases
from tests.test_planos_rede import _planos_estudo_reais
from tests.test_regras_comerciais import _html_de
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from fastapi.testclient import TestClient
from newport_app.api.main import create_app
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    db = tmp_path / "test.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    app = create_app(
        repo=repo,
        import_repo=imp,
        uploads_dir=tmp_path / "uploads",
        seed_demos=False,
    )
    return TestClient(app)


def _planilha_real(nomes: tuple[str, ...], *, glob_anistia: bool = False) -> Path | None:
    raizes = [
        Path(r"C:\Users\tiago\Downloads"),
        ROOT / ".private" / "runtime",
    ]
    for raiz in raizes:
        if not raiz.is_dir():
            continue
        for nome in nomes:
            direto = raiz / nome
            if direto.is_file():
                return direto
            for hit in raiz.rglob(nome):
                if hit.is_file():
                    return hit
        if glob_anistia:
            for hit in raiz.glob("POSI*.xlsx"):
                n = hit.name.upper()
                if "IVTEC" in n:
                    continue
                if "CADASTRAL" in n and "SEGURADO" in n:
                    return hit
    return None


def _parse_bytes(conteudo: bytes, estudo_id: str = "rede-b") -> object:
    return parse_planilha_siscor(conteudo, estudo_id=estudo_id, documento_id="doc-rede-b")


def _contagem_localizacao(linhas) -> tuple[int, Counter]:
    com_loc = [l for l in linhas if l.uf and l.cidade]
    ufs = Counter(l.uf for l in com_loc)
    return len(com_loc), ufs


def test_01_anistia_real_39_de_41_e_distribuicao_uf():
    path = _planilha_real(
        (
            "POSIÇÃO_CADASTRAL_SEGURADOS__SAÚDE_2.xlsx",
            "POSICAO_CADASTRAL_SEGURADOS__SAUDE_2.xlsx",
        ),
        glob_anistia=True,
    )
    if path is None:
        pytest.skip("Planilha Anistia real indisponível")
    resultado = _parse_bytes(path.read_bytes(), estudo_id="anistia-real-loc")
    assert resultado.sucesso
    c = resultado.candidata
    assert c.disponibilidade_colunas.uf
    assert c.disponibilidade_colunas.cidade
    preenchidas, ufs = _contagem_localizacao(c.linhas)
    assert preenchidas == 39
    assert c.estatisticas.localizacao_preenchida == 39
    assert c.estatisticas.localizacao_celula_vazia == 2
    assert ufs["RJ"] == 22
    assert ufs["SP"] == 13
    assert ufs["PA"] == 2
    assert ufs["RS"] == 1
    assert ufs["BA"] == 1


def test_01_sintetico_41_mesma_contagem_se_real_ausente():
    """Fixture 50 col — mesma lógica de contagem quando a planilha real não está no CI."""
    resultado = _parse_bytes(planilha_anistia_41_sintetica())
    assert resultado.sucesso
    c = resultado.candidata
    assert c.disponibilidade_colunas.uf and c.disponibilidade_colunas.cidade
    preenchidas, ufs = _contagem_localizacao(c.linhas)
    assert len(c.linhas) == 41
    assert preenchidas == 39
    assert c.estatisticas.localizacao_celula_vazia == 2
    assert ufs["RJ"] == 22
    assert ufs["SP"] == 13


def test_02_ausencia_individual_celula_vazia():
    resultado = _parse_bytes(planilha_anistia_41_sintetica())
    c = resultado.candidata
    vazias = [l for l in c.linhas if not (l.uf and l.cidade)]
    assert len(vazias) == 2
    assert all(l.uf is None or l.cidade is None for l in vazias)


def test_03_ivtec_8_colunas_sem_localizacao():
    resultado = _parse_bytes(planilha_12_vidas(), estudo_id="ivtec-loc")
    assert resultado.sucesso
    c = resultado.candidata
    assert not c.disponibilidade_colunas.uf
    assert not c.disponibilidade_colunas.cidade
    assert c.estatisticas.localizacao_preenchida == 0
    assert c.estatisticas.localizacao_celula_vazia == 0
    assert all(l.uf is None and l.cidade is None for l in c.linhas)


def test_04_nenhuma_deducao_uf_ou_cidade():
    wb = Workbook()
    ws = wb.active
    cab = list(COLUNAS_OBRIGATORIAS) + ["UF", "CIDADE"]
    ws.append(cab)
    ws.append(
        [
            "Cliente",
            "Segurado A",
            "TITULAR",
            "01/01/1980",
            "Plano X",
            "Op Y",
            100.0,
            "ATIVO",
            "Rio de Janeiro",
            "SAO PAULO",
        ]
    )
    buf = BytesIO()
    wb.save(buf)
    r = _parse_bytes(buf.getvalue(), estudo_id="deducao")
    linha = r.candidata.linhas[0]
    assert linha.uf is None
    assert linha.cidade == "SAO PAULO"


def test_05_rascunho_antigo_abre_sem_localizacao():
    rascunho = rascunho_demo_12_vidas()
    assert all(v.uf is None and v.cidade is None for v in rascunho.vidas)
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado is not None


def test_06_cabecalho_nbsp_e_alias_municipio_estado():
    linhas = _linhas_anistia_41()[:2]
    cab = list(COLUNAS_OBRIGATORIAS) + ["SEXO", "MUNICÍPIO", "ESTADO"]
    chaves = list(COLUNAS_OBRIGATORIAS) + ["SEXO", "CIDADE", "UF"]
    for i, linha in enumerate(linhas):
        linha["UF"] = "SP"
        linha["CIDADE"] = "CAMPINAS"
        if i == 1:
            linha["UF"] = None
            linha["CIDADE"] = None
    xlsx = gerar_planilha_siscor_completa(linhas, cabecalho=cab, chaves_linha=chaves)
    r = _parse_bytes(xlsx)
    assert r.candidata.disponibilidade_colunas.uf
    assert r.candidata.disponibilidade_colunas.cidade
    assert r.candidata.linhas[0].uf == "SP"
    assert r.candidata.linhas[0].cidade == "CAMPINAS"

    nbsp = planilha_anistia_41_cabecalho_nbsp()
    rn = _parse_bytes(nbsp, estudo_id="nbsp-loc")
    assert rn.candidata.disponibilidade_colunas.uf
    assert rn.candidata.disponibilidade_colunas.cidade


def test_07_gabarito_intacto(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_08_rascunhos_banco_compilam():
    db = ROOT / ".data" / "newport_app.db"
    if not db.is_file():
        pytest.skip("banco demo ausente")
    import sqlite3

    conn = sqlite3.connect(db)
    n = conn.execute("SELECT COUNT(*) FROM rascunhos").fetchone()[0]
    conn.close()
    assert n >= 1
    rascunho = _rascunho_anistia_seis()
    assert compile(rascunho, policy_registry=default_registry) is not None


def test_09_hash_snapshot_novo_muda_existente_nao(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_nucleo = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, _ = _stack(tmp_path, "hash-rede-b")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    h_congelado = snap.hash_sha256
    assert h_congelado == h_nucleo
    assert len(h_congelado) == 64

    rascunho_novo = rascunho.model_copy(deep=True)
    rascunho_novo.vidas[0].uf = "RJ"
    rascunho_novo.vidas[0].cidade = "RIO DE JANEIRO"
    _, nucleo_novo, _ = montar_payload_nucleo_congelamento(rascunho_novo, default_registry)
    h_com_local = hash_snapshot_canonico(nucleo_novo)
    assert h_com_local != h_nucleo
    print(f"HASH_SEM_LOCAL={h_nucleo}")
    print(f"HASH_COM_LOCAL={h_com_local}")
    print(f"HASH_SNAPSHOT_EXISTENTE={h_congelado}")


def test_10_html_export_inalterado(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html


def test_11_fase_a_55_casam():
    xlsx = caminho_base_rede_padrao()
    if xlsx is None:
        pytest.skip("base SiscorNet ausente")
    aliases = carregar_aliases()
    colunas = carregar_colunas_rede_xlsx(xlsx, aliases)
    tabela = carregar_aliases_rede(colunas_rede=colunas)
    planos = _planos_estudo_reais()
    assert len(planos) == 55
    for op, pl in planos:
        r = resolver_casamento_rede(op, pl, colunas, tabela=tabela)
        assert r.estado in (EstadoCasamentoRede.ALIAS, EstadoCasamentoRede.REGRA)


def test_12_colunas_opcionais_anteriores():
    resultado = _parse_bytes(planilha_anistia_41_sintetica())
    c = resultado.candidata
    assert c.disponibilidade_colunas.sexo
    assert c.disponibilidade_colunas.cpf_titular
    assert c.estatisticas.sexo_preenchido == 41


def test_api_anistia_contagem_localizacao(client: TestClient):
    path = _planilha_real((), glob_anistia=True)
    if path is None:
        pytest.skip("Planilha Anistia real indisponível")
    estudo_id = "estudo-rede-b-api"
    client.post(
        "/api/estudos",
        json={"id": estudo_id, "titulo": "Anistia loc", "nome_empresa": "Anistia"},
    )
    res = client.post(
        f"/api/estudos/{estudo_id}/importar-siscor",
        files={
            "arquivo": (
                path.name,
                path.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        params={"formato": "renovacao"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    disp = body["candidata"]["disponibilidade_colunas"]
    assert disp["uf"] is True
    assert disp["cidade"] is True
    assert body["resumo"]["estatisticas"]["localizacao_preenchida"] == 39


def test_api_ivtec_sem_coluna_localizacao(client: TestClient):
    conteudo = planilha_12_vidas()
    estudo_id = "estudo-ivtec-rede-b"
    client.post(
        "/api/estudos",
        json={"id": estudo_id, "titulo": "IVTEC", "nome_empresa": "IVTEC"},
    )
    res = client.post(
        f"/api/estudos/{estudo_id}/importar-siscor",
        files={
            "arquivo": (
                "ivtec.xlsx",
                conteudo,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        params={"formato": "renovacao"},
    )
    assert res.status_code == 200, res.text
    disp = res.json()["candidata"]["disponibilidade_colunas"]
    assert disp["uf"] is False
    assert disp["cidade"] is False
