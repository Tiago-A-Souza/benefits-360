# Relatório de Implementação — ETAPA 1 + ETAPA 1.1 + ETAPA 1.1.1

> Motor financeiro puro + auditoria/correção 1.1 + correções piloto 1.1.1 · UTF-8 · 2026-07-22

---

## 1. Módulos e fronteira pública

| Módulo | Responsabilidade |
|--------|------------------|
| `finance.py` | Normalização por `price_basis`, IOF, estratégias; **1.1.1** — semântica prêmio+IOF, 1ª parcela |
| `types.py` | Tipos + `PrecedenciaAtualVida` + **`AlvoTipo`** (`vida` \| `subgrupo`) |
| `money.py` | Aritmética inteiros, `round_half_up` simétrico (+/−) |
| `rounding.py` | Delegação a `finance` |
| `models.py` | Entrada tipada; `AtribuicaoPlano.alvo_tipo` tipado como `AlvoTipo` |
| `policy.py` | `EffectivePolicy` + `precedencia_atual_vida` |
| `reconciliation.py` | B-02 em 5 níveis; **1.1.1** — prêmio+IOF e 1ª parcela com bases distintas |
| `calculation.py` | Cálculo + agregação por opção no cenário |
| `validations.py` | B-03…B-08; **1.1.1** — B-07 para estratégias não homologadas no piloto |
| `engine.py` | `calcular(estudo, policy) -> MotorResult` |

```python
from newport_motor import calcular, EstudoInput, EffectivePolicy, MotorResult
```

### 1.1. Estratégia de arredondamento no piloto (Alternativa A)

| Estratégia | Enum | Piloto |
|------------|------|--------|
| `por_vida_entao_soma` | `RoundingStrategy.POR_VIDA_ENTAO_SOMA` | **Homologada e operacional** |
| `soma_entao_aplica` | `RoundingStrategy.SOMA_ENTAO_APLICA` | Reservada — **B-07 bloqueante** |
| `no_total` | `RoundingStrategy.NO_TOTAL` | Reservada — **B-07 bloqueante** |

Código das estratégias reservadas permanece em `finance.py` para uso futuro; o motor não as executa no piloto.

### 1.2. Semântica prêmio + IOF (1.1.1)

- `iof.centavos` = valor absoluto da linha extraída; **nunca** recebe IOF novamente.
- `premio_saude` em `exclui_iof` + IOF explícito → recorrente = prêmio + IOF.
- `premio_saude` em `inclui_iof` → recorrente = prêmio (linha IOF informativa).
- `premio_saude` em `exclui_iof` sem IOF explícito → IOF calculado pela policy.

### 1.3. Primeira parcela (1.1.1)

Identidade: **primeira parcela = total recorrente + custos únicos**.

Custos únicos nunca recebem IOF. Se a 1ª parcela está em `exclui_iof`, normaliza-se apenas a parte recorrente (`parcela − custos`) antes de comparar com o recorrente impresso.

---

## 2. Resultado dos testes

```
59 passed in 0.16s
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
| **1.1.1 — Correções piloto** | 10 | PASSOU |
| **Fixtures JSON** | 15 | PASSOU |

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
| `arredondamento_soma_entao_aplica` | `soma_entao_aplica` bloqueada com B-07 no piloto |

Cada diretório contém: `input.json`, `effective_policy.json`, `expected.json`, `README.md`.

---

## 4. Matriz requisito → teste

| Requisito ETAPA 1.1 / 1.1.1 | Teste(s) |
|-----------------------------|----------|
| `price_basis` em todos os cálculos | A (`inclui_iof`/`exclui_iof`), C, fixtures `seguradora_tabela_inclui_iof`, `price_basis_desconhecido` |
| `desconhecido` bloqueia antes do cálculo | `price_basis_desconhecido`, C, B |
| B-02 por vida | `divergencia_por_vida`, B |
| B-02 subtotal | `divergencia_subtotal`, B |
| B-02 prêmio+IOF vs recorrente | 1.1.1 `test_premio_*`, B |
| B-02 total agregado por opção | `mesma_opcao_dois_subgrupos`, `divergencia_total`, B |
| B-02 primeira parcela (bases distintas) | 1.1.1 `test_primeira_parcela_*`, `primeira_parcela_custos_unicos` |
| `por_vida_entao_soma` operacional | 1.1.1 `test_por_vida_entao_soma_operacional`, A |
| `soma_entao_aplica` / `no_total` → B-07 | 1.1.1, fixture `arredondamento_soma_entao_aplica` |
| `inclui_iof` preservado exatamente | A, 1.1.1 |
| `AlvoTipo` enum | 1.1.1 `test_alvo_tipo_invalido_rejeitado`, models |
| `no_total` código reservado (finance) | A `test_no_total_codigo_reservado_*` |
| `round_half_up` negativo | A `test_round_half_up_negativo` |
| `PriceBasis` enum em modelos | modelos Pydantic + fixtures JSON |
| Faixas duplicadas/fora 0–9/negativos | validadores em `models.py` |
| Subtotal zero ≠ None | B `test_subtotal_zero_nao_vira_none` |
| Precedência tabela vs fatura | E `test_precedencia_*`, policy `precedencia_atual_vida` |
| Escalas 1/12/20/29 vidas | H, fixtures `renovacao_*` |
| Copart sem/parcial/percentual | H, fixtures `copart_*` |
| Seguradora IOF / operadora sem | C, `novo_1vida_sem_copart` |

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
| B-07 | Motor | E (+ `precedencia_atual_vida`); **1.1.1** — estratégias não homologadas no piloto |
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
| DP-11 | Tolerâncias via `EffectivePolicy`; piloto só `por_vida_entao_soma` | B-02 / B-07 |
| Faixas etárias | Mapeamento ANS padrão (10 faixas) | Homologação pendente |

---

## 7. Limitações conhecidas (honestas)

- Motor **não aprovado** como confiável para produção — checkpoint técnico pós-correções 1.1.1.
- **Piloto:** somente `por_vida_entao_soma` homologada; `soma_entao_aplica` e `no_total` bloqueiam com B-07 (código reservado em `finance.py`).
- DP-07 (alerta copart) adiada por falta de campos de referência de copart na entrada tipada.
- Oráculo de fixtures é independente do motor, mas duplica fórmulas — risco de drift; expected.json é a fonte commitada.

---

## 8. Componentes proibidos

Confirmado: nenhum FastAPI, React, Postgres, worker, PPTX, parser ou IA.
