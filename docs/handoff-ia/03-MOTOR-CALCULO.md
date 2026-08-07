# 03 — Motor de cálculo

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento do motor puro (`newport_motor`). Código prevalece.

---

## Assinatura de entrada

```29:33:src/newport_motor/engine.py
def calcular(estudo: EstudoInput, policy: EffectivePolicy) -> MotorResult:
    """
    Função pura: (dados_tipados, effective_policy) -> resultado + validações.
    B-01 (aprovação) é responsabilidade da camada de aplicação.
    """
```

---

## Sequência exata em `calcular`

Ordem em `engine.py:34-120`:

| # | Passo | Função / ação | Linhas |
|---|-------|---------------|--------|
| 1 | Escopo vidas | `validar_escopo_vidas` → B-08 / H-01 | `36` |
| 2 | Policy obrigatória | `validar_b07_politica_obrigatoria` | `37` |
| 3 | Estrutura | `validar_entrada_estrutural` (B-02/B-05/B-06 + 1ª parcela) | `38` |
| 4 | Confirmação | `validar_b03_valores_nao_confirmados` | `39` |
| 5 | Atribuições | `validar_b06_atribuicoes` | `40` |
| 6 | Opções | `validar_b05_opcoes_obrigatorias` | `41` |
| 7 | Nascimento × referência | `validar_b05_nascimento_referencia` | `42` |
| 8 | Baseline renovação | `validar_b05_baseline_atual_renovacao` | `43` |
| 9 | Early exit | se há `BLOQUEANTE` → `_resultado_parcial` (cenários `[]`) | `45-46` |
| 10 | Idade×valor | `validar_b04_idade_valor` | `48-50` |
| 11 | Dados opções usadas | coleta `opcoes_usadas` + `validar_b05_dados_obrigatorios` | `52-57` |
| 12 | Early exit | novamente se bloqueante | `59-60` |
| 13 | Cálculo | por cenário: `calcular_cenario` | `62-66` |
| 14 | Reconciliação B-02 | `agregar_por_opcao_no_cenario` + `reconciliar_opcao_cenario` | `68-97` |
| 15 | Pós-check B-06 | vidas incluídas sem cenários calculados | `99-112` |
| 16 | Retorno | `MotorResult` com `bloqueios_abertos` ordenados | `113-120` |

---

## MoneyCents, half-up, float proibido

| Regra | Código |
|-------|--------|
| Dinheiro = `MoneyCents = NewType(..., int)` | `types.py:8` |
| Taxas = `RateBasisPoints` (int) | `types.py:9` |
| Módulo `money.py`: “sem float” | `money.py:1` |
| Half-up: `(numerador + denom//2) // denom` (simétrico p/ negativo) | `money.py:12-18` |
| IOF/taxa: `valor * (10000 + bps)` half-up ÷ 10000 | `money.py:26-29` |
| `finance.py` só opera `int` / `MoneyCents` | `finance.py` todo |
| `rounding.py` delega a `finance` | `rounding.py:9-24` |

Float **não** aparece na aritmética monetária do motor. Qualquer conversão percentual usa bps inteiros.

Estratégia piloto homologada: só `por_vida_entao_soma` (`validations.py:101-115`); outras → B-07.

IOF só se `tipo_fiscal == SEGURADORA` (`finance.py:15-16`). `exclui_iof` → aplica IOF; `inclui_iof` → não reaplica (`finance.py:76-82`).

---

## Faixa etária e `data_referencia_idade`

```7:29:src/newport_motor/faixa.py
# Faixas ANS padrão (10 faixas: 0–9)
_FAIXA_LIMITES = (18, 23, 28, 33, 38, 43, 48, 53, 58)
...
def faixa_em(nascimento: date, referencia: date) -> tuple[int, int]:
    idade = idade_completa_em(nascimento, referencia)
    return idade, faixa_de_idade(idade)
```

| Índice | Idade completa ≤ |
|--------|------------------|
| 0–8 | 18, 23, 28, 33, 38, 43, 48, 53, 58 |
| 9 | restante (59+) |

Uso no cálculo: `faixa_em(vida.nascimento, policy.data_referencia_idade)` (`calculation.py:234`, `267`).  
`Vida.faixa_override` existe (`models.py:132`) e **não é lido** por `_calcular_subgrupo_*`.

Sem `data_referencia_idade` → B-07 (`validations.py:54-61`).

---

## O que o motor **não** decide

