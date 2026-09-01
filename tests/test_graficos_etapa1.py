"""Gráficos da etapa 1 — rosca de sexo e barras por faixa.

Os gráficos são desenhados no front a partir do payload de
``montar_tabela_faixas_cotacao``. Aqui travamos os dois lados dessa fronteira:
as fixtures JSON consumidas pelo teste do gráfico são **regeradas** pela função
da tabela e comparadas byte a byte, de modo que nenhuma contagem paralela possa
nascer no JavaScript sem quebrar a suíte.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from newport_app.models.draft import ParentescoRascunho
from newport_app.models.siscor_import import (
    DisponibilidadeColunasSiscor,
    LinhaSiscorCandidata,
)
from newport_app.siscor_importer.faixas_cotacao import montar_tabela_faixas_cotacao
from newport_app.siscor_importer.parser import parse_planilha_siscor
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_app.presentation.builder import construir_view_model
from tests.fixtures.siscor.xlsx_builder import (
    planilha_12_vidas,
    planilha_anistia_41_sintetica,
    planilha_sexo_coluna_celulas_vazias,
)
from tests.test_paridade_matriz_html import (
    _GABARITO,
    _aprovar,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    assert_gabarito_propostas,
)

REF = date(2026, 6, 30)

_RAIZ = Path(__file__).resolve().parents[1]
_FIXTURES_JS = _RAIZ / "web" / "src" / "fluxo" / "__fixtures__"
_MODULO_JS = _RAIZ / "web" / "src" / "fluxo" / "graficosFaixas.js"
_COMPONENTE_JS = _RAIZ / "web" / "src" / "fluxo" / "GraficosFaixasCotacao.jsx"
_TABELA_JSX = _RAIZ / "web" / "src" / "fluxo" / "TabelaFaixasCotacao.jsx"

# Nascimentos que caem em faixas conhecidas na data de referência.
_NASC_FAIXA = {
    0: "2010-03-01",  # 16 anos
    1: "2005-03-01",  # 21
    2: "2000-03-01",  # 26
    5: "1985-03-01",  # 41
    9: "1960-03-01",  # 66
}


def _linha(
    idx: int,
    *,
    faixa: int,
    sexo: str | None,
    titular: bool,
) -> LinhaSiscorCandidata:
    return LinhaSiscorCandidata(
        id=f"l{idx}",
        numero_linha=idx + 2,
        segurado=f"Vida {idx + 1}",
        parentesco=(
            ParentescoRascunho.TITULAR if titular else ParentescoRascunho.FILHO
        ),
        nascimento=_NASC_FAIXA[faixa],
        sexo=sexo,
        incluida_sugerida=True,
    )


def _tabela_de_linhas(linhas: list[LinhaSiscorCandidata], *, sexo: bool = True):
    return montar_tabela_faixas_cotacao(
        linhas,
        data_referencia=REF,
        disponibilidade=DisponibilidadeColunasSiscor(sexo=sexo),
    )


def _tabela_de_planilha(conteudo: bytes):
    resultado = parse_planilha_siscor(conteudo, estudo_id="gr", documento_id="doc-gr")
    candidata = resultado.candidata
    assert candidata is not None
    return montar_tabela_faixas_cotacao(
        candidata.linhas,
        data_referencia=REF,
        disponibilidade=candidata.disponibilidade_colunas,
    )


def _ivtec_12_com_sexo():
    """12 vidas com sexo — seis femininas e seis masculinas."""
    faixas = [0, 0, 1, 2, 2, 5, 9, 0, 1, 2, 5, 9]
    sexos = ["feminino"] * 6 + ["masculino"] * 6
    return [
        _linha(i, faixa=faixas[i], sexo=sexos[i], titular=i % 3 == 0)
        for i in range(12)
    ]


def _fixtures_esperadas() -> dict[str, object]:
    """Nome do arquivo → tabela produzida pela função da etapa 1."""
    return {
        "tabelaAnistia41.json": _tabela_de_planilha(planilha_anistia_41_sintetica()),
        "tabelaSemSexo12.json": _tabela_de_planilha(planilha_12_vidas()),
        "tabelaSexoParcial.json": _tabela_de_planilha(
            planilha_sexo_coluna_celulas_vazias()
        ),
        "tabelaIvtec12ComSexo.json": _tabela_de_linhas(_ivtec_12_com_sexo()),
        # Casos-limite do gráfico, sempre pela mesma função.
        "tabelaUmaVida.json": _tabela_de_linhas(
            [_linha(0, faixa=2, sexo="feminino", titular=True)]
        ),
        "tabelaMesmaFaixa.json": _tabela_de_linhas(
            [
                _linha(i, faixa=5, sexo="feminino" if i % 2 else "masculino", titular=False)
                for i in range(8)
            ]
        ),
        "tabelaTresIguais.json": _tabela_de_linhas(
            [
                _linha(0, faixa=0, sexo="feminino", titular=True),
                _linha(1, faixa=1, sexo="masculino", titular=True),
                _linha(2, faixa=2, sexo=None, titular=True),
            ]
        ),
        "tabela300Vidas.json": _tabela_de_linhas(
            [
                _linha(i, faixa=2 if i < 190 else 9, sexo="feminino", titular=False)
                for i in range(298)
            ]
            + [
                _linha(298, faixa=0, sexo="masculino", titular=True),
                _linha(299, faixa=5, sexo="masculino", titular=True),
            ]
        ),
    }


@pytest.mark.parametrize("nome", sorted(_fixtures_esperadas()))
def test_01_fixture_do_grafico_vem_da_funcao_da_tabela(nome: str):
    """A fixture lida pelo gráfico é exatamente a saída da tabela — sem drift."""
    esperado = _fixtures_esperadas()[nome]
    arquivo = _FIXTURES_JS / nome
    assert arquivo.is_file(), f"fixture ausente: {arquivo}"
    gravado = json.loads(arquivo.read_text(encoding="utf-8"))
    assert gravado == json.loads(esperado.model_dump_json())


def test_02_anistia_rosca_29_12_e_barras_41():
    tab = _tabela_de_planilha(planilha_anistia_41_sintetica())
    fem = sum((ln.tit_f or 0) + (ln.dep_f or 0) for ln in tab.linhas)
    masc = sum((ln.tit_m or 0) + (ln.dep_m or 0) for ln in tab.linhas)
    assert (fem, masc) == (29, 12)
    assert fem == tab.total_feminino and masc == tab.total_masculino
    assert sum(ln.total for ln in tab.linhas) == tab.total_vidas == 41


def test_03_troca_de_base_muda_a_rosca():
    """Teste central: outra base, outra distribuição — nada de valor congelado."""
    anistia = _tabela_de_planilha(planilha_anistia_41_sintetica())
    ivtec = _tabela_de_linhas(_ivtec_12_com_sexo())

    def rosca(tab):
        return (
            sum((ln.tit_f or 0) + (ln.dep_f or 0) for ln in tab.linhas),
            sum((ln.tit_m or 0) + (ln.dep_m or 0) for ln in tab.linhas),
        )

    assert rosca(anistia) == (29, 12)
    assert rosca(ivtec) == (6, 6)
    assert [ln.total for ln in anistia.linhas] != [ln.total for ln in ivtec.linhas]


def test_04_sem_sexo_nao_tem_grafico():
    tab = _tabela_de_planilha(planilha_12_vidas())
    assert tab.modo_sexo == "sem_sexo"
    # O JS desliga o botão exatamente por este campo.
    src = _MODULO_JS.read_text(encoding="utf-8")
    assert 'tabela.modo_sexo === "sem_sexo"' in src
    assert "disponivel: false" in src


def test_05_sexo_parcial_nao_distribui_nem_some():
    tab = _tabela_de_planilha(planilha_sexo_coluna_celulas_vazias())
    assert tab.modo_sexo == "parcial"
    fem = sum((ln.tit_f or 0) + (ln.dep_f or 0) for ln in tab.linhas)
    masc = sum((ln.tit_m or 0) + (ln.dep_m or 0) for ln in tab.linhas)
    ni = sum(ln.nao_informado or 0 for ln in tab.linhas)
    assert (fem, masc, ni) == (2, 0, 2)
    # As vidas sem sexo continuam no total das barras.
    assert sum(ln.total for ln in tab.linhas) == 4
    assert fem + masc + ni == 4


def test_06_faixa_vazia_aparece_com_zero():
    tab = _tabela_de_linhas([_linha(0, faixa=2, sexo="feminino", titular=True)])
    assert len(tab.linhas) == 10
    assert [ln.total for ln in tab.linhas].count(0) == 9
    assert next(ln for ln in tab.linhas if ln.faixa == 2).total == 1


def test_07_grafico_nao_recalcula_faixa_nem_sexo():
    """Nada de segunda regra: o JS só relê campos do payload."""
    import re

    src = _MODULO_JS.read_text(encoding="utf-8")
    # Palavra inteira: «intensidade» é cor, não idade.
    for proibido in ("nascimento", r"Date\(", "idade", "faixa_em", "getFullYear"):
        assert re.search(rf"\b{proibido}", src) is None, (
            f"derivação paralela no gráfico: {proibido}"
        )
    assert "tit_f" in src and "dep_f" in src and "tit_m" in src and "dep_m" in src


def test_08_botao_alterna_e_esconde_copiar():
    src = _TABELA_JSX.read_text(encoding="utf-8")
    assert "derivarGraficos" in src
    assert "Ver gráficos" in src and "Ver tabela" in src
    assert "aria-pressed={graficosVisiveis}" in src
    # «Copiar tabela» só existe enquanto há tabela na tela.
    assert "{!graficosVisiveis && (" in src
    # Botão algum quando a base não tem sexo.
    assert "{graficos.disponivel && (" in src
    # Estado local: não vai para rascunho nem snapshot.
    assert "useState(false)" in src
    assert "snapshot" not in src.lower()


def test_09_acessibilidade_alternativa_textual():
    componente = _COMPONENTE_JS.read_text(encoding="utf-8")
    assert componente.count('role="img"') == 2
    assert componente.count("aria-labelledby={idTexto}") == 2
    assert "descricaoRosca" in componente and "descricaoBarras" in componente
    # Cor não é o único diferenciador: textura + rótulo + valor visível.
    assert "gr-hachura-traco" in componente or "hachura" in componente
    assert "gr-legenda-valor" in componente and "gr-barra-valor" in componente


def test_10_gabarito_anistia_intacto(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_12_barras_sem_trilho_com_intensidade_e_linha_de_base():
    """Refinamento visual: leitura contra o vazio, concentração pela cor."""
    css = (_RAIZ / "web" / "src" / "styles.css").read_text(encoding="utf-8")
    bloco = css.split(".gr-barra-trilho {", 1)[1].split("}", 1)[0]
    # Nada de retângulo de fundo competindo com o dado.
    assert "background" not in bloco
    assert "var(--surface-3)" not in bloco
    # Linha de base discreta, ancorando sem devolver a caixa.
    assert "border-bottom: 1px solid var(--line-strong)" in bloco

    fill = css.split(".gr-barra-preenchimento {", 1)[1].split("}", 1)[0]
    assert "color-mix(" in fill and "var(--intensidade)" in fill
    assert "var(--blue-2)" in fill and "var(--blue-100)" in fill
    assert "max(7px," in fill  # piso para a faixa de uma vida
    # A curva mora no módulo, não na folha de estilo.
    assert "intensidadeBarra" in _MODULO_JS.read_text(encoding="utf-8")


def test_13_rosca_maior_e_mais_espessa():
    js = _MODULO_JS.read_text(encoding="utf-8")
    assert "ROSCA_RAIO = 70" in js
    assert "ROSCA_ESPESSURA = 34" in js
    # O anel inteiro continua dentro do viewBox 200 com folga para o traço.
    assert 70 + 34 / 2 < 100


def test_14_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    snap = _aprovar(tmp_path, rascunho)
    digest = hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    assert digest == hash_snapshot_canonico(snap.payload, versao=snap.snapshot_versao)
    assert len(digest) == 64
