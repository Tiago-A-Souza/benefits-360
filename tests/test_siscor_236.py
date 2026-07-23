"""Testes ETAPA 2.3.6 — correções SISCOR."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.config.runtime import ModoExecucao, LIMITE_UPLOAD_BYTES
from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    CampoConfirmavelBaseline,
    CampoConfirmavelPrecedencia,
    EscolhasEstudo,
    OpcaoPropostaRascunho,
    PriceBasisRascunho,
    RegimeCopartRascunho,
)
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_app.services.importacao_siscor import (
    ExclusaoSemMotivoError,
    ImportacaoSiscorService,
    LinhaIncompletaConfirmacaoError,
    ModoImportacaoInvalidoError,
)
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_motor.engine import calcular
from tests.fixtures.siscor.xlsx_builder import (
    gerar_planilha_siscor,
    linha_ficticia,
    planilha_12_vidas,
    planilha_com_formula_no_valor,
)


@pytest.fixture
def servico(tmp_path: Path) -> ImportacaoSiscorService:
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    return ImportacaoSiscorService(repo, imp, uploads_dir=tmp_path / "uploads")


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


def _importar(client: TestClient, estudo_id: str, xlsx: bytes, **params):
    files = {
        "arquivo": (
            "planilha.xlsx",
            xlsx,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    return client.post(f"/api/estudos/{estudo_id}/importar-siscor", files=files, params=params)


def test_modo_demo_usa_data_dir(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data_demo"
    monkeypatch.setenv("NEWPORT_MODO", "demo")
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(data_dir))
    import importlib
    import newport_app.config.paths as paths
    import newport_app.config.runtime as runtime

    importlib.reload(runtime)
    importlib.reload(paths)
    assert runtime.modo_execucao() == ModoExecucao.DEMO
    assert paths.caminho_banco_estudos() == data_dir / "newport_app.db"
    assert "runtime" not in str(paths.caminho_banco_estudos())


def test_modo_real_usa_private_runtime(monkeypatch, tmp_path: Path):
    private = tmp_path / "private"
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(private))
    import importlib
    import newport_app.config.paths as paths
    import newport_app.config.runtime as runtime

    importlib.reload(runtime)
    importlib.reload(paths)
    assert runtime.modo_execucao() == ModoExecucao.REAL
    assert paths.caminho_banco_estudos() == private / "estudos.db"
    assert paths.caminho_banco_importacoes() == private / "importacoes.db"


def test_estudo_real_nao_grava_em_data(monkeypatch, tmp_path: Path):
    data_dir = tmp_path / "data"
    private = tmp_path / "private"
    data_dir.mkdir()
    monkeypatch.setenv("NEWPORT_MODO", "real")
    monkeypatch.setenv("NEWPORT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("NEWPORT_PRIVATE_RUNTIME", str(private))
    import importlib
    import newport_app.config.paths as paths
    import newport_app.config.runtime as runtime

    importlib.reload(runtime)
    importlib.reload(paths)
    repo = SQLiteStudyRepository(paths.caminho_banco_estudos())
    from newport_app.siscor_mapper.apply import rascunho_vazio

    repo.salvar_rascunho(rascunho_vazio("real-1", "Estudo real"))
    assert (private / "estudos.db").is_file()
    assert not (data_dir / "newport_app.db").exists()


def test_formula_detectada_como_excecao():
    conteudo = planilha_com_formula_no_valor()
    resultado = parse_planilha_siscor(conteudo, estudo_id="f", documento_id="d")
    assert resultado.sucesso
    linha_formula = next(
        l for l in resultado.candidata.linhas  # type: ignore[union-attr]
        if l.numero_linha == 3
    )
    assert any(a.codigo == "APP-SIS-F07" for a in linha_formula.alertas)
    assert linha_formula.valor_centavos is None


def test_duplicidade_marca_todos_os_registros():
    linhas = [linha_ficticia(0), linha_ficticia(0)]
    linhas[1]["SEGURADO"] = linhas[0]["SEGURADO"]
    conteudo = gerar_planilha_siscor(linhas)
    resultado = parse_planilha_siscor(conteudo, estudo_id="dup", documento_id="d")
    assert resultado.candidata is not None
    assert all(
        any(a.codigo == "APP-SIS-006" for a in linha.alertas)
        for linha in resultado.candidata.linhas
    )


def test_valor_negativo_rejeitado():
    linhas = [linha_ficticia(0)]
    linhas[0]["VALOR"] = -100
    conteudo = gerar_planilha_siscor(linhas)
    resultado = parse_planilha_siscor(conteudo, estudo_id="neg", documento_id="d")
    linha = resultado.candidata.linhas[0]  # type: ignore[union-attr]
    assert any(a.codigo == "APP-SIS-012" for a in linha.alertas)


def test_operadora_ausente_e_excecao():
    linhas = [linha_ficticia(0)]
    linhas[0]["SEGURADORA"] = ""
    conteudo = gerar_planilha_siscor(linhas)
    resultado = parse_planilha_siscor(conteudo, estudo_id="op", documento_id="d")
    linha = resultado.candidata.linhas[0]  # type: ignore[union-attr]
    assert any(a.codigo == "APP-SIS-010" for a in linha.alertas)


def test_reimportacao_modo_invalido_rejeitado(servico: ImportacaoSiscorService):
    servico.importar_planilha("m", planilha_12_vidas(), titulo="M")
    with pytest.raises(ModoImportacaoInvalidoError):
        servico.importar_planilha("m", planilha_12_vidas(), modo="automatico")


def test_importacao_invalida_nao_desativa_anterior(servico: ImportacaoSiscorService, tmp_path: Path):
    servico.importar_planilha("est", planilha_12_vidas(), titulo="Est")
    antes = servico._importacoes.obter_ativa("est")
    assert antes is not None
    invalido = b"nao-xlsx"
    out = servico.importar_planilha("est", invalido, modo="substituir")
    assert not out.sucesso
    depois = servico._importacoes.obter_ativa("est")
    assert depois is not None
    assert depois.id == antes.id
    assert len(list((tmp_path / "uploads").glob("*.xlsx"))) == 1


def test_edicao_valor_ausente_historico_manual(servico: ImportacaoSiscorService):
    servico.importar_planilha("ed", planilha_12_vidas(), titulo="Ed")
    candidata = servico._importacoes.obter_ativa("ed")
    assert candidata is not None
    linha = candidata.linhas[0]
    linha.valor_centavos = None
    linha.valor_fatura = None
    servico._importacoes.salvar(candidata)
    servico.atualizar_linha("ed", linha.id, valor_centavos=85000)
    candidata = servico._importacoes.obter_ativa("ed")
    atualizada = next(l for l in candidata.linhas if l.id == linha.id)  # type: ignore[union-attr]
    assert atualizada.valor_centavos == 85000
    assert atualizada.historico_edicoes
    assert atualizada.historico_edicoes[-1].campo == "valor_centavos"
    assert not atualizada.registro_confirmado


def test_exclusao_exige_motivo(servico: ImportacaoSiscorService):
    servico.importar_planilha("ex", planilha_12_vidas(), titulo="Ex")
    candidata = servico._importacoes.obter_ativa("ex")
    linha_id = candidata.linhas[0].id  # type: ignore[union-attr]
    with pytest.raises(ExclusaoSemMotivoError):
        servico.atualizar_linha("ex", linha_id, excluida=True)


def test_confirmar_linha_incompleta_falha(servico: ImportacaoSiscorService):
    servico.importar_planilha("inc", planilha_12_vidas(), titulo="Inc")
    candidata = servico._importacoes.obter_ativa("inc")
    linha = candidata.linhas[0]  # type: ignore[union-attr]
    linha.plano = None
    servico._importacoes.salvar(candidata)
    with pytest.raises(LinhaIncompletaConfirmacaoError):
        servico.atualizar_linha("inc", linha.id, confirmar=True)


def test_troca_plano_remonta_subgrupos(servico: ImportacaoSiscorService):
    servico.importar_planilha("pl", planilha_12_vidas(), titulo="Pl")
    candidata = servico._importacoes.obter_ativa("pl")
    linha_id = candidata.linhas[0].id  # type: ignore[union-attr]
    servico.atualizar_linha("pl", linha_id, plano="Plano Novo Fictício")
    candidata = servico._importacoes.obter_ativa("pl")
    assert any(sg.plano_nome == "Plano Novo Fictício" for sg in candidata.subgrupos_sugeridos)  # type: ignore[union-attr]


def test_upload_limite_retorna_413(client: TestClient):
    client.post("/api/estudos", json={"id": "big", "titulo": "Big", "nome_empresa": "Big"})
    grande = b"PK" + b"0" * (LIMITE_UPLOAD_BYTES + 1)
    res = _importar(client, "big", grande)
    assert res.status_code == 413


def test_modo_invalido_api_retorna_400(client: TestClient):
    client.post("/api/estudos", json={"id": "modo", "titulo": "Modo", "nome_empresa": "Modo"})
    _importar(client, "modo", planilha_12_vidas())
    res = _importar(client, "modo", planilha_12_vidas(), modo="merge")
    assert res.status_code == 400


def _enriquecer_rascunho_pos_siscor(rascunho):
    demo = rascunho_demo_12_vidas()
    rascunho.regimes_copart = [RegimeCopartRascunho(id="regime-sem", tipo="sem")]
    for sg in rascunho.subgrupos_atuais:
        sg.tipo_fiscal = "seguradora"
        sg.regime_copart_id = "regime-sem"
        sg.fatura_price_basis = PriceBasisRascunho.EXCLUI_IOF
    for vida in rascunho.vidas:
        if vida.valor_fatura:
            vida.valor_fatura.price_basis = PriceBasisRascunho.EXCLUI_IOF
    rascunho.opcoes_proposta = demo.opcoes_proposta
    rascunho.cenarios = demo.cenarios
    if rascunho.subgrupos_atuais and rascunho.cenarios:
        sg_id = rascunho.subgrupos_atuais[0].id
        for cenario in rascunho.cenarios:
            for atrib in cenario.atribuicoes:
                if atrib.alvo_tipo == "subgrupo":
                    atrib.alvo_id = sg_id
    rascunho.escolhas = EscolhasEstudo(
        data_referencia_idade=date(2026, 6, 30),
        baseline_escolhido=CampoConfirmavelBaseline(valor="reajustado", confirmado=True),
        precedencia_atual_vida=CampoConfirmavelPrecedencia(
            valor="tabela_atual", confirmado=True
        ),
    )
    return rascunho


def test_documento_siscor_registrado_sem_bloqueio_b05(servico: ImportacaoSiscorService):
    servico.importar_planilha("doc", planilha_12_vidas(), titulo="Doc")
    servico.confirmar_lote("doc")
    rascunho = servico._estudos.obter_rascunho("doc")
    assert rascunho is not None
    assert len(rascunho.documentos_siscor) == 1
    assert rascunho.documentos_siscor[0].id
    rascunho = _enriquecer_rascunho_pos_siscor(rascunho)
    servico._estudos.salvar_rascunho(rascunho)
    resultado = compile(rascunho)
    assert resultado.compilavel
    assert resultado.compilado is not None
    motor = calcular(resultado.compilado.estudo_input, resultado.compilado.effective_policy)
    codigos = {v.codigo for v in motor.validacoes}
    assert "B-05" not in codigos