| Tema | Quem decide | Evidência |
|------|-------------|-----------|
| Resolução de policy (baseline, data, precedência, IOF bps efetivo do set) | App / compiler → `EffectivePolicy` | `policy.py:30-31` |
| B-01 (aprovação / entrega) | App (`ApresentacaoService`, snapshot) | `engine.py:32`; `apresentacao.py:45-51` |
| Formatação / PPTX / HTML | Presentation layer | `presentation.py:1` |
| Parentesco / nome comercial | Cadastro; motor ignora no prêmio | só `Vida` tipada sem parentesco |
| Copart sobre procedimentos | Não calcula; só particiona seção por `RegimeCopart.tipo` | `calculation.py:136-143`, `174-185` |
| Origem do rascunho / confirmação UI | Draft + compiler | mapper |
| Qual cenário “vender” | Usuário / seleção apresentação | fora do motor |

---

## Bloqueios B-01…B-08 e H-01

### B-01 — APP, não motor

| Item | Detalhe |
|------|---------|
| Trigger | Gerar apresentação sem snapshot `aprovado` / sem aprovação válida |
| Mensagem | `"Somente snapshots aprovados podem gerar apresentação."` / `"Aprovação inválida ou ausente."` |
| Código | `apresentacao.py:45-51` |
| Motor | Explicitamente fora (`engine.py:32`; `validations.py:1`) |

### B-02 — reconciliação / basis

| Trigger | Padrão de mensagem | file:line |
|---------|-------------------|-----------|
| `price_basis` desconhecido em componente | `"{comp} com price_basis desconhecido (opção {id}); declaração obrigatória (DP-02)."` | `reconciliation.py:55-60`; também `validations.py:372-376`, `393-399` |
| Fatura basis desconhecido | `"fatura_price_basis desconhecido (vida {id}, subgrupo {id})."` | `validations.py:325-331` |
| Conferência diverge | `"Divergência por vida {id}: calculado {c}c vs conferência {e}c (diff {d}c)."` | `reconciliation.py:114-117` |
| Subtotal atual diverge | `"Subtotal atual subgrupo {id} diverge ({calc}c vs {esp}c, diff {d}c)."` | `reconciliation.py:157-159` |
| Subtotal proposta diverge | `"Subtotal da proposta diverge do calculado agregado (...)."` | `reconciliation.py:192-195` |
| Prêmio+IOF vs recorrente | `"Prêmio+IOF ({}c) diverge do total recorrente impresso (...)."` | `reconciliation.py:228-230` |
| Total recorrente vs agregado | `"Total recorrente impresso diverge do calculado agregado (...)."` | `reconciliation.py:251-253` |
| 1ª parcela < custos | `"Primeira parcela ({}c) menor que a soma dos custos únicos ({}c) (opção {id})."` | `validations.py:262-266`; `reconciliation.py:284-288` |
| 1ª parcela ≠ recorrente+custos | `"Primeira parcela equivalente ({}c) ≠ recorrente + custos únicos (...)."` | `reconciliation.py:333-335` |

### B-03 — valores não confirmados

| Trigger | Mensagem | file:line |
|---------|----------|-----------|
| Origem IA sem `confirmado` | `"{rotulo} com origem IA não confirmada."` | `validations.py:478-481` |
| Não confirmado + doc em alerta/falha | `"{rotulo} não confirmado com documento em estado de alerta/falha."` | `validations.py:487-492` |

### B-04 — idade × valor (fatura vs tabela)

| Trigger | Mensagem | file:line |
|---------|----------|-----------|
| Diff > tolerância por vida | `"Vida {id}: fatura ({}c recorrente) diverge da tabela atual faixa {f} ({}c, diff {}c)."` | `validations.py:751-756` |
| Sem faixa na tabela (alerta) | `"Vida {id}: sem faixa {f} na tabela atual comparável."` | `validations.py:718-721` |

### B-05 — dados / estrutura

| Trigger | Mensagem (padrão) | file:line |
|---------|-------------------|-----------|
| Nascimento > referência | `"Vida {id}: nascimento (...) posterior à data de referência (...)."` | `validations.py:164-171` |
| Renovação sem subgrupo | `"Vida {id} em renovação sem subgrupo_atual_id; baseline atual obrigatório."` | `validations.py:191-196` |
| Sem fonte baseline | `"Vida {id}: sem fonte válida para baseline atual (fatura ou tabela atual faixa {f})."` | `validations.py:211-215` |
| Sem opções | `"Estudo sem opção de proposta utilizável."` | `validations.py:239-242` |
| Opção inexistente | `"Opção {id} inexistente (atribuição {id})."` | `validations.py:285-288` |
| Faixa fora 0–9 / duplicada / negativa | mensagens com `faixa` e alvo | `validations.py:341-367` |
| Documento inexistente | `"Documento '{id}' inexistente ({alvo})."` | `validations.py:414-417` |
| Regime indefinido | `"Regime de copart {id} indefinido (DP-06)."` | `validations.py:601-604` |
| Tabela incompleta | `"Tabela incompleta: faixa {f} ausente (opção {id})."` | `validations.py:612-615` |

