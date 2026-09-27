"""Fase A — tabela de equivalência plano × coluna de rede."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from newport_app.models.snapshot import GerarApresentacaoRequest
from newport_app.policy.registry import default_registry
from newport_app.presentation.builder import construir_view_model
from newport_app.presentation.planos_rede import (
    CAMINHO_ALIASES,
    BasePlanosRedeInvalida,
    EstadoCasamentoRede,
    carregar_aliases_rede,
    carregar_colunas_rede_xlsx,
    caminho_base_rede_padrao,
    colunas_por_sufixo,
    reconhecer_operadora_rede,
    resolver_casamento_rede,
)
from newport_app.presentation.regras_comerciais import carregar_aliases
from newport_app.services.comparativo_confirmacao import montar_payload_nucleo_congelamento
from newport_app.snapshot.hashing import hash_snapshot_canonico
from newport_app.siscor_importer.normalize import normalizar_cabecalho
from tests.test_correcao_resumo_regime import _aprovar as _aprovar_anistia
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_fase2_tarefa2 import _aprovar as _aprovar_stack
from tests.test_fase2_tarefa2 import _stack
from tests.test_paridade_matriz_html import (
    _GABARITO,
    assert_gabarito_propostas,
    _calcular_matriz,
    _rascunho_dois_planos_gabarito,
    _aprovar as _aprovar_gabarito,
)
from tests.test_regras_comerciais import _html_de

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / ".data" / "newport_app.db"

WESLEY_17: list[tuple[str, str, str]] = [
    ("Amil", "AMIL ONE S2500 - Apto.", "AMIL - LINHA BLACK S2500"),
    ("Amil", "BRONZE SP MAIS COPART TP", "AMIL - BRONZE BRONZE - SP+"),
    ("Amil", "AMIL BLACK I R1 COPART", "AMIL - LINHA BLACK BLACK I"),
    ("Amil", "AMIL S750 R1 QP NAC COPART PJ", "AMIL - LINHA SELECIONADA S750 - APTO"),
    ("Amil", "OURO QP R COPART", "AMIL - PRATA AO PLATINUM OURO - QP"),
    ("Amil", "PLATINUM R1 COPART", "AMIL - PRATA AO PLATINUM PLATINUM"),
    ("Porto Seguro", "DIAMANTE PRO Q", "PORTO SEGURO - PORTO PRO DIAMANTE PRO SP - APTO"),
    ("Porto Seguro", "DIAMANTE PRO COPAR Q", "PORTO SEGURO - PORTO PRO DIAMANTE PRO SP - APTO"),
    ("Porto Seguro", "PRATA PRO COPAR Q", "PORTO SEGURO - PORTO PRO PRATA PRO SP - APTO"),
    ("SulAmérica", "Especial 100 R1", "SUL AMÉRICA - EXATO AO PRESTIGE ESPECIAL 100-APTO"),
    (
        "SulAmérica",
        "Direto Apartamento (Nacional)",
        "SUL AMÉRICA - DIRETO NACIONAL DIRETO NACIONAL - APTO",
    ),
    ("SulAmérica", "Especial Vital RC", "SUL AMÉRICA - EXATO AO PRESTIGE ESPECIAL VITAL-APTO"),
    (
        "SulAmérica",
        "Especial Mais Vital",
        "SUL AMÉRICA - EXATO AO PRESTIGE ESPECIAL MAIS VITAL-APTO",
    ),
    ("SulAmérica", "Executivo R2", "SUL AMÉRICA - EXATO AO PRESTIGE EXECUTIVO-APTO"),
    (
        "SulAmérica",
        "Executivo R1 Apartamento Nacional",
        "SUL AMÉRICA - EXATO AO PRESTIGE EXECUTIVO-APTO",
    ),
    (
        "SulAmérica",
        "Especial 100 R1 Vital",
        "SUL AMÉRICA - EXATO AO PRESTIGE ESPECIAL VITAL-APTO",
    ),
    ("SulAmérica", "Especial 100 RC", "SUL AMÉRICA - EXATO AO PRESTIGE ESPECIAL 100-APTO"),
]

DEMO_OPS = frozenset(
    {
        "OPERADORA DEMO",
        "OPERADORA P",
        "OPERADORA A",
        "OPERADORA B",
        "SEM PLANO ATUAL",
    }
)


@pytest.fixture(scope="module")
def xlsx_rede() -> Path:
    caminho = caminho_base_rede_padrao()
    if caminho is None:
        pytest.skip("base SiscorNet ausente (defina NEWPORT_REDE_XLSX)")
    return caminho


@pytest.fixture(scope="module")
def colunas_rede(xlsx_rede: Path):
    aliases = carregar_aliases()
    return carregar_colunas_rede_xlsx(xlsx_rede, aliases)


@pytest.fixture(scope="module")
def tabela_rede(colunas_rede):
    return carregar_aliases_rede(colunas_rede=colunas_rede)


def test_csv_versionado_valida_contra_base(colunas_rede):
    tab = carregar_aliases_rede(colunas_rede=colunas_rede)
    assert len(tab.entradas) == 17


@pytest.mark.parametrize("op,plano,rotulo", WESLEY_17)
def test_dezessete_aliases_wesley(op, plano, rotulo, colunas_rede, tabela_rede):
    r = resolver_casamento_rede(
        op,
        plano,
        colunas_rede,
        tabela=tabela_rede,
    )
    assert r.estado == EstadoCasamentoRede.ALIAS
    assert r.rotulo_coluna == rotulo


def test_ouro_qp_prefixo_abreviado(colunas_rede, tabela_rede):
    r = resolver_casamento_rede(
        "Amil",
        "OURO QP R COPART",
        colunas_rede,
        tabela=tabela_rede,
    )
    assert r.rotulo_coluna == "AMIL - PRATA AO PLATINUM OURO - QP"
    hits = colunas_por_sufixo("Amil", "OURO - QP", colunas_rede)
    assert len(hits) == 1


def test_platinum_r1(colunas_rede, tabela_rede):
    r = resolver_casamento_rede(
        "Amil",
        "PLATINUM R1 COPART",
        colunas_rede,
        tabela=tabela_rede,
    )
    assert r.rotulo_coluna == "AMIL - PRATA AO PLATINUM PLATINUM"


def test_regra_automatica_marca_regra_nao_alias(colunas_rede, tabela_rede):
    r = resolver_casamento_rede(
        "Porto Seguro",
        "BRONZE RIO PRO COPAR Q 30",
        colunas_rede,
        tabela=tabela_rede,
    )
    assert r.estado == EstadoCasamentoRede.REGRA
    assert r.rotulo_coluna is not None


def _planos_estudo_reais() -> list[tuple[str, str]]:
    if not DB.is_file():
        pytest.skip("banco demo ausente")
    aliases = carregar_aliases()
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT payload FROM rascunhos").fetchall()
    conn.close()
    vistos: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for (payload,) in rows:
        d = json.loads(payload)
        for lista in (d.get("opcoes_proposta") or [], d.get("subgrupos_atuais") or []):
            for it in lista:
                op = (it.get("operadora") or "").strip()
                pl = (it.get("plano_nome") or "").strip()
                if not pl:
                    continue
                if normalizar_cabecalho(op) in DEMO_OPS:
                    continue
                pn = normalizar_cabecalho(pl)
                if "FICTIC" in pn:
                    continue
                if pl in ("SEGURO NOVO", "Plano vigente A", "Plano vigente B"):
                    continue
                if not reconhecer_operadora_rede(op, aliases):
                    continue
                ch = (op, pl)
                if ch in vistos:
                    continue
                vistos.add(ch)
                out.append(ch)
    return out


def test_censo_55_casam(colunas_rede, tabela_rede):
    planos = _planos_estudo_reais()
    assert len(planos) == 55
    alias = regra = sem = 0
    amb: list[str] = []
    for op, pl in planos:
        r = resolver_casamento_rede(op, pl, colunas_rede, tabela=tabela_rede)
        if r.estado == EstadoCasamentoRede.ALIAS:
            alias += 1
        elif r.estado == EstadoCasamentoRede.REGRA:
            regra += 1
        else:
            sem += 1
            amb.append(f"{op} | {pl}")
    assert sem == 0, amb
    assert alias + regra == 55
    assert alias == 17
    assert regra == 38


def test_plano_desconhecido_sem_rede(colunas_rede, tabela_rede):
    r = resolver_casamento_rede(
        "Amil",
        "PRODUTO INEXISTENTE XYZ 999",
        colunas_rede,
        tabela=tabela_rede,
    )
    assert r.estado == EstadoCasamentoRede.SEM_REDE
    assert r.rotulo_coluna is None


def test_csv_operadora_invalida(tmp_path, colunas_rede):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "operadora;plano_cotacao;coluna_rede;fonte;atualizado_em\n"
        "OperadoraFake;X;Y;f;d\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(BasePlanosRedeInvalida, match="registro 2"):
        carregar_aliases_rede(bad, colunas_rede=colunas_rede)


def test_csv_coluna_inexistente(tmp_path, colunas_rede):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "operadora;plano_cotacao;coluna_rede;fonte;atualizado_em\n"
        "Amil;TESTE;COLUNA QUE NAO EXISTE;f;d\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(BasePlanosRedeInvalida, match="registro 2"):
        carregar_aliases_rede(bad, colunas_rede=colunas_rede)


def test_csv_duplicata(tmp_path, colunas_rede):
    bad = tmp_path / "bad.csv"
    bad.write_text(
        "operadora;plano_cotacao;coluna_rede;fonte;atualizado_em\n"
        "Amil;OURO QP R COPART;OURO - QP;f;d\n"
        "Amil;OURO QP R COPART;OURO - QP;f;d\n",
        encoding="utf-8-sig",
    )
    with pytest.raises(BasePlanosRedeInvalida, match="duplicata"):
        carregar_aliases_rede(bad, colunas_rede=colunas_rede)


def test_tres_estados_distintos(colunas_rede, tabela_rede):
    a = resolver_casamento_rede("Amil", "OURO QP R COPART", colunas_rede, tabela=tabela_rede)
    b = resolver_casamento_rede(
        "Porto Seguro", "BRONZE RIO PRO COPAR Q 30", colunas_rede, tabela=tabela_rede
    )
    c = resolver_casamento_rede("Amil", "INEXISTENTE", colunas_rede, tabela=tabela_rede)
    assert a.estado == EstadoCasamentoRede.ALIAS
    assert b.estado == EstadoCasamentoRede.REGRA
    assert c.estado == EstadoCasamentoRede.SEM_REDE


def test_gabaritos_paridade(tmp_path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    matriz, _ = _calcular_matriz(rascunho)
    snap = _aprovar_gabarito(tmp_path, rascunho)
    vm = construir_view_model(
        snap, modo="resumo", propostas_selecionadas=["op-prata", "op-ouro"]
    )
    gab = json.loads(_GABARITO.read_text(encoding="utf-8"))
    assert_gabarito_propostas(matriz, vm, gab)
    assert vm.totais_gerais.atual_centavos == 4_847_931


def test_rascunhos_compilam(tmp_path):
    snap = _aprovar_anistia(tmp_path, _rascunho_anistia_seis())
    ids = [op.id for op in _rascunho_anistia_seis().opcoes_proposta]
    vm = construir_view_model(snap, modo="resumo", propostas_selecionadas=ids)
    assert vm is not None
    assert len(vm.secoes_regime) >= 1


def test_hash_snapshot_inalterado(tmp_path):
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    _, nucleo_antes, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    h_antes = hash_snapshot_canonico(nucleo_antes)
    repo, _, snap_svc, _ = _stack(tmp_path, "hash-planos-rede")
    snap = _aprovar_stack(repo, snap_svc, rascunho)
    assert snap.hash_sha256 == h_antes
    _, nucleo_depois, _ = montar_payload_nucleo_congelamento(rascunho, default_registry)
    assert hash_snapshot_canonico(nucleo_depois) == h_antes


def test_html_export_identico(tmp_path):
    html, _ = _html_de(tmp_path, _rascunho_anistia_seis())
    assert "48.479,31" in html
    assert CAMINHO_ALIASES.is_file()
