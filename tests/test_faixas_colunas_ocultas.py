"""Colunas Tit. e Dep. sob demanda na visão de faixas do HTML exportado.

O documento continua sem script: um checkbox + label e seletores irmãos
escondem ou revelam as colunas em todas as tabelas da seção ao mesmo tempo.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.html_renderer import (
    RENDERER_VERSAO,
    render_html,
    render_html_completo,
)
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from tests.test_apresentacao_seguro_novo import _aprovar as _aprovar_ivtec
from tests.test_apresentacao_seguro_novo import _rascunho_ivtec_novo
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
_CMP = (
    Path(__file__).resolve().parents[1]
    / "web"
    / "src"
    / "comparativo"
    / "ComparativoExperiencia.jsx"
)


def _html_completo_anistia(tmp_path: Path) -> tuple[str, object]:
    rascunho = _rascunho_anistia_seis()
    snap = _aprovar_anistia(tmp_path, rascunho)
    spec = json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "paridade_matriz"
            / "anistia_seis_propostas.json"
        ).read_text(encoding="utf-8")
    )
    ids = [p["id"] for p in spec["propostas"]]
    vm_r = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    vm_f = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    vm_g = construir_view_model(
        snap,
        modo="grupo_familiar",
        propostas_selecionadas=ids,
        beneficiarios_agregados=False,
    )
    return render_html_completo(vm_r, vm_f, vm_g), snap


def _tabelas_faixas(html: str) -> list[str]:
    return re.findall(
        r"<table class='tabela-faixas[^']*'>(.*?)</table>", html, flags=re.S
    )


def test_01_anistia_abre_com_colunas_ocultas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "id=\"col-titdep\"" in html
    assert "checked" not in html.split('id="col-titdep"')[1][:80]
    assert ".tabela-faixas th.col-titdep,.tabela-faixas td.col-titdep" in html
    tabelas = _tabelas_faixas(html)
    assert len(tabelas) >= 2
    for tab in tabelas:
        assert "Tit." in tab and "Dep." in tab
        assert "class='col-titdep'" in tab


def test_02_um_controle_abre_todas_as_tabelas(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert html.count('id="col-titdep"') == 1
    assert html.count('for="col-titdep"') == 1
    # Um seletor irmão alcança qualquer tabela subsequente — não um por plano.
    assert "#col-titdep:checked ~ * .tabela-faixas th.col-titdep" in html
    assert "#col-titdep:checked ~ * .tabela-faixas td.col-titdep" in html
    assert len(_tabelas_faixas(html)) >= 2


def test_03_segundo_clique_volta_a_ocultar(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert '<input type="checkbox" id="col-titdep"' in html
    # Sem checked inicial: desmarcar o checkbox é o estado padrão. O rótulo
    # muda nos dois sentidos só com :checked.
    assert "ctrl-titdep-abrir" in html and "ctrl-titdep-fechar" in html
    assert "#col-titdep:checked ~ .ctrl-titdep .ctrl-titdep-abrir{display:none}" in html
    assert "#col-titdep:checked ~ .ctrl-titdep .ctrl-titdep-fechar{display:inline}" in html


def test_04_zero_javascript(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert _SCRIPT.search(html) is None
    assert "<script" not in html.lower()
    # Prova de que a troca não depende de script: só input + seletor irmão.
    assert 'type="checkbox" id="col-titdep"' in html
    assert "#col-titdep:checked ~ * .tabela-faixas" in html


def test_05_totais_identicos_nos_dois_estados(tmp_path: Path):
    html, snap = _html_completo_anistia(tmp_path)
    spec = json.loads(
        (
            Path(__file__).resolve().parent
            / "fixtures"
            / "paridade_matriz"
            / "anistia_seis_propostas.json"
        ).read_text(encoding="utf-8")
    )
    ids = [p["id"] for p in spec["propostas"]]
    vm = construir_view_model(snap, modo="faixas", propostas_selecionadas=ids)
    planos = [pl for s in vm.secoes_regime for pl in s.planos_atuais]
    s750 = next(p for p in planos if "750" in p.plano_nome)
    one = next(p for p in planos if "2500" in p.plano_nome)
    assert s750.subtotal_vigente_centavos == 2_623_822
    assert s750.subtotal_reajustado_centavos == 2_938_676
    assert one.subtotal_vigente_centavos == 1_704_692
    assert one.subtotal_reajustado_centavos == 1_909_255
    # A visão exportada mostra o reajustado; o vigente está no ViewModel.
    # Abrir as colunas não duplica nem altera — o HTML é um só documento.
    assert html.count("29.386,76") >= 1
    assert html.count("19.092,55") >= 1
    assert "29.386,76" in html and "19.092,55" in html


def test_06_matriz_etapa5_intacta():
    src = _CMP.read_text(encoding="utf-8")
    assert "col-titdep" not in src
    assert "Ver titulares e dependentes" not in src
    assert "Ocultar titulares e dependentes" not in src
    assert "function TabelaFaixasPlano" in src


def test_07_modo_completo_controle_presente(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'id="tab-todas"' in html
    assert 'id="col-titdep"' in html
    # O checkbox vive dentro da visão de faixas, então sobrevive a «três visões».
    trecho = html.split('id="visao-faixas"')[1].split('id="visao-benef"')[0]
    assert 'id="col-titdep"' in trecho
    assert "Ver titulares e dependentes" in trecho


def test_08_impressao_respeita_estado_e_esconde_controle(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert "@media print" in html
    compacto = html.replace(" ", "")
    assert ".ctrl-titdep" in compacto and "display:none!important" in compacto
    # Nenhuma regra de impressão força as colunas a aparecer ou sumir — o
    # :checked do checkbox continua valendo no papel.
    bloco_print = html.split("@media print")[1].split("}", 8)[0]
    assert "col-titdep" not in bloco_print


def test_09_ivtec_seguro_novo_oito_titulares_quatro_dependentes(tmp_path: Path):
    snap = _aprovar_ivtec(tmp_path, _rascunho_ivtec_novo())
    vm = construir_view_model(
        snap, modo="faixas", propostas_selecionadas=["op-bronze", "op-prata"]
    )
    html = render_html(vm)
    assert 'id="col-titdep"' in html
    assert "Ver titulares e dependentes" in html
    plano = vm.secoes_regime[0].planos_atuais[0]
    tit = sum(fx.qtd_titulares for fx in plano.faixas)
    dep = sum(fx.qtd_dependentes for fx in plano.faixas)
    vidas = sum(fx.qtd_total for fx in plano.faixas)
    assert (tit, dep, vidas) == (8, 4, 12)
    # As mesmas quantidades estão nas células do HTML.
    tab = _tabelas_faixas(html)[0]
    tits = [
        int(n)
        for n in re.findall(r"<td class='col-titdep'>(\d+)</td>", tab)
    ]
    # Pares Tit., Dep. por linha.
    assert sum(tits[0::2]) == 8
    assert sum(tits[1::2]) == 4


def test_10_gabarito_anistia_intacto(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_gabarito(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)


def test_11_hash_snapshot_inalterado(tmp_path: Path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, apres = _stack(tmp_path, "hash-titdep")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    apres.gerar_html(
        rascunho.id,
        snap.id,
        GerarApresentacaoRequest(
            modo="completo", propostas_selecionadas=["op-1", "op-2"]
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


def test_13_acessibilidade_do_controle(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    assert 'for="col-titdep"' in html
    assert 'aria-describedby="hint-titdep"' in html
    assert 'id="hint-titdep"' in html
    assert "#col-titdep:focus-visible ~ .ctrl-titdep" in html
    assert "Ver titulares e dependentes" in html
    assert "Ocultar titulares e dependentes" in html
    # Checkbox nativo anuncia o estado; o rótulo visível muda com :checked.
    assert 'type="checkbox"' in html


def test_14_tabela_com_respiro_e_rolagem_horizontal(tmp_path: Path):
    html, _ = _html_completo_anistia(tmp_path)
    # Primeira coluna não pode colar na borda — padding mínimo em todas as células.
    assert "padding-left:0" not in html
    # Com Tit./Dep. abertos a tabela cresce; o rolo rola em vez de cortar a última coluna.
    assert ".rolo table{width:max-content;min-width:100%}" in html
    assert "overflow-x:auto" in html.split(".rolo{")[1].split("}")[0]


def test_renderer_sem_script_e_versao():
    assert RENDERER_VERSAO.startswith("html@2.13")