### B-06 — cenários / atribuições

| Trigger | Mensagem | file:line |
|---------|----------|-----------|
| Vidas sem cenários | `"Estudo com vidas incluídas sem cenários definidos."` | `validations.py:628-631` |
| Novo com alvo ≠ vida | `"Atribuição {id}: seguro novo exige alvo_tipo=vida (...)."` | `validations.py:642-648` |
| Renovação com alvo ≠ subgrupo | `"Atribuição {id}: renovação exige alvo_tipo=subgrupo (...)."` | `validations.py:654-660` |
| Alvo sem atribuição | `"Alvo {id} sem atribuição no cenário {id}."` | `validations.py:678-681` |
| Subgrupo/vida inexistente | mensagens estruturais | `validations.py:294-307` |
| Pós-cálculo sem cenários | `"Estudo concluído sem cenários calculados."` | `engine.py:106-110` |

### B-07 — política

| Trigger | Mensagem | file:line |
|---------|----------|-----------|
| Sem data referência | `"Data de referência de idade obrigatória (DP-01)."` | `validations.py:57-60` |
| Renovação sem baseline | `"Baseline de comparação obrigatório em renovação (DP-03)."` | `validations.py:67-70` |
| Sem reajuste | `"Reajuste não definido para subgrupo {id} (DP-04)."` | `validations.py:77-80` |
| Reajuste negativo | `"Reajuste negativo ({} bps) no subgrupo {id} não homologado no piloto; ..."` | `validations.py:86-93` |
| Precedência obrigatória | `"Vida {id}: tabela atual e fatura coexistem; precedencia_atual_vida obrigatória (DP-02)."` | `validations.py:141-147` |
| Estratégia não piloto | `"Estratégia de arredondamento '{x}' não homologada no piloto; use 'por_vida_entao_soma' (DP-11)."` | `validations.py:107-113` |

### B-08 / H-01

| Código | Trigger | Mensagem | file:line |
|--------|---------|----------|-----------|
| B-08 | 0 vidas incluídas | `"Estudo sem vidas incluídas."` | `validations.py:27-31` |
| H-01 | `count > max_vidas_homologadas` (alerta) | `"Vidas incluídas ({n}) excedem a faixa homologada ({max}); revisão adicional necessária antes da aprovação."` | `validations.py:38-44` |

---

## Passo a passo do cálculo (renovação)

Por vida no subgrupo (`calculation.py:220-256`):

1. `(idade, faixa) = faixa_em(nascimento, data_referencia_idade)`
2. Base atual via tabela e/ou fatura + `precedencia_atual_vida` (`_base_atual_vida`)
3. `vigente` = normalizar para recorrente (IOF se seguradora + `exclui_iof`)
4. `reajustado = apply_rate_bps(vigente, reajuste_bps)`
5. `proposta` = valor da faixa na opção, mesma normalização IOF
6. Baseline apresentado = `reajustado` ou `vigente` conforme policy
7. `diff_mes = proposta - atual_baseline`; `diff_ano = diff_mes * 12`
8. Soma vidas → subgrupo → seção (por regime) → cenário

---

## Exemplo numérico ficcional (3 vidas)

**Premissas (ficção alinhada ao código):**

| Parâmetro | Valor |
|-----------|-------|
| Formato | renovação |
| Subgrupos / cenários / opções | 1 / 1 / 1 |
| `tipo_fiscal` | `seguradora` |
| Tabelas (`atual` e proposta) | `price_basis=exclui_iof` |
| `iof_bps` | 238 |
| `reajuste_bps` | 1000 (10%) |
| `baseline_escolhido` | `reajustado` |
| `estrategia_arredondamento` | `por_vida_entao_soma` |
| `data_referencia_idade` | `2026-07-01` |
| Precedência | só tabela atual (sem fatura) |

**Vidas e faixas**

