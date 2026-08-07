# 01 — Domínio de negócio

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento de domínio para IA sem acesso ao código. Código prevalece sobre `docs/` canônicos quando divergirem (divergências listadas em `09-ESTADO-ATUAL-E-LACUNAS.md`).

---

## O que é o produto

Sistema de Estudos Newport: comparativo financeiro de planos de saúde coletivos PME (faixa comercial homologada **1–29 vidas**, sem teto técnico no motor — `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md`; `src/newport_motor/policy.py:48-49`).

Fluxo operacional real (ETAPA 3.0+ no git): importar base SISCOR → configurar plano atual → importar/conferir cotações PDF ou manuais → mapear propostas × planos → calcular comparativo → confirmar → snapshot → aprovar → HTML.

---

## Conceitos

### Estudo de renovação vs. seguro novo

| | Renovação | Seguro novo |
|--|-----------|-------------|
| Definição | Cliente já tem plano; compara proposta com posição atual | Sem bloco “atual”; só propostas |
| Por que importa | Exige baseline vigente/reajustado, reajuste, subgrupos e fatura/tabela | Atribuição por vida; sem reajuste/baseline |
| Código | `FormatoEstudo.RENOVACAO` / `NOVO` — `src/newport_motor/types.py:23-25`; `EstudoInput.formato` — `models.py:177+`; rascunho `formato: Literal["renovacao","novo"]` — `src/newport_app/models/draft.py` |
| Maturidade | **implementado** (caminho principal) | **parcial** (motor + modelos; jornada UI otimizada para renovação; seguro novo fora da autorização de produção — `AGENTS.md`) |

### Vida / titular / dependente

| Conceito | Definição | Por que importa | Código | Maturidade |
|----------|-----------|-----------------|--------|------------|
| Vida | Beneficiário incluído ou não no estudo | Unidade de cálculo de prêmio e faixa | `Vida` — `newport_motor/models.py:121-153`; `VidaRascunho` — `draft.py:156-166` | implementado |
| Titular / dependente | Parentesco cadastral (titular, cônjuge, filho…) | SISCOR e histórico; **não** altera fórmula de prêmio no motor | `PARENTESCO_MAP` — `siscor_importer/constants.py:20-29`; `ParentescoRascunho` no draft | implementado (cadastro); motor ignora parentesco no cálculo |

### As 10 faixas etárias ANS

Definição: índices 0–9 com limites de idade completa ≤18, ≤23, ≤28, ≤33, ≤38, ≤43, ≤48, ≤53, ≤58, senão 59+ (`src/newport_motor/faixa.py:7-24`).

| Índice | Rótulo canônico (PDF) |
|--------|------------------------|
| 0 | 0 a 18 |
| 1 | 19 a 23 |
| 2 | 24 a 28 |
| 3 | 29 a 33 |
| 4 | 34 a 38 |
| 5 | 39 a 43 |
| 6 | 44 a 48 |
| 7 | 49 a 53 |
| 8 | 54 a 58 |
| 9 | 59+ |

Fonte rótulos: `src/newport_app/cotacao_pdf/faixas.py:20-32`.

Por que importa: tabela de preços da proposta e (opcionalmente) tabela atual indexam por faixa; idade é calculada na **`data_referencia_idade`** da policy (`faixa_em` — `faixa.py:27-29`; uso em `calculation.py`).

Campo: `TabelaPrecoFaixa.faixa: int` 0–9 — `models.py:39-60`.  
`Vida.faixa_override` existe (`models.py:132`) mas **não é lido** pelo cálculo — ⚠️ divergência modelo × motor.

Maturidade: **implementado**.

### Coparticipação (sem / parcial / percentual / customizada)

Definição: regime comercial do plano, tipado como `RegimeCopartTipo` (`types.py:33-37`).

Por que importa no cálculo: **não altera o valor do prêmio** no motor. Serve para **particionar seções** do cenário (`calculation.py` — `_rotulo_regime` / agrupamento por `RegimeCopart.tipo`). Mistura de regimes sob um mesmo bloco de apresentação é restrição de produto (B-06 em spec; seções disjuntas no resultado).

| Tipo | Rótulo de seção derivado |
|------|--------------------------|
| `sem` | `sem_copart` |
| `parcial` | `copart_parcial` |
| `percentual` | `com_copart` |
| `customizada` | `copart_customizada` |

Código: `RegimeCopart` — `models.py:25-29`; rascunho só `id`+`tipo` — `draft.py` (sem `percentual_bps` no draft).

Maturidade: **implementado** como classificação/seção; cálculo percentual de copart sobre procedimentos = **inexistente** no motor.

### Acomodação

Definição: enfermaria / apartamento (e variantes comerciais).

Por que importa: metadado de plano para UI e histórico; **não** entra na aritmética do motor.

Código: `OpcaoPropostaRascunho.acomodacao`, `SubgrupoAtualRascunho.acomodacao` — `draft.py:191-224`; `planos_contratados.acomodacao` — `repository/migration.py`.

Maturidade: **implementado** como campo; sem regra financeira.

### Modalidade compulsório vs. adesão

Definição: forma de adesão ao plano coletivo (default comercial PME: compulsório — DP-12 em `docs/01`).

Por que importa: alerta de negócio se adesão sem check societário (spec); motor **não** valida modalidade.

Código: campos `modalidade` no rascunho (`draft.py`); ausente em `EstudoInput` do motor.

Maturidade: **parcial** (campo no rascunho/PDF); enforcement DP-12 **não verificado** como bloqueio no motor.

### Reajuste anual

