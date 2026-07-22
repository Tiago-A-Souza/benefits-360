# Relatório de Implementação — ETAPA 1 + ETAPA 1.1

> Motor financeiro puro + auditoria/correção 1.1 · UTF-8 · 2026-07-22

---

## 1. Módulos e fronteira pública

| Módulo | Responsabilidade |
|--------|------------------|
| `finance.py` | **Novo (1.1)** — normalização por `price_basis`, IOF, estratégias |
| `types.py` | Tipos + `PrecedenciaAtualVida` |
| `money.py` | Aritmética inteiros, `round_half_up` simétrico (+/−) |
| `rounding.py` | Delegação a `finance` (sem omitir IOF em `no_total`) |
| `models.py` | Entrada tipada, validadores Pydantic (faixas, duplicatas, negativos) |
| `policy.py` | `EffectivePolicy` + `precedencia_atual_vida` |
| `reconciliation.py` | B-02 em 5 níveis, reconciliação **agregada por opção** |
| `calculation.py` | Cálculo + agregação por opção no cenário |
| `validations.py` | B-03…B-08, entrada estrutural, basis pré-cálculo |
| `engine.py` | `calcular(estudo, policy) -> MotorResult` |

```python
from newport_motor import calcular, EstudoInput, EffectivePolicy, MotorResult
```

---

## 2. Resultado dos testes

```
50 passed in 0.22s
```

| Suíte | Testes | Resultado |
|-------|--------|-----------|
| A — Tipos/aritmética | 7 | PASSOU |
| B — Reconciliação | 5 | PASSOU |
| C — IOF/price_basis | 3 | PASSOU |
| D — Atual/reajuste | 2 | PASSOU |
| E — Idade/faixa/precedência | 6 | PASSOU |
| F — Cenários/seções | 2 | PASSOU |
| G — Pureza/policy | 3 | PASSOU |
| H — Escala/proveniência | 6 | PASSOU |
| **Fixtures JSON** | 16 | PASSOU |

---

## 3. Fixtures determinísticas (expected via oráculo independente)

Oráculo: `tests/oracle_independente.py` (não importa o motor).  
Gerador (authoring): `tests/generate_fixtures.py`.

| Fixture | Cobertura principal |
|---------|---------------------|
| `novo_1vida_sem_copart` | Seguro novo, 1 vida, operadora sem IOF, sem copart |
| `renovacao_1plano_12vidas` | Renovação 1 plano, 12 vidas |
| `renovacao_2planos_20vidas` | 2 planos atuais, 20 vidas, regimes distintos |
| `renovacao_29vidas` | 29 vidas (limite piloto) |
| `copart_parcial_1vida` | Copart parcial |
| `copart_percentual_1vida` | Copart percentual |
| `seguradora_tabela_inclui_iof` | Tabela `inclui_iof` — IOF não reaplicado |
| `total_recorrente_ausente` | Total impresso ausente |
| `primeira_parcela_custos_unicos` | 1ª parcela = recorrente + custos únicos |
| `mesma_opcao_dois_subgrupos` | Reconciliação agregada (1 opção → 2 subgrupos) |
| `divergencia_por_vida` | B-02 por vida |
| `divergencia_subtotal` | B-02 subtotal |
| `divergencia_total` | B-02 total agregado |
| `price_basis_desconhecido` | Bloqueio pré-cálculo |
| `arredondamento_soma_entao_aplica` | Estratégia `soma_entao_aplica` |

Cada diretório contém: `input.json`, `effective_policy.json`, `expected.json`, `README.md`.

---

## 4. Matriz requisito → teste

| Requisito ETAPA 1.1 | Teste(s) |
|---------------------|----------|
| `price_basis` em todos os cálculos | A (`inclui_iof`/`exclui_iof`), C, fixtures `seguradora_tabela_inclui_iof`, `price_basis_desconhecido` |
| `desconhecido` bloqueia antes do cálculo | `price_basis_desconhecido`, C, B |
| B-02 por vida | `divergencia_por_vida`, B |
| B-02 subtotal | `divergencia_subtotal`, B |
| B-02 prêmio+IOF vs recorrente | B (quando componentes presentes) |
| B-02 total agregado por opção | `mesma_opcao_dois_subgrupos`, `divergencia_total`, B |
| B-02 primeira parcela | `primeira_parcela_custos_unicos` |
| `no_total` sem omitir IOF | A `test_no_total_aplica_iof_no_agregado` |
| `round_half_up` negativo | A `test_round_half_up_negativo` |
| `PriceBasis` enum em modelos | modelos Pydantic + fixtures JSON |
| Faixas duplicadas/fora 0–9/negativos | validadores em `models.py` |
| Subtotal zero ≠ None | B `test_subtotal_zero_nao_vira_none` |
| Precedência tabela vs fatura | E `test_precedencia_*`, policy `precedencia_atual_vida` |
| Escalas 1/12/20/29 vidas | H, fixtures `renovacao_*` |
| Copart sem/parcial/percentual | H, fixtures `copart_*` |
| Seguradora IOF / operadora sem | C, `novo_1vida_sem_copart` |
| Estratégias arredondamento | A, `arredondamento_soma_entao_aplica` |

---

## 5. Bloqueios B-01…B-08

| Bloqueio | Camada | Cobertura 1.1 |
|----------|--------|---------------|
| B-01 | Aplicação (adiado) | — |
| B-02 | Motor | Reconciliação 5 níveis + fixtures divergência |
| B-03 | Motor (parcial) | H |
| B-04 | Motor | E (+ precedência não altera auditoria B-04) |
| B-05 | Motor | Validadores + entrada estrutural |
| B-06 | Motor | F |
| B-07 | Motor | E (+ `precedencia_atual_vida`) |
| B-08 | Motor | H, `renovacao_29vidas` |

---

## 6. Decisões ainda não homologadas (sem regra global inventada)

| Tema | Comportamento atual | Escolha bloqueante |
|------|---------------------|-------------------|
| DP-01 | Data referência obrigatória | B-07 |
| DP-02 | `price_basis` por componente; `desconhecido` bloqueia | B-02 pré-cálculo |
| DP-02 precedência atual | `precedencia_atual_vida` na policy | B-07 se tabela+fatura coexistem |
| DP-03/04 | Baseline + reajuste obrigatórios em renovação | B-07 |
| DP-06 | Regime tipado (não registry) | B-05 |
| DP-07 | Alerta copart >2% | **Não implementado** — faltam dados de referência na entrada |
| DP-11 | Tolerâncias via `EffectivePolicy` | B-02 |
| Faixas etárias | Mapeamento ANS padrão (10 faixas) | Homologação pendente |

---

## 7. Limitações conhecidas (honestas)

- Motor **não aprovado** como confiável para produção — checkpoint técnico pós-auditoria 1.1.
- `no_total`: IOF aplicado no agregador; valores por vida ficam em base exclui_iof.
- DP-07 (alerta copart) adiada por falta de campos de referência de copart na entrada tipada.
- Oráculo de fixtures é independente do motor, mas duplica fórmulas — risco de drift; expected.json é a fonte commitada.

---

## 8. Componentes proibidos

Confirmado: nenhum FastAPI, React, Postgres, worker, PPTX, parser ou IA.