| Vida | Nascimento | Idade em 2026-07-01 | Faixa |
|------|------------|---------------------|-------|
| A | 1990-01-15 | 36 | 4 |
| B | 1985-06-01 | 41 | 5 |
| C | 2010-03-01 | 16 | 0 |

**Tabela atual / proposta (centavos, exclui IOF)** — só faixas usadas:

| Faixa | Atual | Proposta |
|-------|-------|----------|
| 0 | 20_000 | 22_000 |
| 4 | 50_000 | 55_000 |
| 5 | 60_000 | 65_000 |

**Half-up IOF** (`apply_rate_bps`):  
`recorrente = (valor × 10238 + 5000) // 10000`  
**Half-up reajuste 1000 bps:**  
`reajustado = (vigente × 11000 + 5000) // 10000`

### Vida A (faixa 4)

| Etapa | Inteiros |
|-------|----------|
| Vigente | `(50000×10238 + 5000)//10000 = 511905000//10000 = **51190**` |
| Reajustado | `(51190×11000 + 5000)//10000 = 563095000//10000 = **56309**` |
| Proposta | `(55000×10238 + 5000)//10000 = 563095000//10000 = **56309**` |
| Diff mês (baseline reajustado) | `56309 − 56309 = **0**` |

### Vida B (faixa 5)

| Etapa | Inteiros |
|-------|----------|
| Vigente | `(60000×10238 + 5000)//10000 = **61428**` |
| Reajustado | `(61428×11000 + 5000)//10000 = **67571**` |
| Proposta | `(65000×10238 + 5000)//10000 = **66547**` |
| Diff mês | `66547 − 67571 = **−1024**` |

### Vida C (faixa 0)

| Etapa | Inteiros |
|-------|----------|
| Vigente | `(20000×10238 + 5000)//10000 = **20476**` |
| Reajustado | `(20476×11000 + 5000)//10000 = **22524**` |
| Proposta | `(22000×10238 + 5000)//10000 = **22524**` |
| Diff mês | `22524 − 22524 = **0**` |

### Totais do cenário

| Agregado | Centavos |
|----------|----------|
| `total_proposta` | `56309 + 66547 + 22524 = **145380**` |
| `total_atual_baseline` (reajustado) | `56309 + 67571 + 22524 = **146404**` |
| `diff_mes` | `145380 − 146404 = **−1024**` |
| `diff_ano` | `−1024 × 12 = **−12288**` |

---

## Classificações de maturidade

### Motor / produto (domínio)

| Área | Classificação | Evidência |
|------|---------------|-----------|
| Cálculo renovação + IOF + reajuste + seções | **implementado** | `calculation.py`, `finance.py` |
| Seguro novo no motor | **parcial** (caminho existe; jornada UI/piloto = renovação) | `calculation.py:186-205` |
| Estratégias `soma_entao_aplica` / `no_total` | código existe; **não homologadas** no piloto (B-07) | `validations.py:101-115` |
| Copart percentual sobre atos | **inexistente** no cálculo | só rótulo de seção |
| B-01 no motor | **inexistente** (app) | `engine.py:32` |
| Motor em produção | **não aprovado** (piloto) | `RELATORIO-IMPLEMENTACAO.md` §10 |

### Extração PDF (`avaliar_maturidade`)

Flags booleanas em `cotacao_pdf/maturidade.py:24-60`:

| Flag | Significado |
|------|-------------|
| `template_reconhecido` | template_id + estado ≠ `nao_reconhecido`/`erro` |
| `tabela_extraida` | opções ativas sem alerta de tabela ausente |
| `valores_reconciliados` | `reconciliacao.ok` em todas ativas |
| `proposta_pronta_aplicacao` | opções-alvo sem pendências |
| `extracao_financeira_homologada` | **sempre `False`** (`maturidade.py:58`) |
| `exige_selecao_consciente` | Porto ou >3 opções ativas |

---

## ⚠️ NÃO VERIFICADO

1. Cobertura de testes para cada variante de mensagem B-02 (há muitas; inventário acima é do código-fonte, não da suíte).
2. Comportamento de `quantidade_cotada` vs. vidas reais na reconciliação agregada (flag conhecido em relatório).
3. Se `faixa_override` será ativado em versão futura — hoje morto no cálculo.
4. Equivalência bit-a-bit do exemplo ficcional com um fixture oficial do repo (exemplo montado à mão a partir das fórmulas; não há fixture idêntico neste handoff).
5. Interação H-01 × B-01 na UI de aprovação (H-01 é alerta no motor; confirmação extra na app não auditada ponta a ponta aqui).
