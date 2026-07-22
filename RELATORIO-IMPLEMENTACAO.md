# Relatório de Implementação — ETAPA 1 + ETAPA 1.1 + ETAPA 1.1.1 + ETAPA 1.2 + ETAPA 1.2.1

> Motor financeiro puro · UTF-8 · 2026-07-22

---

## 1. Módulos e fronteira pública

| Módulo | Responsabilidade |
|--------|------------------|
| `finance.py` | Normalização por `price_basis`, IOF, estratégias; guarda 1ª parcela ≥ custos |
| `provenance.py` | `ProvenienciaCampo`, `LinhagemReferencia`, helpers de mesclagem |
| `types.py` | Tipos + `PrecedenciaAtualVida` + `AlvoTipo` |
| `models.py` | Entrada tipada; IDs únicos; `fatura_proveniencia` por vida |
| `policy.py` | `EffectivePolicy`; tolerâncias e `iof_bps` ≥ 0 |
| `reconciliation.py` | B-02: subtotal **atual** vs vigente; subtotal **proposta** vs total agregado |
| `calculation.py` | Cálculo com linhagem fatura/tabela/proposta na saída |
| `validations.py` | B-02…B-08 endurecidos (baseline, cenários, nascimento, B-03 atual) |
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

### 1.2. Endurecimento 1.2 (entrada e saída)

- **Baseline renovação:** fatura **ou** faixa na tabela atual por vida; ausência → **B-05** (zero explícito ≠ ausência).
- **Cenários:** `cenarios=[]` com vidas → **B-06**; sem opções utilizáveis → **B-05**; cenário vazio → **B-06**.
- **Nascimento futuro:** **B-05** por vida, sem `ValueError`.
- **IDs únicos** em vidas, subgrupos, opções, cenários, regimes, documentos (rejeição Pydantic).
- **Negativos:** rejeitados em componentes financeiros, conferência, tolerâncias, `iof_bps`.
- **Reajuste negativo:** **B-07** (não homologado no piloto); suporte futuro exige política explícita.
- **1ª parcela < custos:** **B-02** com mensagem clara; sem IOF sobre base recorrente negativa.
- **Proveniência atual:** `Vida.fatura_proveniencia`; B-03 estendido; saída com `fontes[]` (inclui página/trecho).

### 1.3. Correções 1.2.1 (subtotais e B-03)

- **`SubgrupoAtual.subtotal_impresso`** → reconciliado contra `subtotal_atual_vigente_centavos` (tipo fiscal e basis do subgrupo).
- **`OpcaoPlano.subtotal_impresso`** → reconciliado contra total calculado da proposta na população atribuída.
- Diferença legítima entre atual e proposta **não** gera B-02.
- **B-03:** `confirmado=false` + documento em alerta/falha bloqueia qualquer origem (fatura, tabela, subtotal, componentes, custos únicos); IA não confirmada continua bloqueando.
- **`alvo_tipo` por formato:** novo → `vida`; renovação → `subgrupo` (B-06).
- **`documento_id` inexistente** → B-05; manual sem documento continua válido.
- **`LinhagemReferencia`:** propaga `evidencia_pagina` e `evidencia_trecho`.

---

## 2. Resultado dos testes

