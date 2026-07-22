"""Gera fixtures JSON com expected via oráculo independente (não usa motor)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from oracle_independente import apply_iof_exclui, faixa_idade, recorrente, valor_tabela

FIXTURES = Path(__file__).parent / "fixtures"
REF = date(2026, 6, 30)
IOF_BPS = 238


def faixa_em(nasc: date, ref: date = REF) -> tuple[int, int]:
    idade = ref.year - nasc.year - ((ref.month, ref.day) < (nasc.month, nasc.day))
    return idade, faixa_idade(idade)


def tabela_json(base=100_000, inc=10_000, basis="exclui_iof"):
    return [
        {
            "faixa": f,
            "valor_centavos": base + f * inc,
            "quantidade_cotada": 0,
            "price_basis": basis,
        }
        for f in range(10)
    ]


def policy_json(**kw):
    base = {
        "policy_set_versao": "fixture-v1",
        "data_referencia_idade": "2026-06-30",
        "baseline_escolhido": "reajustado",
        "precedencia_atual_vida": "tabela_atual",
        "iof_bps": IOF_BPS,
        "estrategia_arredondamento": "por_vida_entao_soma",
    }
    base.update(kw)
    return base


def write_case(name: str, input_data: dict, policy: dict, expected: dict, readme: str):
    d = FIXTURES / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "input.json").write_text(json.dumps(input_data, indent=2, ensure_ascii=False), encoding="utf-8")
    (d / "effective_policy.json").write_text(json.dumps(policy, indent=2), encoding="utf-8")
    (d / "expected.json").write_text(json.dumps(expected, indent=2), encoding="utf-8")
    (d / "README.md").write_text(readme, encoding="utf-8")


def main():
    # 1. novo_1vida_sem_copart
    _, fx = faixa_em(date(1990, 6, 15))
    prop = valor_tabela(fx)
    write_case(
        "novo_1vida_sem_copart",
        {
            "id": "novo-1",
            "formato": "novo",
            "vidas": [{"id": "v1", "nome": "Fictício A", "nascimento": "1990-06-15", "incluida": True}],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Amil", "plano_nome": "Amil Fictício",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "operadora",
                "tabela": tabela_json(basis="exclui_iof"),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": False, "proposta_total_centavos": prop, "bloqueios": []},
        "Seguro novo, 1 vida, operadora sem IOF, copart sem.",
    )

    # 2. renovacao_12vidas_1plano
    vidas = []
    total = 0
    for i in range(12):
        nasc = date(1970 + i, 1, 1)
        _, fx = faixa_em(nasc)
        vidas.append({
            "id": f"v{i}", "nome": f"Fictício {i}", "nascimento": nasc.isoformat(),
            "incluida": True, "subgrupo_atual_id": "sg-1",
        })
        total += recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "renovacao_1plano_12vidas",
        {
            "id": "ren-12",
            "formato": "renovacao",
            "vidas": vidas,
            "subgrupos_atuais": [{
                "id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora",
                "plano_nome": "Atual", "regime_copart_id": "regime-sem",
                "reajuste_bps": 1198, "fatura_price_basis": "exclui_iof",
                "tabela_atual": tabela_json(80_000, 8_000),
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "Proposta",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": False, "proposta_total_centavos": total, "vidas_count": 12, "bloqueios": []},
        "Renovação 1 plano, 12 vidas, total impresso ausente.",
    )

    # 3. seguradora_tabela_inclui_iof
    _, fx = faixa_em(date(1985, 3, 10))
    val_inclui = recorrente(valor_tabela(fx), "inclui_iof", "seguradora")
    tabela_inclui = tabela_json(basis="inclui_iof")
    for t in tabela_inclui:
        if t["faixa"] == fx:
            t["valor_centavos"] = val_inclui
    write_case(
        "seguradora_tabela_inclui_iof",
        {
            "id": "inclui-iof",
            "formato": "novo",
            "vidas": [{"id": "v1", "nome": "Fictício", "nascimento": "1985-03-10", "incluida": True}],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_inclui,
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": False, "proposta_total_centavos": val_inclui, "bloqueios": []},
        "Tabela proposta inclui_iof — IOF não reaplicado.",
    )

    # 4. total_ausente
    write_case(
        "total_recorrente_ausente",
        {
            "id": "sem-total",
            "formato": "renovacao",
            "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True, "subgrupo_atual_id": "sg-1"}],
            "subgrupos_atuais": [{
                "id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora",
                "plano_nome": "A", "regime_copart_id": "regime-sem", "reajuste_bps": 1000,
                "fatura_price_basis": "exclui_iof", "tabela_atual": tabela_json(80_000, 8_000),
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": False, "tem_cenarios": True, "bloqueios_b02": []},
        "Total recorrente ausente — cálculo ok, sem B-02 de total.",
    )

    # 5. price_basis_desconhecido
    tabela_desc = tabela_json()
    tabela_desc[0]["price_basis"] = "desconhecido"
    write_case(
        "price_basis_desconhecido",
        {
            "id": "desc",
            "formato": "novo",
            "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True}],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_desc,
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": True, "bloqueios": ["B-02"], "tem_cenarios": False},
        "price_basis desconhecido bloqueia antes do cálculo.",
    )

    # 6. divergencia_total
    _, fx = faixa_em(date(1990, 1, 1))
    calc = recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "divergencia_total",
        {
            "id": "div-total",
            "formato": "novo",
            "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True}],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
                "total_recorrente": {"centavos": 99999999, "price_basis": "inclui_iof",
                    "proveniencia": {"origem": "manual", "confirmado": True}},
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": True, "bloqueios": ["B-02"], "proposta_total_centavos": calc},
        "Total impresso diverge do calculado agregado.",
    )

    # 7. mesma_opcao_dois_subgrupos
    v1_fx = faixa_em(date(1988, 1, 1))[1]
    v2_fx = faixa_em(date(1992, 1, 1))[1]
    t1 = recorrente(valor_tabela(v1_fx), "exclui_iof", "seguradora")
    t2 = recorrente(valor_tabela(v2_fx), "exclui_iof", "seguradora")
    write_case(
        "mesma_opcao_dois_subgrupos",
        {
            "id": "2sg-1op",
            "formato": "renovacao",
            "vidas": [
                {"id": "v1", "nome": "F1", "nascimento": "1988-01-01", "incluida": True, "subgrupo_atual_id": "sg-1"},
                {"id": "v2", "nome": "F2", "nascimento": "1992-01-01", "incluida": True, "subgrupo_atual_id": "sg-2"},
            ],
            "subgrupos_atuais": [
                {"id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora", "plano_nome": "A1",
                 "regime_copart_id": "regime-sem", "reajuste_bps": 1198, "fatura_price_basis": "exclui_iof",
                 "tabela_atual": tabela_json(80_000, 8_000)},
                {"id": "sg-2", "operadora": "Bradesco", "tipo_fiscal": "seguradora", "plano_nome": "A2",
                 "regime_copart_id": "regime-sem", "reajuste_bps": 1198, "fatura_price_basis": "exclui_iof",
                 "tabela_atual": tabela_json(80_000, 8_000)},
            ],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
                "total_recorrente": {"centavos": t1 + t2, "price_basis": "inclui_iof",
                    "proveniencia": {"origem": "manual", "confirmado": True}},
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"},
                {"id": "a2", "alvo_tipo": "subgrupo", "alvo_id": "sg-2", "opcao_plano_id": "op-1"},
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": False, "proposta_total_centavos": t1 + t2, "subgrupos": 2, "bloqueios": []},
        "Mesma opção atribuída a dois subgrupos — reconciliação agregada.",
    )

    # 8. copart_parcial e percentual — compact
    for tipo in ("parcial", "percentual"):
        _, fx = faixa_em(date(1990, 6, 1))
        p = recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
        write_case(
            f"copart_{tipo}_1vida",
            {
                "id": f"copart-{tipo}",
                "formato": "novo",
                "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-06-01", "incluida": True}],
                "opcoes_plano": [{
                    "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                    "regime_copart_id": f"regime-{tipo}", "tipo_fiscal": "seguradora",
                    "tabela": tabela_json(),
                }],
                "regimes_copart": [{"id": f"regime-{tipo}", "tipo": tipo}],
                "cenarios": [{"id": "c1", "atribuicoes": [
                    {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
                ]}],
            },
            policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
            {"tem_bloqueio": False, "proposta_total_centavos": p, "regime": tipo, "bloqueios": []},
            f"Coparticipação {tipo}, 1 vida.",
        )

    # 9. primeira_parcela_custos_unicos
    _, fx = faixa_em(date(1990, 1, 1))
    rec = recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    custo = 50_000
    write_case(
        "primeira_parcela_custos_unicos",
        {
            "id": "1a-parcela",
            "formato": "novo",
            "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True}],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Porto", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
                "total_recorrente": {"centavos": rec, "price_basis": "inclui_iof",
                    "proveniencia": {"origem": "manual", "confirmado": True}},
                "total_primeira_parcela": {"centavos": rec + custo, "price_basis": "inclui_iof",
                    "proveniencia": {"origem": "manual", "confirmado": True}},
                "custos_unicos": [{"id": "cu1", "descricao": "Taxa inscrição", "valor_centavos": custo}],
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": False, "proposta_total_centavos": rec, "bloqueios": []},
        "Primeira parcela = recorrente + custos únicos.",
    )

    # 10. divergencia_por_vida
    _, fx = faixa_em(date(1990, 1, 1))
    calc_v = recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "divergencia_por_vida",
        {
            "id": "div-vida",
            "formato": "novo",
            "vidas": [{
                "id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True,
                "valor_conferencia_centavos": calc_v + 100,
                "conferencia_price_basis": "inclui_iof",
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "vida", "alvo_id": "v1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(baseline_escolhido=None, precedencia_atual_vida=None),
        {"tem_bloqueio": True, "bloqueios": ["B-02"], "proposta_total_centavos": calc_v},
        "Divergência por vida além da tolerância.",
    )

    # 11. renovacao_29vidas
    vidas29 = []
    tot29 = 0
    for i in range(29):
        nasc = date(1960 + (i % 40), 1, 1)
        _, fx = faixa_em(nasc)
        vidas29.append({"id": f"v{i}", "nome": f"F{i}", "nascimento": nasc.isoformat(),
                        "incluida": True, "subgrupo_atual_id": "sg-1"})
        tot29 += recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "renovacao_29vidas",
        {
            "id": "ren-29",
            "formato": "renovacao",
            "vidas": vidas29,
            "subgrupos_atuais": [{
                "id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora",
                "plano_nome": "A", "regime_copart_id": "regime-sem", "reajuste_bps": 1198,
                "fatura_price_basis": "exclui_iof", "tabela_atual": tabela_json(80_000, 8_000),
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": False, "proposta_total_centavos": tot29, "vidas_count": 29, "bloqueios": []},
        "Renovação com 29 vidas (limite piloto).",
    )

    # 12. renovacao_2planos_20vidas
    vidas20 = []
    tot20 = 0
    for i in range(20):
        sg = "sg-1" if i < 10 else "sg-2"
        nasc = date(1965 + (i % 35), 6, 1)
        _, fx = faixa_em(nasc)
        vidas20.append({"id": f"v{i}", "nome": f"F{i}", "nascimento": nasc.isoformat(),
                        "incluida": True, "subgrupo_atual_id": sg})
        tot20 += recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "renovacao_2planos_20vidas",
        {
            "id": "ren-20-2p",
            "formato": "renovacao",
            "vidas": vidas20,
            "subgrupos_atuais": [
                {"id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora", "plano_nome": "A1",
                 "regime_copart_id": "regime-sem", "reajuste_bps": 1198, "fatura_price_basis": "exclui_iof",
                 "tabela_atual": tabela_json(80_000, 8_000)},
                {"id": "sg-2", "operadora": "Amil", "tipo_fiscal": "operadora", "plano_nome": "A2",
                 "regime_copart_id": "regime-parcial", "reajuste_bps": 1000, "fatura_price_basis": "exclui_iof",
                 "tabela_atual": tabela_json(70_000, 7_000)},
            ],
            "opcoes_plano": [
                {"id": "op-1", "operadora": "Bradesco", "plano_nome": "P1",
                 "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora", "tabela": tabela_json()},
                {"id": "op-2", "operadora": "Amil", "plano_nome": "P2",
                 "regime_copart_id": "regime-parcial", "tipo_fiscal": "operadora",
                 "tabela": tabela_json(90_000, 9_000)},
            ],
            "regimes_copart": [
                {"id": "regime-sem", "tipo": "sem"},
                {"id": "regime-parcial", "tipo": "parcial"},
            ],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"},
                {"id": "a2", "alvo_tipo": "subgrupo", "alvo_id": "sg-2", "opcao_plano_id": "op-2"},
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": False, "secoes_count": 2, "vidas_count": 20, "bloqueios": []},
        "Renovação 2 planos atuais, 20 vidas, regimes distintos.",
    )

    # 13. arredondamento_soma_entao_aplica
    write_case(
        "arredondamento_soma_entao_aplica",
        {
            "id": "soma-iof",
            "formato": "renovacao",
            "vidas": [
                {"id": "v1", "nome": "F1", "nascimento": "1990-01-01", "incluida": True, "subgrupo_atual_id": "sg-1"},
                {"id": "v2", "nome": "F2", "nascimento": "1985-01-01", "incluida": True, "subgrupo_atual_id": "sg-1"},
            ],
            "subgrupos_atuais": [{
                "id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora",
                "plano_nome": "A", "regime_copart_id": "regime-sem", "reajuste_bps": 1198,
                "fatura_price_basis": "exclui_iof", "tabela_atual": tabela_json(80_000, 8_000),
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(estrategia_arredondamento="soma_entao_aplica"),
        {"tem_bloqueio": False, "estrategia": "soma_entao_aplica", "bloqueios": []},
        "Estratégia soma_entao_aplica.",
    )

    # 14. divergencia_subtotal
    _, fx = faixa_em(date(1990, 1, 1))
    sub_calc = recorrente(valor_tabela(fx), "exclui_iof", "seguradora")
    write_case(
        "divergencia_subtotal",
        {
            "id": "div-sub",
            "formato": "renovacao",
            "vidas": [{"id": "v1", "nome": "F", "nascimento": "1990-01-01", "incluida": True, "subgrupo_atual_id": "sg-1"}],
            "subgrupos_atuais": [{
                "id": "sg-1", "operadora": "Bradesco", "tipo_fiscal": "seguradora",
                "plano_nome": "A", "regime_copart_id": "regime-sem", "reajuste_bps": 1198,
                "fatura_price_basis": "exclui_iof", "tabela_atual": tabela_json(80_000, 8_000),
                "subtotal_impresso": {"centavos": sub_calc + 50, "price_basis": "inclui_iof",
                    "proveniencia": {"origem": "manual", "confirmado": True}},
            }],
            "opcoes_plano": [{
                "id": "op-1", "operadora": "Bradesco", "plano_nome": "P",
                "regime_copart_id": "regime-sem", "tipo_fiscal": "seguradora",
                "tabela": tabela_json(),
            }],
            "regimes_copart": [{"id": "regime-sem", "tipo": "sem"}],
            "cenarios": [{"id": "c1", "atribuicoes": [
                {"id": "a1", "alvo_tipo": "subgrupo", "alvo_id": "sg-1", "opcao_plano_id": "op-1"}
            ]}],
        },
        policy_json(),
        {"tem_bloqueio": True, "bloqueios": ["B-02"], "subtotal_calculado_centavos": sub_calc},
        "Divergência de subtotal além da tolerância.",
    )

    print(f"Geradas {len(list(FIXTURES.glob('*')))} fixtures em {FIXTURES}")


if __name__ == "__main__":
    main()
