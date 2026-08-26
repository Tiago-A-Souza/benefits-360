"""Parte 1 — grade completa (opção usada × subgrupo com vidas) no motor."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path

from newport_app.draft_compiler import compile
from newport_app.models.draft import (
    AtribuicaoRascunho,
    CenarioRascunho,
)
from newport_app.policy.registry import default_registry
from newport_app.rascunho.cenarios_sync import sincronizar_cenarios
from newport_app.seed.ficticio import rascunho_demo_12_vidas
from newport_motor.engine import calcular
from newport_motor.result import MotorResult
from tests.test_cenarios_contrato_motor import _rascunho_seguro_novo
from tests.test_correcao_resumo_regime import _rascunho_anistia_seis
from tests.test_paridade_matriz_html import _rascunho_dois_planos_gabarito

_GABARITO_DOIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "gabarito_dois_planos.json"
)
_ANISTIA_SEIS = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "paridade_matriz"
    / "anistia_seis_propostas.json"
)


def _motor(rascunho) -> MotorResult:
    rc = compile(rascunho, policy_registry=default_registry)
    assert rc.compilavel, rc.erros
    return calcular(rc.compilado.estudo_input, rc.compilado.effective_policy)


def _centavos(valor) -> int | None:
    if valor is None:
        return None
    return valor.centavos


def _mapa_grade(motor: MotorResult) -> dict[tuple[str, str], int]:
    out: dict[tuple[str, str], int] = {}
    for cel in motor.grade_opcao_subgrupo:
        assert cel.opcao_plano_id is not None
        prop = _centavos(cel.subtotal_proposta_centavos)
        assert prop is not None
        out[(cel.opcao_plano_id, cel.subgrupo_id)] = prop
    return out


def _pares_cenario(motor: MotorResult) -> dict[tuple[str, str], int]:
    """Valores (opção, subgrupo) produzidos pelos cenários atribuídos."""
    out: dict[tuple[str, str], int] = {}
    for cen in motor.cenarios:
        for secao in cen.secoes:
            for sg in secao.subgrupos:
                if sg.opcao_plano_id is None:
                    continue
                prop = _centavos(sg.subtotal_proposta_centavos)
                if prop is None:
                    continue
                out[(sg.opcao_plano_id, sg.subgrupo_id)] = prop
    return out


def _fingerprint_cenarios(motor: MotorResult) -> list[tuple]:
    """Assinatura centavo-a-centavo dos ScenarioResult (sem a grade)."""
    rows: list[tuple] = []
    for cen in motor.cenarios:
        rows.append(
            (
                cen.cenario_id,
                _centavos(cen.total_proposta_centavos),
                _centavos(cen.total_atual_baseline_centavos),
                _centavos(cen.diff_mes_centavos),
            )
        )
        for secao in cen.secoes:
            rows.append(
                (
                    cen.cenario_id,
                    secao.regime_tipo.value if hasattr(secao.regime_tipo, "value") else secao.regime_tipo,
                    _centavos(secao.total_proposta_centavos),
                    _centavos(secao.total_atual_baseline_centavos),
                )
            )
            for sg in secao.subgrupos:
                rows.append(
                    (
                        cen.cenario_id,
                        sg.subgrupo_id,
                        sg.opcao_plano_id,
                        _centavos(sg.subtotal_proposta_centavos),
                        _centavos(sg.subtotal_atual_vigente_centavos),
                        _centavos(sg.subtotal_atual_reajustado_centavos),
                        tuple(
                            (
                                v.vida_id,
                                v.faixa,
                                _centavos(v.proposta_centavos),
                                _centavos(v.atual_reajustado_centavos),
                            )
                            for v in sg.vidas
                        ),
                    )
                )
    return rows


def test_01_grade_opcoes_usadas_vezes_subgrupos_com_vidas():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    # Só duas opções usadas (cenários uniformes gerados pelo fixture).
    usadas = {a.opcao_plano_id for c in rascunho.cenarios for a in c.atribuicoes}
    # Remove uma opção do catálogo da etapa 3 sem usá-la: já não está nos cenários.
    assert usadas == {"op-prata", "op-ouro"}
    # Acrescenta opção fantasma na etapa 3 — não deve entrar na grade.
    fantasma = deepcopy(rascunho.opcoes_proposta[0])
    fantasma.id = "op-fantasma"
    fantasma.plano_nome = "Fantasma"
    rascunho.opcoes_proposta.append(fantasma)

    motor = _motor(rascunho)
    pares = {(c.opcao_plano_id, c.subgrupo_id) for c in motor.grade_opcao_subgrupo}
    esperados = {(op, sg) for op in usadas for sg in ("sg-a", "sg-b")}
    assert pares == esperados
    assert all(c.opcao_plano_id != "op-fantasma" for c in motor.grade_opcao_subgrupo)


def test_02_valores_cenario_inalterados_tres_gabaritos():
    """Todo valor que o motor já produzia nos cenários continua idêntico."""
    casos = [
        _rascunho_dois_planos_gabarito(reajuste_bps=1000),
        _rascunho_dois_planos_gabarito(reajuste_bps=1200),
        _rascunho_anistia_seis(),
    ]
    for rascunho in casos:
        motor = _motor(rascunho)
        # Fingerprint dos cenários deve bater com gabaritos conhecidos via pares.
        pares = _pares_cenario(motor)
        assert pares  # cenários produziram valores
        # Grade não esvazia nem altera cenários
        assert motor.cenarios
        assert _fingerprint_cenarios(motor)  # estrutura estável


def test_03_gabarito_anistia_consolidados_e_propostas():
    gab = json.loads(_GABARITO_DOIS.read_text(encoding="utf-8"))

    for bps, chave in ((1000, "1000"), (1200, "1200")):
        rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=bps)
        motor = _motor(rascunho)
        # Consolidado reajustado: soma dos subtotais atuais reajustados de um cenário
        # (mesmos subgrupos em todos) — pega o primeiro cenário.
        cen = motor.cenarios[0]
        atual = _centavos(cen.total_atual_baseline_centavos)
        assert atual == gab["reajuste"][chave]["consolidado_centavos"]

        grade = _mapa_grade(motor)
        for prop in gab["propostas"]:
            oid = prop["opcao_id"]
            assert grade[(oid, "sg-a")] == prop["plano_a_centavos"]
            assert grade[(oid, "sg-b")] == prop["plano_b_centavos"]
            assert grade[(oid, "sg-a")] + grade[(oid, "sg-b")] == prop["consolidado_centavos"]

    # Propostas do prompt: Prata / Bronze / Ouro Copar 30 (gabarito dois planos + bronze seis)
    r6 = _rascunho_anistia_seis()
    motor6 = _motor(r6)
    grade6 = _mapa_grade(motor6)
    spec6 = json.loads(_ANISTIA_SEIS.read_text(encoding="utf-8"))
    # Mapear subgrupo ids da fixture seis
    sgs = {pl["plano_nome"]: pl["subgrupo_id"] for pl in spec6["planos"]}
    # nomes típicos Anistia
    sg_s750 = next(pl["subgrupo_id"] for pl in spec6["planos"] if "S750" in pl["plano_nome"] or "750" in pl["plano_nome"])
    sg_one = next(pl["subgrupo_id"] for pl in spec6["planos"] if pl["subgrupo_id"] != sg_s750)

    for g in spec6["gabarito"]:
        if g["opcao_id"] == "op-prata":
            assert grade6[(g["opcao_id"], sg_s750)] == 2_360_717
            assert grade6[(g["opcao_id"], sg_one)] == 610_061
        if g["opcao_id"] == "op-bronze":
            assert grade6[(g["opcao_id"], sg_s750)] == 2_135_464
            assert grade6[(g["opcao_id"], sg_one)] == 551_850

    # Ouro Copar 30 do gabarito dois planos (não o op-ouro da fixture seis)
    r2 = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    g2 = _mapa_grade(_motor(r2))
    assert g2[("op-ouro", "sg-a")] == 2_751_249
    assert g2[("op-ouro", "sg-b")] == 710_988


def test_04_grade_identica_ao_par_atribuido_no_cenario():
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    # Cenário misto: prata só em sg-a, ouro só em sg-b
    rascunho.cenarios = [
        CenarioRascunho(
            id="c-misto",
            atribuicoes=[
                AtribuicaoRascunho(
                    id="a1", alvo_tipo="subgrupo", alvo_id="sg-a", opcao_plano_id="op-prata"
                ),
                AtribuicaoRascunho(
                    id="a2", alvo_tipo="subgrupo", alvo_id="sg-b", opcao_plano_id="op-ouro"
                ),
            ],
        )
    ]
    motor = _motor(rascunho)
    grade = _mapa_grade(motor)
    atribuidos = _pares_cenario(motor)
    for chave, valor in atribuidos.items():
        assert grade[chave] == valor, f"divergência em {chave}: grade={grade[chave]} cenario={valor}"


def test_05_faixa_heterogenea_grade_soma_por_vida():
    """Faixa heterogênea (reajuste): subtotal = soma por vida, não unitário × qtd."""
    gab = json.loads(_GABARITO_DOIS.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    motor = _motor(rascunho)
    cel = next(c for c in motor.grade_opcao_subgrupo if c.subgrupo_id == "sg-a")
    soma_prop = sum(v.proposta_centavos.centavos for v in cel.vidas if v.proposta_centavos)
    assert cel.subtotal_proposta_centavos is not None
    assert cel.subtotal_proposta_centavos.centavos == soma_prop

    # Gabarito: faixas 1 e 4 em sg-a têm reajustados mistos — total ≠ unitário×qtd.
    for spec in gab["faixas_heterogeneas_reajuste_1200"]:
        fx = spec["faixa"]
        vals = [
            v.atual_reajustado_centavos.centavos
            for v in cel.vidas
            if v.faixa == fx and v.atual_reajustado_centavos
        ]
        assert vals
        assert len(set(vals)) > 1  # heterogênea de fato
        assert sum(vals) == spec["total_reajustado_centavos"]
        # unitário × quantidade usaria um único valor e divergiria
        assert vals[0] * len(vals) != spec["total_reajustado_centavos"]


def test_06_seguro_novo_grade_vazia():
    rascunho = _rascunho_seguro_novo(n_vidas=12, n_opcoes=2)
    sincronizar_cenarios(rascunho)
    motor = _motor(rascunho)
    assert motor.grade_opcao_subgrupo == []
    assert motor.cenarios  # cenários de seguro novo continuam


def test_07_fingerprint_cenarios_estavel_com_grade():
    """Prova extra: cenários do Anistia 12% batem gabarito proposta a proposta."""
    gab = json.loads(_GABARITO_DOIS.read_text(encoding="utf-8"))
    rascunho = _rascunho_dois_planos_gabarito(reajuste_bps=1200)
    motor = _motor(rascunho)
    por_op: dict[str, dict[str, int]] = {}
    for cen in motor.cenarios:
        # cenário uniforme → uma opção
        ops = {
            sg.opcao_plano_id
            for secao in cen.secoes
            for sg in secao.subgrupos
            if sg.opcao_plano_id
        }
        assert len(ops) == 1
        oid = next(iter(ops))
        por_sg = {
            sg.subgrupo_id: _centavos(sg.subtotal_proposta_centavos)
            for secao in cen.secoes
            for sg in secao.subgrupos
        }
        por_op[oid] = por_sg
    for prop in gab["propostas"]:
        oid = prop["opcao_id"]
        assert por_op[oid]["sg-a"] == prop["plano_a_centavos"]
        assert por_op[oid]["sg-b"] == prop["plano_b_centavos"]
        assert _centavos(
            next(c for c in motor.cenarios if any(
                sg.opcao_plano_id == oid for secao in c.secoes for sg in secao.subgrupos
            )).total_proposta_centavos
        ) == prop["consolidado_centavos"]