```
86 passed
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
| **1.1.1 — Correções piloto** | 9 | PASSOU |
| **1.2 — Endurecimento** | 19 | PASSOU |
| **1.2.1 — Subtotais/B-03** | 8 | PASSOU |
| **Fixtures JSON** | 16 execuções | PASSOU |

Fixtures JSON: **15 casos parametrizados** + `test_fixtures_minimo_exigido` (presença mínima).

---

## 3. Casos de teste ETAPA 1.2.1

| Caso | Resultado |
|------|-----------|
| Subtotal atual 10.000, proposta 8.000, ambos corretos | Sem B-02 (`test_subtotal_atual_e_proposta_diferentes_sem_b02`) |
| Subtotal atual divergente | B-02 subtotal atual |
| Subtotal proposta divergente | B-02 subtotal proposta |
| Extraído não confirmado + doc alerta | B-03 |
| `alvo_tipo` incompatível (IDs coincidentes) | B-06 |
| Documento inexistente | B-05 |
| Linhagem com página/trecho | Preservados em `fontes[]` |

---

## 4. Casos de teste ETAPA 1.2

| Caso | Bloqueio / comportamento |
|------|---------------------------|
| Renovação sem fatura e sem faixa atual | B-05 |
| Fatura explicitamente zero | Calcula vigente = 0 (≠ ausência) |
| Estudo sem cenários | B-06 |
| Estudo sem opções | B-05 |
| Cenário vazio | B-06 |
| Nascimento posterior à referência | B-05, sem exceção |
| IDs duplicados (5 coleções) | Rejeição Pydantic |
| Componente/policy negativos | Rejeição Pydantic |
| Reajuste negativo | B-07 |
| 1ª parcela < custos únicos | B-02 mensagem clara |
| Fatura IA não confirmada | B-03 |
| Tabela atual IA não confirmada | B-03 |
| Linhagem na saída | `fontes[]` com refs fatura/tabela/proposta |

---

## 5. Fixtures determinísticas

Oráculo: `tests/oracle_independente.py`. Gerador: `tests/generate_fixtures.py`.

15 diretórios de fixture (lista inalterada desde 1.1.1); expected.json continua fonte commitada.

---

## 6. Matriz requisito → teste (1.2 / 1.2.1)

| Requisito | Teste(s) |
|-----------|----------|
| Baseline atual obrigatório | 1.2 `test_renovacao_sem_fatura_*`, `test_fatura_zero_*` |
| Cenários/opções obrigatórios | 1.2 `test_estudo_sem_cenarios_*`, `test_estudo_sem_opcoes_*`, `test_cenario_vazio_*` |
| Nascimento futuro | 1.2 `test_nascimento_futuro_*` |
| IDs únicos | 1.2 `test_ids_duplicados_*` |
| Valores/policy negativos | 1.2 `test_componente_*`, `test_policy_*`, `test_tolerancia_*` |
| Reajuste negativo | 1.2 `test_reajuste_negativo_*` |
| 1ª parcela < custos | 1.2 `test_primeira_parcela_menor_*`, 1.1.1 |
| Proveniência atual + linhagem | 1.2, 1.2.1 `test_linhagem_*` |
| Subtotal atual ≠ proposta na reconciliação | 1.2.1 `test_subtotal_atual_e_proposta_diferentes_sem_b02` |
| B-03 documento alerta (qualquer origem) | 1.2.1 `test_b03_extraido_*` |
| alvo_tipo por formato | 1.2.1 `test_alvo_tipo_incompativel_*` |
| documento_id inexistente | 1.2.1 `test_documento_inexistente_b05` |

---

## 7. Bloqueios B-01…B-08

| Bloqueio | Cobertura 1.2 |
|----------|---------------|
| B-02 | Reconciliação + 1ª parcela < custos |
| B-03 | Proposta + **fatura/tabela/subtotal atual** |
| B-04 | E (inalterado) |
| B-05 | Baseline, nascimento, opções, estrutura |
| B-06 | Cenários obrigatórios e atribuições |
| B-07 | Policy + reajuste negativo + estratégias piloto |
| B-08 | H, fixtures escala |

---

## 8. Decisões provisórias

| Tema | Comportamento |
|------|---------------|
| Reajuste negativo | B-07 no piloto; suporte futuro = política explícita por estudo |
| Linhagem saída | `ValorCalculado.fontes[]` — refs não recursivas, sem PII |
| Valor zero explícito | Aceito como baseline válido |

---

## 9. Limitações conhecidas

- Motor **não aprovado** para produção — checkpoint pós-endurecimento 1.2.
- Piloto: somente `por_vida_entao_soma` homologada.
- DP-07 (alerta copart) adiada.
- Integração SISCOR/PDF/parser **fora de escopo** desta entrega.

---

## 10. Componentes proibidos

Confirmado: nenhum FastAPI, React, Postgres, worker, PPTX, parser de PDF ou IA integrada.
