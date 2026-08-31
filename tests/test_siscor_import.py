"""Testes unitários — importação SISCOR (parser e serviço)."""

from __future__ import annotations

import hashlib
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import Workbook

from newport_app.models.siscor_import import IMPORTADOR_SISCOR_VERSAO
from newport_app.repository.importacao_siscor import ImportacaoSiscorRepository
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.importacao_siscor import (
    ImportacaoRequerDecisaoError,
    ImportacaoSiscorService,
)
from newport_app.siscor_importer.constants import COLUNAS_OBRIGATORIAS
from newport_app.siscor_importer.money import valor_para_centavos
from newport_app.siscor_importer.normalize import normalizar_cabecalho
from newport_app.siscor_importer.parser import parse_planilha_siscor
from tests.fixtures.siscor.xlsx_builder import (
    gerar_planilha_siscor,
    linha_ficticia,
    planilha_12_vidas,
    planilha_41_vidas_2_planos,
    planilha_41_vidas_cabecalho_nbsp,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "siscor"


@pytest.fixture
def servico(tmp_path: Path) -> ImportacaoSiscorService:
    db = tmp_path / "estudos.db"
    repo = SQLiteStudyRepository(db)
    imp = ImportacaoSiscorRepository(tmp_path / "importacoes.db")
    return ImportacaoSiscorService(repo, imp, uploads_dir=tmp_path / "uploads")


def test_valor_para_centavos_usa_decimal_nao_float():
    assert valor_para_centavos(850.5) == 85050
    assert valor_para_centavos("850,50") == 85050
    assert valor_para_centavos("1.234,56") == 123456


def test_parse_12_vidas_todas_nao_confirmadas():
    conteudo = planilha_12_vidas()
    resultado = parse_planilha_siscor(
        conteudo,
        estudo_id="test-12",
        documento_id="doc-1",
    )
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert len(resultado.candidata.linhas) == 12
    assert resultado.candidata.estatisticas.planos_detectados == 1
    assert all(not linha.registro_confirmado for linha in resultado.candidata.linhas)
    assert resultado.candidata.documento_hash_sha256 == hashlib.sha256(conteudo).hexdigest()


def test_normalizar_cabecalho_converte_nbsp_e_colapsa_espacos():
    assert normalizar_cabecalho("DATA\u00A0DE\u00A0NASCIMENTO") == "DATA DE NASCIMENTO"
    assert normalizar_cabecalho("STATUS\u00A0SEGURADO") == "STATUS SEGURADO"
    assert normalizar_cabecalho("CPF\u00A0TITULAR") == "CPF TITULAR"
    assert normalizar_cabecalho("TIPO\u00A0DE\u00A0VIDA") == "TIPO DE VIDA"
    assert normalizar_cabecalho("NOME\u00A0DA\u00A0MAE") == "NOME DA MAE"
    assert normalizar_cabecalho("  CLIENTE\t\n  ") == "CLIENTE"
    assert normalizar_cabecalho("PLANO  \u2003  DEMO") == "PLANO DEMO"
    assert normalizar_cabecalho("\uFEFFSEXO") == "SEXO"
    assert normalizar_cabecalho("MATRÍCULA") == "MATRICULA"
    assert normalizar_cabecalho("matrícula") == "MATRICULA"
    assert normalizar_cabecalho("sexo") == "SEXO"


def test_parse_41_vidas_cabecalho_nbsp_50_colunas():
    conteudo = planilha_41_vidas_cabecalho_nbsp()
    resultado = parse_planilha_siscor(
        conteudo,
        estudo_id="test-nbsp",
        documento_id="doc-nbsp",
    )
    assert resultado.sucesso
    assert not any(e.codigo == "APP-SIS-F05" for e in resultado.erros_arquivo)
    candidata = resultado.candidata
    assert candidata is not None
    assert len(candidata.linhas) == 41
    assert candidata.estatisticas.planos_detectados == 2


def test_parse_41_vidas_dois_planos():
    conteudo = planilha_41_vidas_2_planos()
    resultado = parse_planilha_siscor(
        conteudo,
        estudo_id="test-41",
        documento_id="doc-41",
    )
    assert resultado.sucesso
    candidata = resultado.candidata
    assert candidata is not None
    assert len(candidata.linhas) == 41
    assert candidata.estatisticas.planos_detectados == 2
    assert len(candidata.subgrupos_sugeridos) == 2


def test_ids_opacos_sem_pii():
    conteudo = planilha_12_vidas()
    resultado = parse_planilha_siscor(
        conteudo,
        estudo_id="test-ids",
        documento_id="doc-ids",
    )
    assert resultado.candidata is not None
    for linha in resultado.candidata.linhas:
        uuid.UUID(linha.id)
        assert "+" not in linha.id
        assert linha.segurado not in linha.id


def test_proveniencia_extraida_desconhecida_nao_confirmada():
    conteudo = planilha_12_vidas()
    resultado = parse_planilha_siscor(
        conteudo,
        estudo_id="prov",
        documento_id="doc-prov",
    )
    linha = resultado.candidata.linhas[0]  # type: ignore[union-attr]
    vf = linha.valor_fatura
    assert vf is not None
    assert vf.price_basis.value == "desconhecido"
    assert vf.proveniencia.origem.value == "extraido"
    assert vf.proveniencia.extrator_versao == IMPORTADOR_SISCOR_VERSAO
    assert vf.proveniencia.confirmado is False
    assert vf.proveniencia.documento_id == "doc-prov"
    assert vf.proveniencia.linha_origem == linha.numero_linha


def test_erro_arquivo_vazio():
    resultado = parse_planilha_siscor(b"", estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    assert resultado.candidata is None
    assert any(e.codigo == "APP-SIS-F01" for e in resultado.erros_arquivo)


def test_erro_arquivo_nao_xlsx():
    resultado = parse_planilha_siscor(b"nao-e-xlsx", estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    assert any(e.codigo == "APP-SIS-F02" for e in resultado.erros_arquivo)


def test_erro_cabecalho_ausente():
    wb = Workbook()
    ws = wb.active
    ws.append(["CLIENTE", "SEGURADO"])
    buf = BytesIO()
    wb.save(buf)
    resultado = parse_planilha_siscor(buf.getvalue(), estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    assert any(e.codigo == "APP-SIS-F05" for e in resultado.erros_arquivo)


def test_erro_cabecalho_duplicado():
    wb = Workbook()
    ws = wb.active
    ws.append(list(COLUNAS_OBRIGATORIAS) + ["CLIENTE"])
    buf = BytesIO()
    wb.save(buf)
    resultado = parse_planilha_siscor(buf.getvalue(), estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    assert any(e.codigo == "APP-SIS-F04" for e in resultado.erros_arquivo)


def test_erro_sem_linhas_utilizaveis():
    wb = Workbook()
    ws = wb.active
    ws.append(list(COLUNAS_OBRIGATORIAS))
    buf = BytesIO()
    wb.save(buf)
    resultado = parse_planilha_siscor(buf.getvalue(), estudo_id="x", documento_id="d")
    assert not resultado.sucesso
    assert any(e.codigo == "APP-SIS-F06" for e in resultado.erros_arquivo)


def test_alertas_linha_nao_bloqueiam_candidata():
    linhas = [
        linha_ficticia(0, valor=0),
        linha_ficticia(1),
    ]
    linhas[0]["STATUS SEGURADO"] = "INATIVO"
    linhas[1]["SEGURADO"] = ""
    conteudo = gerar_planilha_siscor(linhas)
    resultado = parse_planilha_siscor(conteudo, estudo_id="alertas", documento_id="d")
    assert resultado.sucesso
    assert resultado.candidata is not None
    assert len(resultado.candidata.linhas) == 2
    codigos = {a.codigo for linha in resultado.candidata.linhas for a in linha.alertas}
    assert "APP-SIS-003" in codigos
    assert "APP-SIS-005" in codigos
    assert "APP-SIS-007" in codigos


def test_status_ativo_case_insensitive():
    linhas = [linha_ficticia(0)]
    linhas[0]["STATUS SEGURADO"] = "  ativo  "
    conteudo = gerar_planilha_siscor(linhas)
    resultado = parse_planilha_siscor(conteudo, estudo_id="st", documento_id="d")
    linha = resultado.candidata.linhas[0]  # type: ignore[union-attr]
    assert linha.status_normalizado == "ATIVO"
    assert linha.incluida_sugerida is True


def test_importacao_servico_estudo_novo(servico: ImportacaoSiscorService):
    out = servico.importar_planilha("novo-12", planilha_12_vidas(), titulo="Novo 12")
    assert out.sucesso
    assert out.resumo is not None
    assert out.resumo.estatisticas.total_linhas_lidas == 12
    conf = servico.obter_conferencia("novo-12")
    assert len(conf.linhas) == 12


def test_reimportacao_exige_decisao(servico: ImportacaoSiscorService):
    servico.importar_planilha("reimp", planilha_12_vidas(), titulo="Reimp")
    with pytest.raises(ImportacaoRequerDecisaoError) as exc:
        servico.importar_planilha("reimp", planilha_12_vidas())
    assert exc.value.opcoes == ["substituir"]


def test_confirmar_lote_aplica_rascunho_sem_tipo_fiscal(servico: ImportacaoSiscorService):
    servico.importar_planilha("lote", planilha_12_vidas(), titulo="Lote")
    resp = servico.confirmar_lote("lote")
    assert resp.confirmadas == 12
    assert resp.vidas_no_rascunho == 12
    rascunho = servico._estudos.obter_rascunho("lote")
    assert rascunho is not None
    assert len(rascunho.vidas) == 12
    assert all(sg.tipo_fiscal is None for sg in rascunho.subgrupos_atuais)
    assert all(sg.regime_copart_id is None for sg in rascunho.subgrupos_atuais)


def test_edicao_manual_reseta_confirmacao(servico: ImportacaoSiscorService):
    servico.importar_planilha("edit", planilha_12_vidas(), titulo="Edit")
    servico.confirmar_lote("edit")
    candidata = servico._importacoes.obter_ativa("edit")
    assert candidata is not None
    linha_id = candidata.linhas[0].id
    servico.atualizar_linha("edit", linha_id, segurado="Nome Alterado Fictício")
    candidata = servico._importacoes.obter_ativa("edit")
    assert candidata is not None
    linha = next(l for l in candidata.linhas if l.id == linha_id)
    assert linha.registro_confirmado is False
    assert linha.editado_manualmente is True


def test_fixtures_xlsx_versionadas_existem():
    doze = FIXTURES_DIR / "demo_12_vidas.xlsx"
    quarenta = FIXTURES_DIR / "demo_41_vidas_2_planos.xlsx"
    assert doze.is_file()
    assert quarenta.is_file()
    r12 = parse_planilha_siscor(doze.read_bytes(), estudo_id="f12", documento_id="f12")
    r41 = parse_planilha_siscor(quarenta.read_bytes(), estudo_id="f41", documento_id="f41")
    assert len(r12.candidata.linhas) == 12  # type: ignore[union-attr]
    assert len(r41.candidata.linhas) == 41  # type: ignore[union-attr]
    assert r41.candidata.estatisticas.planos_detectados == 2  # type: ignore[union-attr]