Definição: percentual anual do plano atual, em **basis points** (`reajuste_bps`). Ex.: 11,98% → 1198.

Por que importa: produz `atual_reajustado = apply_rate_bps(vigente, reajuste_bps)` (`calculation.py` / `money.py:26-29`). Ausência em renovação → **B-07**. Negativo → **B-07** (não homologado no piloto) — `validations.py:74-94`.

Código: `SubgrupoAtual.reajuste_bps` — `models.py:108`; `SubgrupoAtualRascunho.reajuste_bps` — `draft.py`.

Maturidade: **implementado**.

### Baseline vigente vs. reajustado

| Baseline | Definição | Uso |
|----------|-----------|-----|
| Vigente | Valor atual recorrente após normalização IOF/price_basis | Comparação “como está na fatura/tabela” |
| Reajustado | Vigente × (1 + reajuste) | Default de apresentação (DP-03) |

Ambos são **sempre calculados** em renovação; o apresentado vem de `EffectivePolicy.baseline_escolhido` (`policy.py:34-35`; `calculation.py:152-156`). Ausência em renovação → B-07.

`Cenario.baseline_escolhido` existe no modelo motor (`models.py:166`) mas o cálculo usa a policy — divergência.

Maturidade: **implementado**.

### Precedência fatura × tabela

Definição: quando a vida tem **valor de fatura** e **faixa na tabela atual**, quem manda.

Enum: `PrecedenciaAtualVida.TABELA_ATUAL | VALOR_FATURA` — `types.py:46-50`.  
Policy: `precedencia_atual_vida` — `policy.py:36`.  
Lógica: `_base_atual_vida` — `calculation.py:31-89`.  
Se ambos existem e precedência é `None` → **B-07** — `validations.py:139-149`.

Maturidade: **implementado**.

### Subgrupo

Definição: fatia do plano atual (renovação) agrupando vidas com mesma operadora/plano (e metadados associados).

Por que importa: atribuição de proposta em renovação é **por subgrupo** (`AlvoTipo.SUBGRUPO` — B-06 se errado); SISCOR sugere subgrupos por `(plano, operadora)` — `siscor_importer/subgrupos.py:14-30`.

Código: `SubgrupoAtual` — `models.py:102-118`; `SubgrupoAtualRascunho` — `draft.py`.

Maturidade: **implementado**.

### Carência

Definição comercial: períodos de espera para coberturas.

No código de produto: **inexistente** como entidade/cálculo. Mencionado apenas em documentos de visão/escopo futuro.

Maturidade: **inexistente** / só previsto em doc de produto antigo.

### CPT (Cobertura Parcial Temporária)

Definição comercial: restrição temporária por doença preexistente.

No código: **inexistente**.

Maturidade: **inexistente**.

### Rede credenciada

Definição: hospitais/laboratórios por perfil (Básico / Intermediário / Gerencial / Diretoria no entregável manual).

No código: **inexistente** (explicitamente fora de escopo — `docs/02`, `docs/04`).

Maturidade: **só previsto em doc** / inexistente no software.

### Reembolso / procedimentos reembolsáveis

Definição: tabelas e regras de reembolso ao beneficiário.

No código: **inexistente**. DP-07 em caderno menciona precedência de copart/reembolso da proposta sobre base — **não** há módulo de reembolso.

Maturidade: **só previsto em doc**.

### Cenário

Definição: combinação de atribuições (qual `OpcaoPlano` cada subgrupo/vida recebe) com rótulo opcional.

Por que importa: o motor calcula **um resultado por cenário**; seções internas particionadas por regime de copart.

Código: `Cenario` + `AtribuicaoPlano` — `models.py:156-174`; `CenarioRascunho` no draft; sync automático 1 plano atual → N cenários — `rascunho/cenarios_sync.py`.

Maturidade: **implementado**.

### Price basis e IOF

| Conceito | Definição | Código |
|----------|-----------|--------|
| `PriceBasis` | `inclui_iof` \| `exclui_iof` \| `desconhecido` | `types.py:12-15` |
| IOF | 2,38% = **238 bps**; só `TipoFiscal.SEGURADORA` | `policy.py:37`; `finance.py:15-16` |
| Operadora | Sem IOF | `TipoFiscal.OPERADORA` |

`desconhecido` **não entra** no cálculo (`finance.py:30-31`) e gera B-02.

Maturidade: **implementado**.

### MoneyCents

Dinheiro = inteiro em centavos. Taxas = `RateBasisPoints`. Nunca float (`money.py:1`; `types.py:8-9`).

Maturidade: **implementado**.

### Estudo / rascunho / snapshot

| Camada | Papel | Maturidade |
|--------|-------|------------|
| `RascunhoEstudo` | Estado editável JSON no SQLite | implementado |
| `EstudoInput` | Entrada tipada do motor (pós-compilação) | implementado |
| `SnapshotCalculo` | Congelamento canônico + hash | implementado |
| HTML | Entregável pós-aprovação | implementado |
| PPTX | Entregável histórico manual | **inexistente** no sistema (`AGENTS.md`) |

---

## ⚠️ NÃO VERIFICADO

1. Se a UI de modalidade adesão dispara de fato o alerta DP-12 (campo existe; handler não rastreado ponta a ponta neste handoff).
2. Semântica comercial exata de “copart parcial = só terapias” (afirmada em `docs/01` DP-06; motor não modela escopo de procedimentos no draft).
3. Lista oficial ANS de nomes de faixa vs. rótulos `ROTULOS_FAIXA` — alinhamento regulatório não auditado além do código.
