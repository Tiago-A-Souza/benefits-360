"""Quarta aba — regras contratuais no HTML exportado (CSS puro)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html_completo,
)
from newport_app.presentation.regras_comerciais import (
    CAMINHO_ALIASES,
    CAMINHO_BASE,
    MAX_OPERADORAS_POR_PAGINA,
    OPERADORAS_CANONICAS,
    REGRAS_ORDEM,
    BaseRegrasComerciaisInvalida,
    carregar_aliases,
    carregar_base,
    montar_tabela,
    reconhecer_operadora,
)
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.siscor_importer.normalize import normalizar_cabecalho
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar as _aprovar_gabarito,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

_SCRIPT = re.compile(r"<script\b", re.IGNORECASE)
_WEB = Path(__file__).resolve().parents[1] / "web" / "src"
_FIXTURE_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)


def _ids_anistia() -> list[str]:
    spec = json.loads(_FIXTURE_SEIS.read_text(encoding="utf-8"))
    return [p["id"] for p in spec["propostas"]]


def _com_operadoras(rascunho, nomes: list[str]):
    r = rascunho.model_copy(deep=True)
    novas = []
    for i, op in enumerate(r.opcoes_proposta):
        nome = nomes[i] if i < len(nomes) else nomes[-1]
        novas.append(op.model_copy(update={"operadora": nome}))
    return r.model_copy(update={"opcoes_proposta": novas})


def _html_de(tmp_path: Path, rascunho, ids: list[str] | None = None) -> tuple[str, object]:
    snap = _aprovar_anistia(tmp_path, rascunho)
    if ids is None:
        ids = [op.id for op in rascunho.opcoes_proposta]
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=ids,
        beneficiarios_agregados=True,
    )
    return render_html_completo(vm_r, vm_f, vm_g), snap


def _texto_celula(html_cel: str) -> str:
    texto = re.sub(r"<br\s*/?>", "\n", html_cel, flags=re.I)
    texto = re.sub(r"<[^>]+>", "", texto)
    return texto.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _tabelas_regras(html: str) -> list[list[list[str]]]:
    saida: list[list[list[str]]] = []
    for bloco in re.findall(
        r"<table class='tabela-regras'>(.*?)</table>", html, flags=re.S
    ):
        linhas: list[list[str]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", bloco, flags=re.S):
            cells = [_texto_celula(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, flags=re.S)]
            linhas.append(cells)
        saida.append(linhas)
    return saida


def test_01_amil_bradesco_sulamerica_tres_colunas_oito_regras(tmp_path: Path):
    r = _rascunho_anistia_seis()
    r = _com_operadoras(
        r,
        ["Amil", "Amil", "Bradesco", "Bradesco", "SulAmérica", "SulAmérica"],
    )
    html, _ = _html_de(tmp_path, r)
    tabelas = _tabelas_regras(html)
    assert len(tabelas) == 1
    cab = tabelas[0][0]
    assert cab == ["Regra", "Amil", "Bradesco", "SulAmérica"]
    regras = [lin[0] for lin in tabelas[0][1:]]
    assert regras == list(REGRAS_ORDEM)


def test_02_valores_conferem_celula_a_celula_incluindo_quebras(tmp_path: Path):
    r = _rascunho_anistia_seis()
    r = _com_operadoras(
        r,
        ["Amil", "Amil", "Bradesco", "Bradesco", "SulAmérica", "SulAmérica"],
    )
    html, _ = _html_de(tmp_path, r)
    base = carregar_base()
    cab = _tabelas_regras(html)[0][0]
    for lin in _tabelas_regras(html)[0][1:]:
        regra = lin[0]
        for col, op in enumerate(cab[1:], start=1):
            assert lin[col] == base[(op, regra)]


def test_03_informacao_pendente_aparece_como_esta():
    base = carregar_base()
    pendentes = [(op, rg, v) for (op, rg), v in base.items() if v == "Informação pendente"]
    assert pendentes, "a base deve ter células Informação pendente"
    tabela = montar_tabela([op for op, _, _ in pendentes])
    assert tabela is not None
    for op, rg, v in pendentes:
        assert tabela.valor(op, rg) == "Informação pendente"
    r = _rascunho_anistia_seis()
    r = _com_operadoras(r, ["Alice"] * len(r.opcoes_proposta))
    # HTML gerado no teste seguinte dedicado — aqui a base e a tabela.


def test_03b_informacao_pendente_no_html(tmp_path: Path):
    r = _com_operadoras(_rascunho_anistia_seis(), ["Alice"] * 6)
    html, _ = _html_de(tmp_path, r)
    assert "Informação pendente" in html
    assert html.count("Informação pendente") == 2


def test_04_operadora_fora_da_base_nao_vira_coluna(tmp_path: Path):
    r = _com_operadoras(
        _rascunho_anistia_seis(),
        ["Amil", "Amil", "Qualicorp", "Qualicorp", "SulAmérica", "SulAmérica"],
    )
    html, _ = _html_de(tmp_path, r)
    cab = _tabelas_regras(html)[0][0]
    assert cab == ["Regra", "Amil", "SulAmérica"]
    assert "Qualicorp" not in html.split("id=\"visao-regras\"")[1][:4000]


def test_05_nenhuma_operadora_reconhecida_aba_nao_existe(tmp_path: Path):
    r = _com_operadoras(_rascunho_anistia_seis(), ["Unimed Campinas"] * 6)
    html, _ = _html_de(tmp_path, r)
    assert 'id="visao-regras"' not in html
    assert 'id="tab-regras"' not in html
    assert "Regras contratuais" not in html
    assert 'id="visao-resumo"' in html
    assert 'id="visao-faixas"' in html
    assert 'id="visao-benef"' in html
    assert html.count('name="doc-visao"') == 4  # três visões + todas


def test_06_unimed_regional_nao_casa_com_seguros_unimed(tmp_path: Path):
    assert reconhecer_operadora("Unimed Campinas") is None
    assert reconhecer_operadora("Unimed Paulistana") is None
    assert reconhecer_operadora("Central Nacional Unimed") is None
    assert reconhecer_operadora("Unimed Nacional") is None
    assert reconhecer_operadora("Unimed do Brasil") is None
    assert reconhecer_operadora("Seguros Unimed") == "Seguros Unimed"
    r = _com_operadoras(_rascunho_anistia_seis(), ["Unimed Campinas"] * 6)
    html, _ = _html_de(tmp_path, r)
    assert "Seguros Unimed" not in html
    assert "De 10 à 63 anos" not in html
    src = Path(__file__).resolve().parents[1] / "src" / "newport_app" / "presentation" / "regras_comerciais.py"
    texto = src.read_text(encoding="utf-8")
    assert " in " not in texto.split("def reconhecer_operadora")[1].split("def operadoras")[0]


def test_07_variacoes_de_nome_casam():
    mapa = carregar_aliases()
    assert reconhecer_operadora("Sul América", mapa) == "SulAmérica"
    assert reconhecer_operadora("SulAmérica", mapa) == "SulAmérica"
    assert reconhecer_operadora("Porto Saúde", mapa) == "Porto Seguro"
    assert reconhecer_operadora("GNDI", mapa) == "NotreDame"
    assert reconhecer_operadora("Sul\u00a0América", mapa) == "SulAmérica"
    assert reconhecer_operadora("porto saude", mapa) == "Porto Seguro"


def test_07b_variacoes_viram_coluna(tmp_path: Path):
    r = _com_operadoras(
        _rascunho_anistia_seis(),
        ["Sul América", "Porto Saúde", "GNDI", "GNDI", "Sul América", "Porto Saúde"],
    )
    html, _ = _html_de(tmp_path, r)
    cab = _tabelas_regras(html)[0][0]
    assert cab == ["Regra", "SulAmérica", "Porto Seguro", "NotreDame"]


def test_08_hapvida_e_notredame_duas_colunas_mesmos_valores(tmp_path: Path):
    r = _com_operadoras(
        _rascunho_anistia_seis(),
        ["Hapvida", "NotreDame", "Hapvida", "NotreDame", "Hapvida", "NotreDame"],
    )
    html, _ = _html_de(tmp_path, r)
    cab = _tabelas_regras(html)[0][0]
    assert cab == ["Regra", "Hapvida", "NotreDame"]
    for lin in _tabelas_regras(html)[0][1:]:
        assert lin[1] == lin[2]


def test_09_base_malformada_informa_o_registro(tmp_path: Path):
    ruim = tmp_path / "base.csv"
    ruim.write_text(
        "operadora;regra;valor\n"
        "Amil;Redução de Carências;ok\n"
        "Operadora Inventada;Adesão;x\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseRegrasComerciaisInvalida, match=r"registro 3") as exc:
        carregar_base(ruim)
    assert "Operadora Inventada" in str(exc.value)

    dup = tmp_path / "dup.csv"
    dup.write_text(
        "operadora;regra;valor\n"
        "Amil;Redução de Carências;a\n"
        "Amil;Redução de Carências;b\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseRegrasComerciaisInvalida, match=r"registro 3.*duplicata"):
        carregar_base(dup)

    alias_ruim = tmp_path / "aliases.csv"
    alias_ruim.write_text(
        "canonica;variacao\n"
        "Operadora Inventada;Foo\n",
        encoding="utf-8",
    )
    with pytest.raises(BaseRegrasComerciaisInvalida, match=r"registro 2"):
        carregar_aliases(alias_ruim)


def test_09b_base_oficial_esta_inteira():
    celulas = carregar_base()
    assert len(celulas) == 80
    assert set(op for op, _ in celulas) == set(OPERADORAS_CANONICAS)
    carregar_aliases()
    assert CAMINHO_BASE.is_file()
    assert CAMINHO_ALIASES.is_file()


def test_10_zero_script_no_documento(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert _SCRIPT.search(html) is None
    assert RENDERER_VERSAO == "html@2.12.1"
    assert "Ver todas as visões" in html


def test_11_nada_na_interface_do_sistema():
    proibidos = (
        "Regras contratuais",
        "regras_comerciais",
        "tab-regras",
        "visao-regras",
    )
    for path in _WEB.rglob("*"):
        if path.suffix not in {".js", ".jsx", ".css", ".html"}:
            continue
        texto = path.read_text(encoding="utf-8")
        for termo in proibidos:
            assert termo not in texto, f"{path}: vazou {termo!r}"


def test_12_gabarito_anistia_intacto(tmp_path: Path):
    r10 = _rascunho_dois_planos_gabarito(reajuste_bps=1000)
    m10, _ = _calcular_matriz(r10)
    snap10 = _aprovar_gabarito(tmp_path, r10)
    vm10 = construir_view_model(
        snap10, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(m10, vm10, gab)
    assert gab["reajuste"]["1000"]["consolidado_centavos"] == 4_761_362
    assert gab["reajuste"]["1200"]["consolidado_centavos"] == 4_847_931
    assert vm10.totais_gerais.atual_centavos == 4_761_362
    prata = next(p for p in gab["propostas"] if p["chave"] == "prata")
    assert prata["plano_a_centavos"] == 2_360_717
    assert prata["plano_b_centavos"] == 610_061

    r12 = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    m12, _ = _calcular_matriz(r12)
    snap12 = _aprovar_gabarito(tmp_path, r12)
    vm12 = construir_view_model(
        snap12, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    assert_gabarito_propostas(m12, vm12, gab)
    assert vm12.totais_gerais.atual_centavos == 4_847_931


def test_13_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-regras")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="completo", propostas_selecionadas=["op-prata", "op-ouro"]
        ),
    )
    snap_depois = snap_svc.obter_snapshot(snap.id)
    assert snap_depois.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_depois = hash_snapshot_canonico(nucleo_depois)
    assert h_antes == h_depois
    assert len(h_antes) == 64
    print(f"HASH_ANTES={h_antes}")
    print(f"HASH_DEPOIS={h_depois}")


def test_15_impressao_aba_visivel_sem_cortar(tmp_path: Path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "#tab-regras:checked ~ .doc-corpo .visao-regras" in html
    assert ".tabela-regras{page-break-inside:avoid}" in html
    assert MAX_OPERADORAS_POR_PAGINA == 3
    assert "white-space:normal" in html
    assert "@media print" in html
    # Impressão esconde controles; a aba checked continua display:block.
    css_print = html.split("@media print{")[1].split("}", 1)[0]
    assert "visao-regras" not in css_print or "display:none" not in css_print


def test_normalizacao_reutilizada():
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "newport_app"
        / "presentation"
        / "regras_comerciais.py"
    ).read_text(encoding="utf-8")
    assert "from newport_app.siscor_importer.normalize import normalizar_cabecalho" in src
    assert "normalizar_cabecalho(variacao)" in src
    assert "normalizar_cabecalho(nome)" in src
    assert normalizar_cabecalho("Sul\u00a0América") == "SUL AMERICA"
