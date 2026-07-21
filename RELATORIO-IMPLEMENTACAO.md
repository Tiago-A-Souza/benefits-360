# Relatório de Implementação — ETAPA 1

> Motor financeiro puro + testes A–H · UTF-8 · 2026-07-21

---

## 1. Módulos entregues e fronteira pública

### Pacote `newport_motor` (`src/newport_motor/`)

| Módulo | Responsabilidade |
|--------|------------------|
| `types.py` | `MoneyCents`, `RateBasisPoints`, enums (`PriceBasis`, `RegimeCopartTipo`, etc.) |
| `money.py` | Aritmética em centavos inteiros, `apply_rate_bps`, half-up |
| `rounding.py` | Registry **somente** de estratégias de arredondamento (P3) |
| `models.py` | Entidades tipadas de entrada (`EstudoInput`, `Vida`, `OpcaoPlano`, …) |
| `policy.py` | `EffectivePolicy`, `TolerancePolicy` |
| `provenance.py` | `ProvenienciaCampo`, `ComponenteFinanceiro` |
| `faixa.py` | Idade/faixa na data de referência (10 faixas ANS) |
| `iof.py` | IOF por `tipo_fiscal` e normalização de `price_basis` |
| `calculation.py` | Cálculo por vida/subgrupo/cenário, `ScenarioResult` + seções |
| `reconciliation.py` | Reconciliação B-02 (P7) |
| `validations.py` | Bloqueios B-03…B-08 aplicáveis ao motor |
| `result.py` | `MotorResult`, `ScenarioResult`, `ScenarioSectionResult`, `Validacao` |
| `engine.py` | **`calcular(estudo, policy) -> MotorResult`** |

### Fronteira pública

```python
from newport_motor import calcular, EstudoInput, EffectivePolicy, MotorResult
```

- **Entrada:** `EstudoInput` (dados tipados em memória) + `EffectivePolicy` (já resolvida fora do motor).
- **Saída:** `MotorResult` com cenários calculados, validações, `politicas_efetivas` embutidas.
- **Sem I/O:** nenhum acesso a banco, arquivo, rede ou PPTX.

---

## 2. Resultado das suítes A–H

| Suíte | Arquivo | Testes | Resultado |
|-------|---------|--------|-----------|
| A | `tests/test_suite_a_types.py` | 5 | **PASSOU** |
| B | `tests/test_suite_b_reconciliation.py` | 4 | **PASSOU** |
| C | `tests/test_suite_c_iof_price_basis.py` | 3 | **PASSOU** |
| D | `tests/test_suite_d_atual_reajuste.py` | 2 | **PASSOU** |
| E | `tests/test_suite_e_idade_faixa.py` | 4 | **PASSOU** |
| F | `tests/test_suite_f_cenarios_secoes.py` | 2 | **PASSOU** |
| G | `tests/test_suite_g_pureza_policy.py` | 3 | **PASSOU** |
| H | `tests/test_suite_h_formas_escala.py` | 6 | **PASSOU** |
| **Total** | | **29** | **29 passed** |

### Fixtures

- Helpers programáticos em `tests/conftest.py` (dados 100% fictícios).
- Diretório `tests/fixtures/renovacao_1plano_12vidas/` documentado (formato JSON previsto para casos futuros).
- Nenhum PDF, planilha real ou PII utilizado.

---

## 3. Cobertura dos bloqueios B-01…B-08

| Bloqueio | Camada | Cobertura |
|----------|--------|-----------|
| **B-01** | **Adiado — camada de aplicação** | Aprovação de snapshot/PPTX (DP-14). Motor não implementa. |
| **B-02** | Motor | `reconciliation.py` + suíte B (ok, total ausente, bloqueante, tolerâncias da policy) |
| **B-03** | Motor (parcial) | `validations.py` — origem `ia` não confirmada; documento em alerta/falha. Suíte H. |
| **B-04** | Motor | `validations.py` — só com tabela atual comparável (P8). Suíte E. |
| **B-05** | Motor | Tabela incompleta / regime indefinido. Integrado em `engine.py`. |
| **B-06** | Motor | Atribuição ausente; seções disjuntas por regime (P6). Suíte F. |
| **B-07** | Motor | Data referência, baseline, reajuste ausentes. Suítes E, D. |
| **B-08** | Motor | >29 vidas ou zero vidas. Suíte H. |

---

## 4. Escolhas bloqueantes por estudo (defaults provisórios usados)

| DP | Default usado nos testes | Comportamento sem escolha |
|----|--------------------------|---------------------------|
| DP-01 | `2026-06-30` explícita na policy | B-07 bloqueia |
| DP-02 | `tipo_fiscal` → IOF; basis por componente | B-02 se `desconhecido` + divergência |
| DP-03 | `reajustado` | B-07 em renovação sem baseline |
| DP-04 | `reajuste_bps=1198` no subgrupo | B-07 se ausente em renovação |
| DP-06 | Regime informado por opção | B-05 se indefinido |
| DP-11 | Tolerâncias 1c/2c/5c via `EffectivePolicy` | B-02 se fora da faixa |

**Não inventados como regra global:** DP-05 (alerta), DP-07 (alerta >2%), DP-12 (alerta), DP-13/14 (camadas futuras).

---

## 5. Questões abertas e riscos

1. **Faixas etárias:** mapeamento ANS padrão (0–18…59+) implementado; operadoras podem usar limites distintos — requer homologação (DP-01).
2. **Tabela atual vs fatura:** B-04 compara fatura com tabela do subgrupo; critério de “comparável e identificada” simplificado para presença de `tabela_atual` não vazia.
3. **Registry de arredondamento:** implementado conforme P3/P4; **registry de copart não criado** — regime é dado tipado e critério de segmentação (orientação ETAPA 1).
4. **DP-07 (precedência copart >2%):** alerta não implementado no motor — depende de dados de referência de copart ainda não modelados na entrada tipada.
5. **Novo negócio:** cálculo de proposta por vida funciona; comparativo atual/reajustado limitado a renovação.
6. **Reajuste sobre base com IOF:** ordem P3 aplicada; validação contra faturas reais pendente (DP-11).

---

## 6. Componentes proibidos

Confirmado: **nenhum** FastAPI, React, Postgres, worker, PPTX, parser ou IA introduzido.

---

## 7. Execução dos testes

```
python -m pytest tests/ -v
============================= 29 passed in 0.12s ==============================
```
