"""Etapa 5 — inclusão manual de hospital fora dos principais.

Numeração = a do pedido (01–24). O item 25 do pedido é a suíte inteira, rodada à
parte; os testes `test_x*` cobrem os ajustes combinados depois (selos só na tela,
legenda dinâmica por CSV, sanitização de quem virou principal).
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from newport_app.api.main import create_app
from newport_app.models.draft import IncluidoRedeRascunho, SelecaoRedeRascunho
from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.presentation import rede_legenda
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.hospitais_principais import (
    CAMINHO_BASE,
    carregar_hospitais_principais,
)
from newport_app.presentation.html_renderer import render_html_completo
from newport_app.presentation.rede_apresentacao import (
    _id_linha_rede,
    montar_rede_apresentacao,
)
from newport_app.presentation.rede_matriz_hospital import carregar_base_rede_hospital
from newport_app.repository.sqlite import SQLiteStudyRepository
from newport_app.services.rede_inclusao import (
    InclusaoRedeInvalida,
    buscar_para_inclusao,
    incluir_manual,
)
from newport_app.services.rede_selecao import (
    descartar_incluidos_invalidos,
    sanitizar_selecao_rede,
)
from newport_app.services.rede_selecao_ui import montar_rede_selecao_ui, todos_ids_linha_rede
from newport_app.models.snapshot import SNAPSHOT_VERSAO

from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_rede_fase_d1 import _rascunho_dois_grupos_um_cenario

ROOT = Path(__file__).resolve().parents[1]
_XLSX = ROOT / "docs" / "SiscorNet_Comparativo_Nacional_Hospital_Laboratorio.xlsx"

pytestmark = pytest.mark.skipif(not _XLSX.is_file(), reason="base SiscorNet ausente")

SG_A = "sg-a"  # beneficiários no Rio de Janeiro
SG_B = "sg-b"  # beneficiários em São Paulo

# Não principal, no recorte do Rio, passa no critério (H PS).
ADVENTISTA = ("HOSP ADVENTISTA SILVESTRE", "RJ.RIO DE JANEIRO", "COSME VELHO")
# Fora do recorte (Acre) e sem as quatro especialidades (HPED PSPED).
URGIL = ("HOSP DA CRIANCA URGIL", "AC.RIO BRANCO", "CAPOEIRA")
# No recorte do Rio, sem as quatro especialidades (PSOFT).
OFTALMO = ("AMERICAS OFTALMOCENTER", "RJ.RIO DE JANEIRO", "BOTAFOGO")
# Sem as quatro; códigos HCELT HOESP (fora do CSV de legenda) e HONC (no CSV).
CTO_SAMARITANO = ("CTO SAMARITANO IPANEMA", "RJ.RIO DE JANEIRO", "IPANEMA")
# Principal do recorte do Rio: já está na tabela.
SAMARITANO = ("HOSP SAMARITANO", "RJ.RIO DE JANEIRO", "BOTAFOGO")
# Nenhum plano do estudo o cobre: todas as células ficam vazias.
OFTALMO_TIJUCA = ("AMERICAS OFTALMOCENTER", "RJ.RIO DE JANEIRO", "TIJUCA")

EID = "est-incl-manual"


# ---------------------------------------------------------------- utilidades


@pytest.fixture
def ctx(tmp_path: Path):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": EID})
    db = tmp_path / "incl.db"
    repo = SQLiteStudyRepository(db)
    repo.salvar_rascunho(rascunho)
    client = TestClient(create_app(repo=repo, seed_demos=False))
    return {"repo": repo, "client": client, "cen": cen_id, "db": db, "tmp": tmp_path}


def _corpo(chave: tuple[str, str, str]) -> dict:
    return {
        "prestador": chave[0],
        "municipio": chave[1],
        "bairro": chave[2],
    }


def _incluir(client, chave, status: int = 200):
    r = client.post(f"/api/estudos/{EID}/rede-selecao/incluidos", json=_corpo(chave))
    assert r.status_code == status, r.text
    return r.json()


def _remover(client, chave, status: int = 200):
    r = client.post(
        f"/api/estudos/{EID}/rede-selecao/incluidos/remover", json=_corpo(chave)
    )
    assert r.status_code == status, r.text
    return r.json()


def _ui(client) -> dict:
    r = client.get(f"/api/estudos/{EID}/rede-selecao")
    assert r.status_code == 200, r.text
    return r.json()


def _busca(client, q: str) -> dict:
    r = client.get(
        f"/api/estudos/{EID}/rede-selecao/busca", params={"q": q}
    )
    assert r.status_code == 200, r.text
    return r.json()


def _secao(ui: dict, sg: str) -> dict:
    return next(s for s in ui["secoes"] if s["subgrupo_id"] == sg)


def _linhas(ui: dict, sg: str) -> list[dict]:
    return [ln for b in _secao(ui, sg)["blocos"] for ln in b["linhas"]]


def _achar(linhas: list[dict], chave) -> dict | None:
    return next(
        (
            ln
            for ln in linhas
            if (ln["prestador"], ln["municipio"], ln["bairro"]) == chave
        ),
        None,
    )


def _resultado(busca: dict, chave) -> dict:
    achado = next(
        r
        for r in busca["resultados"]
        if (r["prestador"], r["municipio"], r["bairro"]) == chave
    )
    return achado


def _lid(sg: str, chave) -> str:
    return _id_linha_rede(chave[0], chave[1], chave[2], subgrupo_id=sg)


def _rascunho_com_incluidos(*chaves: tuple[str, str, str]):
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": EID})
    rascunho.selecao_rede = SelecaoRedeRascunho(
        incluidos=[
            IncluidoRedeRascunho(prestador=c[0], municipio=c[1], bairro=c[2])
            for c in chaves
        ]
    )
    return rascunho, cen_id


def _doc(rascunho, cen_id, **kw):
    doc = montar_rede_apresentacao(rascunho, [cen_id], **kw)
    assert doc is not None
    return doc


def _linhas_doc(doc, sg: str):
    return [
        ln
        for sec in doc.secoes
        if sec.subgrupo_id == sg
        for b in sec.blocos
        for ln in b.linhas
    ]


def _html_servico(tmp_path: Path, rascunho, cen_id: str, nome: str) -> str:
    """Documento gerado pelo caminho real da etapa 6 (serviço de apresentação)."""
    from tests.test_fase2_tarefa2 import _aprovar, _stack

    repo, _, snap_svc, apres = _stack(tmp_path, nome)
    snap = _aprovar(repo, snap_svc, rascunho)
    req = GerarApresentacaoRequest(
        modo="completo", propostas_selecionadas=[cen_id], ressalvas=[]
    )
    res = apres.gerar_html(rascunho.id, snap.id, req)
    return (apres._entregaveis_dir / res.caminho_relativo).read_text(encoding="utf-8")


def _trecho_linha(html: str, lid: str) -> str:
    m = re.search(rf"<tr class='p-rede' data-rede-id='{lid}'.*?</tr>", html, re.S)
    assert m, f"linha {lid} ausente do documento"
    return m.group(0)


def _rede(html: str) -> str:
    return html.split('id="visao-rede"', 1)[-1]


def _legenda(html: str) -> str:
    m = re.search(r"<div class='rede-legenda'><p>(.*?)</p>", html, re.S)
    assert m
    return m.group(1)


# ------------------------------------------------------------------ A busca


def test_01_busca_acha_prestador_que_nao_e_principal(ctx):
    base = carregar_base_rede_hospital()
    p = next(x for x in base.prestadores if x.chave == ADVENTISTA)
    ent = carregar_hospitais_principais(
        prestadores_matriz=base.prestadores
    ).por_prestador_matriz.get(p.chave)
    assert not (ent and ent.principal)  # premissa: não é principal
    b = _busca(ctx["client"], "adventista silvestre")
    r = _resultado(b, ADVENTISTA)
    assert r["ja_na_tabela"] is False
    assert r["incluido_manual"] is False


def test_02_busca_acha_prestador_fora_do_recorte_com_aviso(ctx):
    b = _busca(ctx["client"], "hosp da crianca urgil")
    r = _resultado(b, URGIL)
    assert r["fora_recorte"] is True  # sg-a é Rio de Janeiro; URGIL é Rio Branco/AC
    ui = _ui(ctx["client"])
    assert _achar(_linhas(ui, SG_A), URGIL) is None  # e continua fora da tabela


def test_03_busca_acha_prestador_sem_as_quatro_especialidades(ctx):
    b = _busca(ctx["client"], "oftalmocenter")
    r = _resultado(b, OFTALMO)
    assert r["fora_criterio"] is True
    assert r["celulas"], "tem cobertura real, com o código real da base"
    assert not r["sem_cobertura"]
    assert any("PSOFT" in v for v in r["celulas"].values())


def test_04_resultado_mostra_a_cobertura_em_cada_plano_distinto_do_estudo(ctx):
    ui = _ui(ctx["client"])
    planos_secoes = {
        (c["operadora"], c["plano_nome"])
        for s in ui["secoes"]
        for c in s["colunas"]
    }
    b = _busca(ctx["client"], "adventista silvestre")
    planos_busca = [(c["operadora"], c["plano_nome"]) for c in b["colunas"]]
    assert len(planos_busca) == len(set(planos_busca))  # cada plano uma vez só
    assert set(planos_busca) == planos_secoes  # S750, ONE S2500 e a proposta
    nomes = {n for _, n in planos_busca}
    assert {"AMIL S750 - Apto.", "AMIL ONE S2500 - Apto."} <= nomes
    r = _resultado(b, ADVENTISTA)
    assert set(r["celulas"]) <= {c["chave"] for c in b["colunas"]}
    assert r["celulas"] and all(
        set(v.split()) <= {"H", "HD", "M", "PS"} for v in r["celulas"].values()
    )
    # mesmos códigos da tabela: o que o resultado promete é o que entra depois
    por_chave = {c["chave"]: (c["operadora"], c["plano_nome"]) for c in b["colunas"]}
    prometido = {por_chave[k]: v for k, v in r["celulas"].items()}
    ui2 = _incluir(ctx["client"], ADVENTISTA)
    for sec in ui2["secoes"]:
        ln = _achar(_linhas(ui2, sec["subgrupo_id"]), ADVENTISTA)
        for col in sec["colunas"]:
            texto = ln["celulas"].get(col["chave"], "")
            assert texto == prometido.get((col["operadora"], col["plano_nome"]), "")


def test_05_tabela_nao_muda_enquanto_so_busca(ctx):
    """Destaque: buscar não altera a tabela, o rascunho nem o CSV de principais."""
    antes_ui = _ui(ctx["client"])
    with ctx["repo"]._connect() as conn:
        antes_db = conn.execute(
            "SELECT payload FROM rascunhos WHERE id = ?", (EID,)
        ).fetchone()["payload"]
    csv_antes = hashlib.sha256(CAMINHO_BASE.read_bytes()).hexdigest()

    for q in ("adventista", "urgil", "oftalmocenter", "einstein", "samaritano"):
        _busca(ctx["client"], q)
        _busca(ctx["client"], q)

    assert _ui(ctx["client"]) == antes_ui
    with ctx["repo"]._connect() as conn:
        depois_db = conn.execute(
            "SELECT payload FROM rascunhos WHERE id = ?", (EID,)
        ).fetchone()["payload"]
    assert depois_db == antes_db
    assert hashlib.sha256(CAMINHO_BASE.read_bytes()).hexdigest() == csv_antes


# ----------------------------------------------------------------- A inclusão


def test_06_incluir_faz_o_prestador_aparecer_no_bloco_do_municipio(ctx):
    ui = _incluir(ctx["client"], ADVENTISTA)
    bloco = next(
        b
        for b in _secao(ui, SG_A)["blocos"]
        if any(
            (ln["prestador"], ln["municipio"], ln["bairro"]) == ADVENTISTA
            for ln in b["linhas"]
        )
    )
    assert bloco["titulo"] == "Rio De Janeiro · RJ"
    assert all(ln["municipio"] == "RJ.RIO DE JANEIRO" for ln in bloco["linhas"])


def test_07_municipio_sem_bloco_ganha_bloco_novo(ctx):
    antes = {b["titulo"] for b in _secao(_ui(ctx["client"]), SG_A)["blocos"]}
    assert "Rio Branco · AC" not in antes
    ui = _incluir(ctx["client"], URGIL)
    blocos = {b["titulo"]: b for b in _secao(ui, SG_A)["blocos"]}
    assert "Rio Branco · AC" in blocos
    assert [ln["prestador"] for ln in blocos["Rio Branco · AC"]["linhas"]] == [URGIL[0]]


def test_08_incluido_aparece_marcado_como_manual(ctx):
    ui = _incluir(ctx["client"], URGIL)
    ln = _achar(_linhas(ui, SG_A), URGIL)
    assert ln["manual"] is True
    assert ln["fora_criterio"] is True  # sem as quatro especialidades
    assert any("HPED" in v and "PSPED" in v for v in ln["celulas"].values())
    ui2 = _incluir(ctx["client"], ADVENTISTA)
    ln2 = _achar(_linhas(ui2, SG_A), ADVENTISTA)
    assert ln2["manual"] is True and ln2["fora_criterio"] is False
    # os principais não ganham marca nenhuma
    outros = [x for x in _linhas(ui2, SG_A) if not x["manual"]]
    assert outros and not any(x["fora_criterio"] for x in outros)


def test_09_remover_a_inclusao_tira_o_prestador_da_tabela(ctx):
    base = _ui(ctx["client"])
    _incluir(ctx["client"], URGIL)
    ui = _remover(ctx["client"], URGIL)
    assert _achar(_linhas(ui, SG_A), URGIL) is None
    assert "Rio Branco · AC" not in {b["titulo"] for b in _secao(ui, SG_A)["blocos"]}
    assert ui["secoes"] == base["secoes"]  # volta exatamente ao que era
    assert _ui(ctx["client"])["secoes"] == base["secoes"]
    # remover o que não existe é 404 (nada silencioso)
    _remover(ctx["client"], URGIL, status=404)


def test_10_campo_unico_o_hospital_entra_em_todas_as_secoes(ctx):
    """Destaque: um único «Incluir» vale para o estudo — entra em S750 e em ONE S2500."""
    ui0 = _ui(ctx["client"])
    assert _achar(_linhas(ui0, SG_A), ADVENTISTA) is None
    assert _achar(_linhas(ui0, SG_B), ADVENTISTA) is None
    ui = _incluir(ctx["client"], ADVENTISTA)  # uma chamada, sem seção
    assert _achar(_linhas(ui, SG_A), ADVENTISTA)["manual"] is True
    assert _achar(_linhas(ui, SG_B), ADVENTISTA)["manual"] is True
    # cada tabela tem o seu id (o escopo da exclusão continua por seção)
    assert _lid(SG_A, ADVENTISTA) != _lid(SG_B, ADVENTISTA)
    b = _busca(ctx["client"], "adventista silvestre")
    r = _resultado(b, ADVENTISTA)
    assert r["incluido_manual"] is True and r["secoes_a_incluir"] == []
    assert len(r["secoes_ja_presentes"]) == 2
    # remover tira das duas
    ui3 = _remover(ctx["client"], ADVENTISTA)
    assert _achar(_linhas(ui3, SG_A), ADVENTISTA) is None
    assert _achar(_linhas(ui3, SG_B), ADVENTISTA) is None


def test_11_inclusao_persiste_sair_do_estudo_e_voltar(ctx):
    _incluir(ctx["client"], URGIL)
    # «sair e voltar»: outro repositório e outro app sobre o mesmo banco
    repo2 = SQLiteStudyRepository(ctx["db"])
    client2 = TestClient(create_app(repo=repo2, seed_demos=False))
    ln = _achar(_linhas(_ui(client2), SG_A), URGIL)
    assert ln is not None and ln["manual"] is True
    sel = repo2.obter_rascunho(EID).selecao_rede
    assert [i.prestador for i in sel.incluidos] == [URGIL[0]]


def test_12_incluido_aparece_no_documento_exportado(ctx):
    rascunho, cen_id = _rascunho_com_incluidos(ADVENTISTA, URGIL)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "t12")
    rede = _rede(html)
    assert "Rio Branco · AC" in rede
    for chave in (ADVENTISTA, URGIL):
        assert f"data-rede-id='{_lid(SG_A, chave)}'" in rede


# ------------------------------------------------------------- A persistência


def test_13_rascunho_guarda_incluidos_ao_lado_de_excluidos(ctx):
    ui = _incluir(ctx["client"], URGIL)
    principal = next(ln for ln in _linhas(ui, SG_A) if not ln["manual"])
    r = ctx["client"].put(
        f"/api/estudos/{EID}/rede-selecao",
        json={"excluidos": [principal["linha_id"]], "revisada": True},
    )
    assert r.status_code == 200, r.text
    sel = ctx["repo"].obter_rascunho(EID).selecao_rede
    assert sel.excluidos == [principal["linha_id"]]
    assert [i.prestador for i in sel.incluidos] == [URGIL[0]]  # o PUT não apagou
    bruto = ctx["repo"].obter_rascunho(EID).model_dump(mode="json")["selecao_rede"]
    assert set(bruto) == {"excluidos", "incluidos", "revisada"}


def test_14_sanitizar_selecao_rede_nao_apaga_os_incluidos(ctx):
    """Destaque: os incluidos NÃO estão na visão dos principais — validar contra ela os apagaria."""
    rascunho, cen_id = _rascunho_com_incluidos(ADVENTISTA, URGIL)
    visao = todos_ids_linha_rede(rascunho, incluir_manuais=False)
    assert _lid(SG_A, ADVENTISTA) not in visao  # premissa: é inclusão de verdade
    assert _lid(SG_A, URGIL) not in visao
    principal = next(iter(visao))
    rascunho.selecao_rede = rascunho.selecao_rede.model_copy(
        update={"excluidos": [principal, "id-que-nao-existe"], "revisada": True}
    )
    # 1) contra a visão dos principais, sem informar a base: incluidos intactos
    sanitizar_selecao_rede(rascunho, visao)
    assert len(rascunho.selecao_rede.incluidos) == 2
    assert rascunho.selecao_rede.excluidos == [principal]  # só o inválido saiu
    # 2) contra a base completa: continuam válidos
    base = carregar_base_rede_hospital()
    sanitizar_selecao_rede(
        rascunho, visao, chaves_base=base.chaves_prestadores, ids_visao_calculada=visao
    )
    assert len(rascunho.selecao_rede.incluidos) == 2
    # 3) por salvar/carregar do banco (o caminho real)
    repo = SQLiteStudyRepository(ctx["tmp"] / "t14.db")
    repo.salvar_rascunho(rascunho)
    assert len(repo.obter_rascunho(EID).selecao_rede.incluidos) == 2
    # sem excluídos nem revisada, só com incluidos, a seleção não é descartada
    rascunho.selecao_rede = SelecaoRedeRascunho(incluidos=rascunho.selecao_rede.incluidos)
    sanitizar_selecao_rede(rascunho, visao)
    assert rascunho.selecao_rede is not None and len(rascunho.selecao_rede.incluidos) == 2


def test_15_incluido_cujo_prestador_sumiu_da_base_e_descartado(ctx):
    rascunho, _ = _rascunho_com_incluidos(ADVENTISTA)
    fantasma = IncluidoRedeRascunho(
        prestador="HOSPITAL QUE FECHOU", municipio="RJ.RIO DE JANEIRO", bairro="CENTRO"
    )
    duplicado = IncluidoRedeRascunho(
        prestador=ADVENTISTA[0], municipio=ADVENTISTA[1], bairro=ADVENTISTA[2]
    )
    rascunho.selecao_rede = rascunho.selecao_rede.model_copy(
        update={"incluidos": [*rascunho.selecao_rede.incluidos, fantasma, duplicado]}
    )
    base = carregar_base_rede_hospital()
    visao = todos_ids_linha_rede(rascunho, incluir_manuais=False)
    sanitizar_selecao_rede(
        rascunho, visao, chaves_base=base.chaves_prestadores, ids_visao_calculada=visao
    )
    assert [i.prestador for i in rascunho.selecao_rede.incluidos] == [ADVENTISTA[0]]
    # e no caminho real (salvar no banco) o que sumiu da base também sai
    rascunho2, _ = _rascunho_com_incluidos(ADVENTISTA)
    rascunho2.selecao_rede = rascunho2.selecao_rede.model_copy(
        update={"incluidos": [*rascunho2.selecao_rede.incluidos, fantasma]}
    )
    repo = SQLiteStudyRepository(ctx["tmp"] / "t15.db")
    repo.salvar_rascunho(rascunho2)
    assert [i.prestador for i in repo.obter_rascunho(EID).selecao_rede.incluidos] == [
        ADVENTISTA[0]
    ]


# ------------------------------------------------------------------ A contagem


def _contagem_bloco(doc, sg: str, titulo: str) -> tuple[int, dict[str, int]]:
    sec = next(s for s in doc.secoes if s.subgrupo_id == sg)
    b = next(x for x in sec.blocos if x.titulo == titulo)
    return len(b.linhas), dict(b.contagem_por_coluna)


def test_16_cobertos_do_bloco_conta_tambem_os_incluidos(ctx):
    rascunho, cen_id = _rascunho_com_incluidos()
    rascunho.selecao_rede = None
    antes = _doc(rascunho, cen_id)
    n0, c0 = _contagem_bloco(antes, SG_A, "Rio De Janeiro · RJ")
    rascunho_com, _ = _rascunho_com_incluidos(ADVENTISTA)
    depois = _doc(rascunho_com, cen_id)
    n1, c1 = _contagem_bloco(depois, SG_A, "Rio De Janeiro · RJ")
    ln = next(x for x in _linhas_doc(depois, SG_A) if x.manual)
    esperado = {k: c0[k] + (1 if (ln.celulas.get(k) or "").strip() else 0) for k in c0}
    assert c1 == esperado and c1 != c0
    # a linha «Cobertos» impressa no documento acompanha
    html = _html_servico(ctx["tmp"], rascunho_com, cen_id, "t16")
    from tests.test_rede_etapa5_alternativa import (
        _contagens_esperadas_doc,
        _valores_cont_rede_tabelas,
    )

    assert _valores_cont_rede_tabelas(html) == _contagens_esperadas_doc(
        _doc(rascunho_com, cen_id, excluidos=set())
    )


def test_17_contador_de_linhas_visiveis_acompanha(ctx):
    ui0 = _ui(ctx["client"])
    n0, n0b = len(_linhas(ui0, SG_A)), len(_linhas(ui0, SG_B))
    doc0 = _doc(ctx["repo"].obter_rascunho(EID), ctx["cen"])
    total0 = next(s for s in doc0.secoes if s.subgrupo_id == SG_A).total_linhas
    ui1 = _incluir(ctx["client"], ADVENTISTA)
    assert len(_linhas(ui1, SG_A)) == n0 + 1
    assert len(_linhas(ui1, SG_B)) == n0b + 1  # entra em todas as seções
    doc1 = _doc(ctx["repo"].obter_rascunho(EID), ctx["cen"])
    sec1 = next(s for s in doc1.secoes if s.subgrupo_id == SG_A)
    assert sec1.total_linhas == total0 + 1
    # o «N prestadores» do cabeçalho do bloco também
    n_bloco0, _ = _contagem_bloco(doc0, SG_A, "Rio De Janeiro · RJ")
    n_bloco1, _ = _contagem_bloco(doc1, SG_A, "Rio De Janeiro · RJ")
    assert n_bloco1 == n_bloco0 + 1
    ui2 = _remover(ctx["client"], ADVENTISTA)
    assert len(_linhas(ui2, SG_A)) == n0 and len(_linhas(ui2, SG_B)) == n0b


# --------------------------------------------------------------- Não regressão


def test_18_gabaritos_valor_a_valor_com_inclusao_manual(tmp_path):
    from tests.test_fase5_faixas_por_grupo import test_12_gabaritos_valor_por_valor
    from tests.test_paridade_matriz_html import (
        _calcular_matriz,
        _rascunho_dois_planos_gabarito,
        test_gabarito_dois_planos_vigente_e_reajuste,
    )
    from tests.test_tipo_fiscal_sem_default import (
        test_amil_operadora_sem_iof_totais_ivtec,
    )

    test_12_gabaritos_valor_por_valor(tmp_path)
    test_gabarito_dois_planos_vigente_e_reajuste(1200)  # Anistia 12%: 48.479,31 / 29.386,76 / 19.092,55
    test_amil_operadora_sem_iof_totais_ivtec()  # IVTEC 3.741,89 e 5.652,04

    # a inclusão manual não mexe no cálculo: mesmos valores com e sem ela
    sem = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    com = sem.model_copy(deep=True)
    com.selecao_rede = SelecaoRedeRascunho(
        incluidos=[
            IncluidoRedeRascunho(
                prestador=ADVENTISTA[0], municipio=ADVENTISTA[1], bairro=ADVENTISTA[2]
            )
        ]
    )
    m_sem, _ = _calcular_matriz(sem)
    m_com, _ = _calcular_matriz(com)
    assert m_sem.model_dump() == m_com.model_dump()
    por_id = {p.subgrupo_id: p.reajustado_centavos for p in m_com.planos_atuais}
    assert por_id["sg-a"] == 2_938_676  # R$ 29.386,76
    assert por_id["sg-b"] == 1_909_255  # R$ 19.092,55
    assert sum(por_id.values()) == 4_847_931  # R$ 48.479,31


def test_19_exclusao_continua_funcionando_como_antes(ctx):
    ui = _incluir(ctx["client"], ADVENTISTA)
    principal = next(ln for ln in _linhas(ui, SG_A) if not ln["manual"])
    manual = _achar(_linhas(ui, SG_A), ADVENTISTA)
    r = ctx["client"].put(
        f"/api/estudos/{EID}/rede-selecao",
        json={"excluidos": [principal["linha_id"], manual["linha_id"]], "revisada": True},
    )
    assert r.status_code == 200 and set(r.json()["excluidos"]) == {
        principal["linha_id"],
        manual["linha_id"],
    }
    rascunho = ctx["repo"].obter_rascunho(EID)
    doc = _doc(rascunho, ctx["cen"], excluidos=set(rascunho.selecao_rede.excluidos))
    ids_doc = {ln.linha_id for ln in _linhas_doc(doc, SG_A)}
    assert principal["linha_id"] not in ids_doc  # exclusão de principal, como antes
    assert manual["linha_id"] not in ids_doc  # e a de um incluído à mão
    # a tela ainda mostra as duas, desmarcadas
    ui2 = _ui(ctx["client"])
    assert {ln["linha_id"] for ln in _linhas(ui2, SG_A)} >= {principal["linha_id"], manual["linha_id"]}
    assert {ln["linha_id"]: ln["incluido"] for ln in _linhas(ui2, SG_A)}[principal["linha_id"]] is False


def test_20_documento_continua_sem_script_e_sem_controles(ctx):
    """Destaque: o HTML do cliente não ganha script nem controle com a inclusão manual."""
    rascunho, cen_id = _rascunho_com_incluidos(URGIL, ADVENTISTA, OFTALMO)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "t20")
    assert "<script" not in html.lower()
    rede = _rede(html)
    for proibido in (
        "rede-btn-confirmar",
        "<input",
        "<button",
        "<select",
        "data-unlock",
        "sandbox",
        "contenteditable",
    ):
        assert proibido not in rede.lower(), proibido


def test_21_as_quatro_abas_anteriores_inalteradas(ctx):
    from tests.test_rede_documento_estatico import test_05_quatro_abas_anteriores_intactas

    test_05_quatro_abas_anteriores_intactas(ctx["tmp"])
    rascunho, cen_id = _rascunho_com_incluidos(URGIL)
    sem = rascunho.model_copy(deep=True)
    sem.selecao_rede = None
    snap = _aprovar_anistia(ctx["tmp"], sem)
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=[cen_id])
    html_sem = render_html_completo(vm, vm, vm, rede=_doc(sem, cen_id))
    html_com = render_html_completo(vm, vm, vm, rede=_doc(rascunho, cen_id))
    abas = ("visao-resumo", "visao-faixas", "visao-benef", "visao-regras")
    for aba in abas:
        pat = rf'id="{aba}"[^>]*>(.*?)</section>'
        a, b = re.search(pat, html_sem, re.S), re.search(pat, html_com, re.S)
        assert a and b and a.group(1) == b.group(1), aba
    assert _rede(html_sem) != _rede(html_com)  # só a rede muda


def test_22_rascunhos_do_banco_continuam_carregando_e_compilando():
    r = subprocess.run(
        [sys.executable, "scripts/verificar_rascunhos_do_banco.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "FALHAM_CARGA=0" in r.stdout


def test_23_hashes_de_snapshot_intactos_e_versao_nao_sobe(ctx):
    """Destaque de relato: o hash cheio sai do script; a versão segue 2.8.0."""
    r = subprocess.run(
        [sys.executable, "scripts/verificar_hashes_snapshots.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    assert "HASH_DIVERGENTE=0" in r.stdout
    assert SNAPSHOT_VERSAO == "2.8.0"
    # Sem inclusões o rascunho serializa EXATAMENTE como antes do campo existir
    # (o rascunho inteiro entra no conteúdo canônico do snapshot): hash idêntico.
    sel = SelecaoRedeRascunho(excluidos=["x"], revisada=True)
    assert set(sel.model_dump(mode="json")) == {"excluidos", "revisada"}
    assert '"incluidos"' not in sel.model_dump_json()
    assert SelecaoRedeRascunho.model_validate_json(sel.model_dump_json()) == sel
    # estudo sem inclusão: mesmo hash com e sem o mecanismo (selecao vazia = None)
    base_r, _ = _rascunho_com_incluidos()
    base_r.selecao_rede = None
    vazio = base_r.model_copy(deep=True)
    vazio.selecao_rede = SelecaoRedeRascunho()
    (ctx["tmp"] / "a").mkdir()
    (ctx["tmp"] / "b").mkdir()
    h_a = _aprovar_anistia(ctx["tmp"] / "a", base_r).hash_sha256
    assert h_a == _aprovar_anistia(ctx["tmp"] / "b", vazio).hash_sha256
    # Com inclusão o conteúdo muda — como já acontece com `excluidos` — e o hash
    # acompanha. É formato novo só para quem usa; não é preciso subir a versão.
    rascunho, _ = _rascunho_com_incluidos(URGIL)
    (ctx["tmp"] / "c").mkdir()
    assert _aprovar_anistia(ctx["tmp"] / "c", rascunho).hash_sha256 != h_a

def test_24_simular_rede_continua_funcionando(ctx):
    r = ctx["client"].get("/api/simular-rede/opcoes")
    assert r.status_code == 200 and r.json()["total_prestadores"] > 1000
    r2 = ctx["client"].get("/api/simular-rede/por-hospital", params={"q": "samaritano"})
    assert r2.status_code == 200 and r2.json()["total_linhas"] > 0


# ------------------------------------- Ajustes combinados depois (test_x*)


def test_x01_selos_so_na_tela_documento_sem_manual_nem_fora_do_criterio(ctx):
    rascunho, cen_id = _rascunho_com_incluidos(URGIL, OFTALMO)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x01")
    rede = _rede(html)
    for rotulo in ("Manual", "Fora do critério", "fora do critério", "cod-cru", "selo", "Remover"):
        assert rotulo not in rede, rotulo
    # o incluído à mão é uma linha como as outras: mesma estrutura de célula
    linha = _trecho_linha(rede, _lid(SG_A, URGIL))
    outra = _trecho_linha(rede, next(ln.linha_id for ln in _linhas_doc(_doc(rascunho, cen_id), SG_A) if not ln.manual))
    assert re.sub(r">[^<]*<", "><", linha).count("<td") == re.sub(r">[^<]*<", "><", outra).count("<td")
    assert "<td class='rede-col-plano on'>HPED PSPED</td>" in linha


def test_x02_codigo_cru_no_documento_tem_o_mesmo_estilo_dos_demais(ctx):
    rascunho, cen_id = _rascunho_com_incluidos(OFTALMO)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x02")
    linha = _trecho_linha(_rede(html), _lid(SG_A, OFTALMO))
    assert "<td class='rede-col-plano on'>PSOFT</td>" in linha
    assert "italic" not in linha and "style=" not in linha and "<span" not in linha.split("</td>", 1)[1]
    # a regra de cinza itálico existe só no CSS da tela, não no do documento
    assert "cod-cru" not in html
    css = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    assert ".cod-cru" in css


def test_x03_hospital_que_passa_no_criterio_mostra_so_as_siglas(ctx):
    """Mesmo hospital, mesmo texto, venha do filtro de principais ou da inclusão à mão."""
    base = carregar_base_rede_hospital()
    principais = carregar_hospitais_principais(prestadores_matriz=base.prestadores)
    rascunho, cen_id = _rascunho_com_incluidos(ADVENTISTA)
    ln = next(x for x in _linhas_doc(_doc(rascunho, cen_id), SG_A) if x.manual and x.prestador == ADVENTISTA[0])
    assert ln.fora_criterio is False
    for v in ln.celulas.values():
        assert set(v.split()) <= {"H", "HD", "M", "PS"}
    # um principal do mesmo recorte também só usa siglas padrão
    for outro in _linhas_doc(_doc(rascunho, cen_id), SG_A):
        if not outro.manual:
            for v in outro.celulas.values():
                assert set(v.replace("—", "").split()) <= {"H", "HD", "M", "PS"}
    del principais


def test_x04_hospital_que_virou_principal_em_todas_as_secoes_e_descartado(ctx):
    """Ajuste 4: sai de incluidos[] só quando já está na visão calculada de TODAS as seções."""
    rascunho, cen_id = _rascunho_com_incluidos(SAMARITANO, ADVENTISTA)
    visao = todos_ids_linha_rede(rascunho, incluir_manuais=False)
    assert _lid(SG_A, SAMARITANO) in visao  # principal do recorte do Rio (seção A)
    assert _lid(SG_B, SAMARITANO) not in visao  # mas não do de São Paulo (seção B)
    base = carregar_base_rede_hospital()
    # falta na seção B: a inclusão continua valendo
    descartar_incluidos_invalidos(rascunho, base.chaves_prestadores, visao)
    assert [i.prestador for i in rascunho.selecao_rede.incluidos] == [SAMARITANO[0], ADVENTISTA[0]]
    # principal em todas as seções com tabela: sai
    visao_total = visao | {_lid(SG_B, SAMARITANO)}
    descartar_incluidos_invalidos(rascunho, base.chaves_prestadores, visao_total)
    assert [i.prestador for i in rascunho.selecao_rede.incluidos] == [ADVENTISTA[0]]


def test_x04b_incluir_o_que_ja_esta_em_todas_as_secoes_e_recusado(ctx, monkeypatch):
    from newport_app.services import rede_inclusao

    rascunho = ctx["repo"].obter_rascunho(EID)
    todos = {_lid(SG_A, SAMARITANO), _lid(SG_B, SAMARITANO)}
    monkeypatch.setattr(
        rede_inclusao, "_visao_calculada", lambda r: {SG_A: set(todos), SG_B: set(todos)}
    )
    with pytest.raises(InclusaoRedeInvalida, match="já está na tabela de todas as seções"):
        incluir_manual(rascunho, *SAMARITANO)


def test_x05_incluir_duas_vezes_e_prestador_inexistente_sao_recusados(ctx):
    _incluir(ctx["client"], ADVENTISTA)
    r = ctx["client"].post(
        f"/api/estudos/{EID}/rede-selecao/incluidos", json=_corpo(ADVENTISTA)
    )
    assert r.status_code == 422 and "já foi incluído" in r.json()["detail"]
    r3 = ctx["client"].post(
        f"/api/estudos/{EID}/rede-selecao/incluidos",
        json=_corpo(("NAO EXISTE", "RJ.RIO DE JANEIRO", "")),
    )
    assert r3.status_code == 422


def test_x06_busca_exige_minimo_de_letras_e_ignora_acento_e_caixa(ctx):
    r = ctx["client"].get(
        f"/api/estudos/{EID}/rede-selecao/busca", params={"q": "a"}
    )
    assert r.status_code == 422
    a = _busca(ctx["client"], "AMÉRICAS oftalmocenter")
    b = _busca(ctx["client"], "americas OFTALMOCENTER")
    assert a["resultados"] == b["resultados"] and a["resultados"]
    assert len(_busca(ctx["client"], "hosp")["resultados"]) <= 30


def test_x07_csv_de_principais_nunca_e_escrito_pela_inclusao(ctx):
    antes = hashlib.sha256(CAMINHO_BASE.read_bytes()).hexdigest()
    _incluir(ctx["client"], URGIL)
    _incluir(ctx["client"], ADVENTISTA)
    _remover(ctx["client"], URGIL)
    assert hashlib.sha256(CAMINHO_BASE.read_bytes()).hexdigest() == antes


# ------------------------------------------------------------------- Legenda


def test_x10_sem_inclusao_manual_documento_byte_identico_inclusive_legenda(ctx, monkeypatch):
    """A legenda só cresce quando um código cru aparece de fato."""
    rascunho, cen_id, _ = _rascunho_dois_grupos_um_cenario()
    rascunho = rascunho.model_copy(update={"id": EID})
    html_hoje = _html_servico(ctx["tmp"], rascunho, cen_id, "x10a")
    # sem o mecanismo da legenda dinâmica (equivale ao código anterior)
    monkeypatch.setattr(
        "newport_app.presentation.rede_renderer.itens_legenda_extra", lambda doc, legenda=None: []
    )
    html_antes = _html_servico(ctx["tmp"], rascunho, cen_id, "x10b")
    assert html_hoje == html_antes
    assert _legenda(html_hoje) == (
        "<b>H</b> Hospital Geral · <b>HD</b> Hospital Dia · "
        "<b>M</b> Maternidade · <b>PS</b> Pronto-socorro Geral"
    )


def test_x11_legenda_cresce_com_codigo_cru_que_aparece(ctx):
    rascunho, cen_id = _rascunho_com_incluidos(URGIL, OFTALMO)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x11")
    leg = _legenda(html)
    assert leg.startswith("<b>H</b> Hospital Geral")
    assert "<b>HPED</b> Atendimento hospitalar pediátrico" in leg
    assert "<b>PSPED</b> Pronto-socorro pediátrico" in leg
    assert "<b>PSOFT</b> Pronto-socorro oftalmológico" in leg
    assert "HCAR" not in leg  # só o que aparece no documento


def test_x12_codigo_fora_do_csv_aparece_cru_sem_entrada_e_nada_quebra(ctx):
    rascunho, cen_id = _rascunho_com_incluidos(CTO_SAMARITANO)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x12")
    linha = _trecho_linha(_rede(html), _lid(SG_A, CTO_SAMARITANO))
    assert "HCELT" in linha and "HOESP" in linha and "HONC" in linha
    leg = _legenda(html)
    assert "<b>HONC</b> Atendimento hospitalar oncológico" in leg  # no CSV (alta)
    assert "HCELT" not in leg and "HOESP" not in leg  # não estão no CSV


def test_x13_legenda_vem_do_csv_so_confianca_alta_e_arquivo_ausente_nao_quebra(
    ctx, tmp_path, monkeypatch
):
    csv = tmp_path / "legenda.csv"
    csv.write_text(
        "codigo;nome;confianca\nHPED;Pediatria geral (teste);alta\nPSPED;Chute;baixa\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(rede_legenda, "CAMINHO_LEGENDA", csv)
    rede_legenda.limpar_cache_legenda_codigos()
    rascunho, cen_id = _rascunho_com_incluidos(URGIL)
    leg = _legenda(_html_servico(ctx["tmp"], rascunho, cen_id, "x13a"))
    assert "<b>HPED</b> Pediatria geral (teste)" in leg  # o nome vem do CSV, não do código
    assert "PSPED" not in leg  # confiança baixa não é impressa
    monkeypatch.setattr(rede_legenda, "CAMINHO_LEGENDA", tmp_path / "nao-existe.csv")
    rede_legenda.limpar_cache_legenda_codigos()
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x13b")
    assert "HPED" in _trecho_linha(_rede(html), _lid(SG_A, URGIL))  # segue cru
    assert _legenda(html).endswith("Pronto-socorro Geral")
    rede_legenda.limpar_cache_legenda_codigos()


def test_x14_csv_da_legenda_no_repositorio_so_tem_confianca_alta():
    linhas = (ROOT / "docs" / "codigos_rede_legenda.csv").read_text(encoding="utf-8-sig").splitlines()
    assert linhas[0] == "codigo;nome;confianca"
    corpo = [ln.split(";") for ln in linhas[1:] if ln.strip()]
    assert corpo and all(len(c) == 3 and c[2] == "alta" for c in corpo)
    assert len({c[0] for c in corpo}) == len(corpo)


def test_x15_celula_mais_larga_cabe_em_112px_so_cresce_em_altura():
    """Pior caso entre os hospitais sem as quatro: 9 códigos crus, 52 caracteres."""
    from newport_app.presentation.rede_inclusao_manual import texto_codigo_real

    base = carregar_base_rede_hospital()
    from newport_app.presentation.rede_inclusao_manual import prestador_fora_do_criterio

    maior = max(
        (
            texto_codigo_real(v)
            for p in base.prestadores
            if prestador_fora_do_criterio(p)
            for v in p.celulas.values()
        ),
        key=len,
    )
    assert len(maior) == 52 and len(maior.split()) == 9
    # a coluna segue fixa em 112px, na tela e no documento
    css = (ROOT / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    assert "width: 112px;" in css
    from newport_app.presentation import html_renderer

    assert ".tabela-rede .rede-col-plano{width:112px;max-width:112px;min-width:112px;" in Path(
        html_renderer.__file__
    ).read_text(encoding="utf-8")


def test_x16_coberto_so_pelo_contrato_atual_e_aceito_e_aparece_no_documento(ctx):
    """«Você perde esse hospital se trocar»: a linha que só o contrato atual cobre."""
    b = _busca(ctx["client"], "urgil")
    r = _resultado(b, URGIL)
    atuais = {c["chave"] for c in b["colunas"] if c["contrato_atual"]}
    assert r["celulas"] and set(r["celulas"]) <= atuais  # nenhuma proposta cobre
    assert not r["sem_cobertura"]
    ui = _incluir(ctx["client"], URGIL)
    assert _achar(_linhas(ui, SG_A), URGIL) is not None
    rascunho, cen_id = _rascunho_com_incluidos(URGIL)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x16")
    linha = _trecho_linha(_rede(html), _lid(SG_A, URGIL))
    assert "<td class='rede-col-plano on'>HPED PSPED</td>" in linha
    assert linha.count("class='rede-col-plano on'") == 1  # a coluna da proposta fica vazia


def test_x17_hospital_que_nenhum_plano_cobre_entra_e_chega_ao_documento_com_celulas_vazias(ctx):
    """O teste que importa: sem recusa por cobertura, e a linha sobrevive à omissão."""
    b = _busca(ctx["client"], "americas oftalmocenter")
    r = _resultado(b, OFTALMO_TIJUCA)
    assert r["celulas"] == {} and r["sem_cobertura"] is True  # nenhum plano do estudo cobre
    ui = _incluir(ctx["client"], OFTALMO_TIJUCA)  # 200: sem recusa
    for sg in (SG_A, SG_B):
        ln = _achar(_linhas(ui, sg), OFTALMO_TIJUCA)
        assert ln is not None and ln["manual"] is True
        assert not any((v or "").strip() and v != "—" for v in ln["celulas"].values())
    rascunho, cen_id = _rascunho_com_incluidos(OFTALMO_TIJUCA)
    html = _html_servico(ctx["tmp"], rascunho, cen_id, "x17")
    for sg in (SG_A, SG_B):
        linha = _trecho_linha(_rede(html), _lid(sg, OFTALMO_TIJUCA))
        assert "rede-col-plano on" not in linha  # todas as células vazias
        assert "AMERICAS OFTALMOCENTER" in linha.upper()


def test_x18_regra_de_omissao_nao_remove_linha_incluida_a_mao(ctx):
    from newport_app.presentation.rede_apresentacao import linha_tem_cobertura_na_secao

    rascunho, cen_id = _rascunho_com_incluidos(OFTALMO_TIJUCA, ADVENTISTA)
    doc = _doc(rascunho, cen_id)
    for sec in doc.secoes:
        linhas = _linhas_doc(doc, sec.subgrupo_id)
        vazia = next(x for x in linhas if x.prestador == OFTALMO_TIJUCA[0])
        assert vazia.manual and not linha_tem_cobertura_na_secao(vazia, sec.colunas)
        # a regra continua valendo para o que NÃO foi incluído à mão
        for ln in linhas:
            if not ln.manual:
                assert linha_tem_cobertura_na_secao(ln, sec.colunas), ln.prestador
    # sem a inclusão, a linha não aparece (a omissão automática segue de pé)
    rascunho.selecao_rede = None
    doc0 = _doc(rascunho, cen_id)
    assert not any(x.prestador == OFTALMO_TIJUCA[0] for x in _linhas_doc(doc0, SG_A))


def test_x19_presente_na_secao_um_e_ausente_na_dois_entra_so_na_dois(ctx):
    ui0 = _ui(ctx["client"])
    na_a = _achar(_linhas(ui0, SG_A), SAMARITANO)
    assert na_a is not None and na_a["manual"] is False  # principal da seção A
    assert _achar(_linhas(ui0, SG_B), SAMARITANO) is None
    b = _busca(ctx["client"], "samaritano botafogo")
    r = _resultado(b, SAMARITANO)
    assert len(r["secoes_ja_presentes"]) == 1 and len(r["secoes_a_incluir"]) == 1
    assert r["ja_na_tabela"] is False  # falta na B: dá para incluir
    ui = _incluir(ctx["client"], SAMARITANO)
    linhas_a = [x for x in _linhas(ui, SG_A) if (x["prestador"], x["municipio"], x["bairro"]) == SAMARITANO]
    assert len(linhas_a) == 1 and linhas_a[0]["manual"] is False  # sem duplicar na A
    assert linhas_a[0]["linha_id"] == na_a["linha_id"]
    assert _achar(_linhas(ui, SG_B), SAMARITANO)["manual"] is True  # entrou só na B
    # no documento: uma linha na A (principal), uma na B
    rascunho = ctx["repo"].obter_rascunho(EID)
    doc = _doc(rascunho, ctx["cen"])
    assert sum(1 for x in _linhas_doc(doc, SG_A) if (x.prestador, x.chave_municipio, x.bairro) == SAMARITANO) == 1
    assert sum(1 for x in _linhas_doc(doc, SG_B) if (x.prestador, x.chave_municipio, x.bairro) == SAMARITANO) == 1


def test_x20_incluidos_no_rascunho_e_do_estudo_nao_da_secao(ctx):
    inc = IncluidoRedeRascunho(prestador="P", municipio="M", bairro="B")
    assert set(inc.model_dump()) == {"prestador", "municipio", "bairro"}
    assert "subgrupo_id" not in IncluidoRedeRascunho.model_fields
    _incluir(ctx["client"], ADVENTISTA)
    bruto = ctx["repo"].obter_rascunho(EID).model_dump(mode="json")["selecao_rede"]
    assert bruto["incluidos"] == [
        {"prestador": ADVENTISTA[0], "municipio": ADVENTISTA[1], "bairro": ADVENTISTA[2]}
    ]
    # rascunho gravado pelo modelo anterior (com subgrupo_id) ainda carrega, sem duplicar
    antigo = {
        "excluidos": [],
        "revisada": False,
        "incluidos": [
            {"subgrupo_id": SG_A, **{"prestador": ADVENTISTA[0], "municipio": ADVENTISTA[1], "bairro": ADVENTISTA[2]}},
            {"subgrupo_id": SG_B, **{"prestador": ADVENTISTA[0], "municipio": ADVENTISTA[1], "bairro": ADVENTISTA[2]}},
        ],
    }
    sel = SelecaoRedeRascunho.model_validate(antigo)
    rascunho = ctx["repo"].obter_rascunho(EID)
    rascunho.selecao_rede = sel
    base = carregar_base_rede_hospital()
    descartar_incluidos_invalidos(rascunho, base.chaves_prestadores)
    assert len(rascunho.selecao_rede.incluidos) == 1


def test_x21_remover_limpa_as_exclusoes_das_linhas_do_hospital(ctx):
    ui = _incluir(ctx["client"], ADVENTISTA)
    ids = [_achar(_linhas(ui, sg), ADVENTISTA)["linha_id"] for sg in (SG_A, SG_B)]
    r = ctx["client"].put(
        f"/api/estudos/{EID}/rede-selecao", json={"excluidos": ids, "revisada": True}
    )
    assert r.status_code == 200
    _remover(ctx["client"], ADVENTISTA)
    assert ctx["repo"].obter_rascunho(EID).selecao_rede.excluidos == []


