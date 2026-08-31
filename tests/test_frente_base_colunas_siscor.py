"""FRENTE BASE — colunas opcionais SISCOR (sexo, vínculo titular)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from newport_app.draft_compiler import compile
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.fixtures.siscor.xlsx_builder import (
    planilha_12_vidas,
    planilha_anistia_41_cabecalho_nbsp,
    planilha_anistia_41_sintetica,
    planilha_atef_3_sintetica,
    planilha_sexo_coluna_celulas_vazias,
)
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)


def _planilha_real(nomes: tuple[str, ...], *, glob_anistia: bool = False) -> Path | None:
    raizes = [
        Path(r"C:\Users\tiago\Downloads"),
        Path(r"C:\np\.private\runtime"),
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
        if not glob_anistia:
            continue
        # Nomes com acento/encoding de filesystem (POSIÇÃO…SAÚDE).
        for hit in raiz.glob("POSI*.xlsx"):
            n = hit.name.upper()
            if "IVTEC" in n:
                continue
            if "CADASTRAL" in n and "SEGURADO" in n:
                return hit
    return None


def _parse_bytes(conteudo: bytes, estudo_id: str = "fb-test"):
    return parse_planilha_siscor(conteudo, estudo_id=estudo_id, documento_id="doc-fb")


def _parse_arquivo(path: Path):
    return _parse_bytes(path.read_bytes(), estudo_id=f"fb-{path.stem}")


def test_01_anistia_41_sexo_e_vinculo_sintetico():
    resultado = _parse_bytes(planilha_anistia_41_sintetica())
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert len(c.linhas) == 41
    assert c.disponibilidade_colunas.sexo
    assert c.disponibilidade_colunas.cpf_titular
    assert c.estatisticas.sexo_preenchido == 41
    assert sum(1 for l in c.linhas if l.sexo == "feminino") == 29
    assert sum(1 for l in c.linhas if l.sexo == "masculino") == 12
    assert c.estatisticas.vinculos_resolvidos == 41
    assert all(l.vinculo_resolvido for l in c.linhas)


def test_01b_anistia_41_cabecalho_nbsp_regressao():
    """Fixture com NBSP nos compostos — mesma regressão da planilha real."""
    from collections import Counter

    from openpyxl import load_workbook
    from io import BytesIO

    conteudo = planilha_anistia_41_cabecalho_nbsp()
    wb = load_workbook(BytesIO(conteudo), read_only=True, data_only=True)
    headers = [c.value for c in next(wb.active.iter_rows(min_row=1, max_row=1))]
    wb.close()
    assert "CPF\u00A0TITULAR" in headers
    assert "TIPO\u00A0DE\u00A0VIDA" in headers
    assert "DATA\u00A0DE\u00A0NASCIMENTO" in headers
    assert "NOME\u00A0DA\u00A0MAE" in headers

    resultado = _parse_bytes(conteudo, estudo_id="fb-nbsp")
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert len(c.linhas) == 41
    assert c.disponibilidade_colunas.sexo
    assert c.disponibilidade_colunas.cpf_titular
    assert c.disponibilidade_colunas.matricula
    assert c.disponibilidade_colunas.tipo_de_vida
    assert c.estatisticas.sexo_preenchido == 41
    assert sum(1 for l in c.linhas if l.sexo == "feminino") == 29
    assert sum(1 for l in c.linhas if l.sexo == "masculino") == 12
    parentesco = Counter(l.parentesco.value if l.parentesco else None for l in c.linhas)
    assert parentesco["titular"] == 27
    assert parentesco["conjuge"] == 8
    assert parentesco["filho"] == 5
    assert parentesco["companheiro"] == 1
    grupos = {l.vinculo_grupo_chave for l in c.linhas if l.vinculo_grupo_chave}
    assert len(grupos) == 27
    assert c.estatisticas.vinculos_resolvidos == 41
    assert sum(1 for l in c.linhas if l.matricula) == 36
    sem_mat = [l for l in c.linhas if not l.matricula]
    assert len(sem_mat) == 5
    assert all(l.parentesco and l.parentesco.value != "titular" for l in sem_mat)


def test_01_anistia_real_se_disponivel():
    path = _planilha_real(
        (
            "POSIÇÃO_CADASTRAL_SEGURADOS__SAÚDE_2.xlsx",
            "POSICAO_CADASTRAL_SEGURADOS__SAUDE_2.xlsx",
        ),
        glob_anistia=True,
    )
    if path is None:
        pytest.skip("Planilha Anistia real indisponível")
    from collections import Counter

    resultado = _parse_arquivo(path)
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert len(c.linhas) == 41
    assert c.disponibilidade_colunas.cpf_titular
    assert c.estatisticas.sexo_preenchido == 41
    assert sum(1 for l in c.linhas if l.sexo == "feminino") == 29
    assert sum(1 for l in c.linhas if l.sexo == "masculino") == 12
    parentesco = Counter(l.parentesco.value if l.parentesco else None for l in c.linhas)
    assert parentesco["titular"] == 27
    assert parentesco["conjuge"] == 8
    assert parentesco["filho"] == 5
    assert parentesco["companheiro"] == 1
    grupos = {l.vinculo_grupo_chave for l in c.linhas if l.vinculo_grupo_chave}
    assert len(grupos) == 27
    assert c.estatisticas.vinculos_resolvidos == 41
    assert sum(1 for l in c.linhas if l.matricula) == 36
    assert sum(1 for l in c.linhas if not l.matricula) == 5


def test_02_atef_3_sexo_sintetico():
    resultado = _parse_bytes(planilha_atef_3_sintetica(), estudo_id="atef")
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert len(c.linhas) == 3
    assert c.estatisticas.sexo_preenchido == 3
    assert sum(1 for l in c.linhas if l.sexo == "masculino") == 2
    assert sum(1 for l in c.linhas if l.sexo == "feminino") == 1


def test_02_atef_real_se_disponivel():
    path = _planilha_real(("ATEF_7.xlsx",))
    if path is None:
        pytest.skip("Planilha ATEF real indisponível")
    resultado = _parse_arquivo(path)
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert len(c.linhas) == 3
    assert c.estatisticas.sexo_preenchido == 3


def test_03_formato_reduzido_8_col_sexo_ausente_formato():
    resultado = _parse_bytes(planilha_12_vidas(), estudo_id="ivtec")
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert not c.disponibilidade_colunas.sexo
    assert c.estatisticas.sexo_preenchido == 0
    assert c.estatisticas.sexo_celula_vazia == 0
    assert all(l.sexo is None for l in c.linhas)


def test_04_cinco_dependentes_sem_matricula_agrupam_cpf():
    resultado = _parse_bytes(planilha_anistia_41_sintetica())
    c = resultado.candidata
    assert c is not None
    deps_sem_mat = [
        l
        for l in c.linhas
        if not l.matricula and l.parentesco and l.parentesco.value != "titular"
    ]
    assert len(deps_sem_mat) == 5
    assert all(l.vinculo_resolvido for l in deps_sem_mat)
    assert all(
        l.vinculo_grupo_chave and l.vinculo_grupo_chave.startswith("cpf:")
        for l in deps_sem_mat
    )
    for dep in deps_sem_mat:
        titular = next(
            t
            for t in c.linhas
            if t.parentesco
            and t.parentesco.value == "titular"
            and t.segurado
            and dep.titular_nome
            and dep.titular_nome.upper() in t.segurado.upper()
        )
        assert titular.vinculo_grupo_chave == dep.vinculo_grupo_chave


def test_05_gabarito_anistia_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"])
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_06_estudo_existente_sem_sexo_abre():
    rascunho = rascunho_demo_12_vidas()
    assert all(v.sexo is None for v in rascunho.vidas)
    compilado = compile(rascunho, policy_registry=default_registry)
    assert compilado.compilavel


def test_07_snapshot_aprovado_legivel(tmp_path: Path):
    rascunho = rascunho_demo_12_vidas()
    snap = _aprovar(tmp_path, rascunho)
    assert snap.estado == "aprovado"
    assert "rascunho" in snap.payload


def test_08_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    digest = hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    digest2 = hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    assert digest == digest2
    assert len(digest) == 64


def test_09_suite_regressao_importador_versao():
    from newport_app.models.siscor_import import IMPORTADOR_SISCOR_VERSAO

    assert IMPORTADOR_SISCOR_VERSAO == "siscor@2.4.0"


def test_10_sexo_coluna_presente_celulas_vazias():
    resultado = _parse_bytes(planilha_sexo_coluna_celulas_vazias())
    assert resultado.sucesso
    c = resultado.candidata
    assert c is not None
    assert c.disponibilidade_colunas.sexo
    assert c.estatisticas.sexo_preenchido == 2
    assert c.estatisticas.sexo_celula_vazia == 2
