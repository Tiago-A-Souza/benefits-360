# Caracterização ETAPA 2.0 — Conclusões estruturais (anonimizadas)

> Resultado da inspeção **somente leitura** de documentos reais no corpus privado local.  
> Nenhum dado pessoal, valor monetário real ou identificador de cliente neste arquivo.  
> Inventário detalhado e caso dourado operacional: `.private/etapa-2.0/` (fora do Git).  
> UTF-8 · 2026-07-22.

---

## 1. Corpus inspecionado (metadados)

| Artefato | Tipo | Observação estrutural |
|----------|------|------------------------|
| Planilha SISCOR (1 arquivo) | XLSX, 1 aba | 50 colunas × 41 linhas de dados + cabeçalho |
| Cotação operadora A | PDF, 4 páginas | Operadora **sem IOF**; tabela agregada por faixa etária |
| Cotação operadora B | PDF, 2 páginas | Seguradora; 2 perfis/planos; 4 vidas no documento |
| Cotação operadora C | PDF, 15 páginas | Seguradora; layout extenso; tabelas de faixa em páginas centrais |
| Template apresentação | PPTX, 25 slides | Referência visual; comparativo financeiro no slide 4 |

Cotações adicionais disponíveis no corpus (não inspecionadas em profundidade nesta rodada): operadora C estendida, operadora D, operadora E — reservadas para ETAPA 3+ ou refinamento.

---

## 2. Dicionário de campos

### 2.1 Planilha SISCOR — colunas observadas (50)

#### Whitelist proposta (Patch P9 + necessidade operacional)

| Coluna SISCOR | Uso no sistema | Observação |
|---------------|----------------|------------|
| SEGURADO | `Vida.nome` | Necessário ao slide; dado pessoal minimizado |
| PARENTESCO | Agrupamento / titularidade | Normalizar enum (TITULAR, CÔNJUGE, FILHO(A), COMPANHEIRO, …) |
| DATA DE NASCIMENTO | `Vida.nascimento` | Obrigatório; nunca inferir |
| SEXO | Opcional | Presente em 100% das linhas inspecionadas |
| PLANO | `SubgrupoAtual.plano_nome` / agrupamento | Agrupa subgrupos atuais |
| SEGURADORA | `SubgrupoAtual.operadora` | Constante no arquivo inspecionado |
| VALOR | `Vida.valor_fatura_centavos` | Decimal na planilha → centavos inteiros |
| STATUS SEGURADO | Filtro inclusão | Todas as linhas: status ativo |

#### Descarte obrigatório na ingestão (nunca persistir)

CLIENTE, CNPJ CLIENTE, UNIDADE, CNPJ UNIDADE, CONTRATO, STATUS CONTRATO, RAMO, TITULAR, CPF TITULAR, NOME DA MAE, CPF, DOC PIS, carteira de trabalho (número/série), RG (número, datas, órgão, UF), CARTAO SUS, DATA DE INICIO, ESTADO CIVIL, TIPO DE VIDA, REGISTRO EMPREGADO, CARGO, DEPARTAMENTO, CENTRO DE CUSTO, NIVEL DE CARGO, COD CONTABIL, SALARIO, DATA DE ADMISSAO, MATRICULA, NUM SEGURO, TEL FIXO, TEL CELULAR, EMAIL, CEP, ENDERECO, UF, CIDADE, NUMERO, COMPLEMENTO, BAIRRO.

#### Campos SISCOR ausentes para o motor

| Necessidade motor | Situação | Resolução operacional |
|-------------------|----------|------------------------|
| `data_referencia_idade` | Ausente | Escolha do estudo na UI |
| `fatura_price_basis` | Ausente | Pergunta: “Este valor já inclui IOF?” por subgrupo |
| `reajuste_bps` | Ausente | Escolha do estudo ou entrada manual |
| `tabela_atual` por faixa | Ausente | Entrada manual ou import separado (fatura) |
| Regime de coparticipação | Ausente | Escolha/declaração manual |
| IDs estáveis | Ausente | Gerados na importação |

### 2.2 Cotação operadora A (sem IOF, 4 páginas)

| Campo documento | Destino motor | Notas |
|-----------------|---------------|-------|
| Distribuição faixas (0–18 … 59+) | `TabelaPrecoFaixa` + `quantidade_cotada` | Tabela agregada, não por vida |
| Valor por vida (por faixa) | `TabelaPrecoFaixa.valor_centavos` | `price_basis = exclui_iof` |
| Subtotal por faixa | Conferência / reconciliação | |
| Total de vidas (linha plano) | Conferência qtd | |
| TOTAL GERAL | `OpcaoPlano.subtotal_impresso` ou `total_recorrente` | |
| Plano dental separado | Fora do escopo financeiro piloto | Ignorar ou seção futura |
| Regime copart (título) | `RegimeCopart` | Identificar no cabeçalho |

**Ausente:** prêmio/IOF decompostos (operadora). **Ausente:** valores por vida individual.

### 2.3 Cotação operadora B (seguradora, 2 páginas, 4 vidas)

| Campo documento | Destino motor | Notas |
|-----------------|---------------|-------|
| Perfil 1 / Perfil 2 | 2 subgrupos ou 2 opções | Caso **não simples** se usado integralmente |
| Faixa + Qtd + valores saúde/dental | `TabelaPrecoFaixa` + quantidades | Colunas dental paralelas |
| Prêmio Saúde | `OpcaoPlano.premio_saude` | |
| Prêmio Dental | Fora escopo ou custo único | Decisão pendente |
| Total Geral | `subtotal_impresso` / `total_recorrente` | |
| Total 1ª Parcela | `total_primeira_parcela` | |
| IOF explícito | **Não encontrado** no texto extraído | Pergunta UI ou cálculo derivado |

### 2.4 Cotação operadora C (seguradora, 15 páginas)

| Campo documento | Destino motor | Notas |
|-----------------|---------------|-------|
| Subtotal + Taxa inscrição + IOF (pág. 2) | Componentes financeiros | Layout compacto no resumo |
| Tabelas gerais com/sem copart (págs. 13–14) | `TabelaPrecoFaixa` | Múltiplas variantes — escolha manual |
| “Valores em Reais e sem IOF” | `price_basis = exclui_iof` | Declaração explícita |
| Faixas etárias | Padrão 0–18 … 59+ | Faixa 10 = índice 9 no motor |

**Complexidade:** alta para entrada manual na primeira homologação (muitas páginas condicionais).

---

## 3. Matriz origem → extração → confirmação → uso

Legenda confirmação: **L** = lote possível · **I** = individual · **E** = escolha do estudo · **O** = opcional

| Campo / conceito | Origem | Extração ETAPA 2 | Confirmação | Uso |
|------------------|--------|------------------|-------------|-----|
| Nome beneficiário | SISCOR | Automática (whitelist) | L + exceções I | Slide, identificação na UI |
| Data nascimento | SISCOR | Automática | L (validar formato) | Idade/faixa |
| Parentesco | SISCOR | Automática | L | Agrupamento |
| Plano atual | SISCOR | Automática | L por plano distinto | Subgrupo |
| Valor fatura vida | SISCOR | Automática → centavos | L + outliers I | Atual por vida |
| Inclusão vida | SISCOR + regra status | Sugestão | L “confirmar todas ativas” | `Vida.incluida` |
| Operadora atual | SISCOR | Automática | L | Subgrupo |
| Valor inclui IOF? | — | Manual / pergunta UI | E por subgrupo | `fatura_price_basis` |
| Data referência idade | — | Manual | E | `EffectivePolicy` |
| Baseline (vigente/reajustado) | — | Manual | E | Cenário |
| Reajuste % | — | Manual | E | `SubgrupoAtual.reajuste_bps` |
| Precedência fatura vs tabela | — | Manual | E | `EffectivePolicy` |
| Tabela atual por faixa | Fatura / manual | Manual | I ou L por subgrupo | `SubgrupoAtual.tabela_atual` |
| Nome plano proposta | Cotação PDF | Manual (sem parser) | I | `OpcaoPlano` |
| Tabela faixas proposta | Cotação PDF | Manual | I | `OpcaoPlano.tabela` |
| Qtd por faixa | Cotação PDF | Manual | L dentro do plano | `quantidade_cotada` |
| Prêmio / IOF / Total | Cotação PDF | Manual | I | Componentes financeiros |
| “Este valor já inclui IOF?” | — | Pergunta UI | I por componente | `price_basis` |
| Regime coparticipação | Cotação / manual | Manual | I | `RegimeCopart` |
| Atribuição plano → alvo | — | Manual | I ou L por subgrupo | `AtribuicaoPlano` |
| Confirmação origem dado | — | UI | I | `ProvenienciaCampo.confirmado` |

### Confirmação SISCOR em lote (requisito aprovado)

1. Importar → exibir **N vidas sugeridas** com resumo por plano e faixa etária calculada.
2. Ação **“Confirmar todas coerentes”** marca lote com proveniência `extraido` + `confirmado=true`.
3. Destaque automático de **exceções**: valor zerado, nascimento inválido, plano não mapeado, idade fora da faixa esperada (alerta, não correção automática).
4. Exceções abrem edição **individual** com trilha de alteração.

---

## 4. Mapa para `EstudoInput` e `EffectivePolicy`

### 4.1 SISCOR → rascunho → `EstudoInput`

```text
Linhas SISCOR (whitelist)
  → agrupar por PLANO → SubgrupoAtual (id gerado, operadora, plano_nome, tipo_fiscal)
  → cada linha → Vida (id gerado, nome, nascimento, valor_fatura_centavos, subgrupo_atual_id)
  → formato = renovacao
  → documentos[] vazio na importação pura
```

### 4.2 Cotação manual → `OpcaoPlano`

```text
Formulário proposta
  → OpcaoPlano (operadora, plano_nome, tipo_fiscal, regime_copart_id)
  → tabela[]: faixa 0..9, valor_centavos, quantidade_cotada, price_basis, proveniencia manual
  → premio_saude, iof, total_recorrente, total_primeira_parcela, subtotal_impresso (conforme layout)
  → documento_id opcional (referência metadados, não PDF no Git)
```

### 4.3 Escolhas UI → `EffectivePolicy`

| Pergunta na UI (linguagem usuário) | Campo `EffectivePolicy` |
|-----------------------------------|-------------------------|
| “Qual data usar para calcular idades?” | `data_referencia_idade` |
| “Qual valor considerar como atual?” | `baseline_escolhido` |
| “Em caso de diferença fatura/tabela, qual prevalece?” | `precedencia_atual_vida` |
| (Auditoria) tolerâncias e arredondamento | `tolerancias`, `estrategia_arredondamento` |
| (Auditoria) versão política | `policy_set_versao` |

### 4.4 Cenário mínimo (renovação simples)

```text
1 RegimeCopart
1 SubgrupoAtual (após filtro plano único)
1 OpcaoPlano
1 Cenario com AtribuicaoPlano(alvo_tipo=subgrupo, alvo_id=subgrupo)
```

---

## 5. Incompatibilidades documento ↔ motor

| # | Incompatibilidade | Impacto | Mitigação ETAPA 2 |
|---|-------------------|---------|-------------------|
| I-01 | Planilha inspecionada: **41 vidas** > limite piloto **29** (B-08) | Bloqueio motor | Caso dourado: subconjunto ≤29 confirmado manualmente |
| I-02 | Planilha: **2 planos** distintos (36 + 5 vidas) | Caso simples exige 1 plano | Homologação filtra **1 plano** ou aceita caso complexo como 2.5 |
| I-03 | SISCOR: só valor por vida; **sem tabela por faixa** | B-04 limitado; reconciliação parcial | Entrada manual tabela atual ou precedência fatura |
| I-04 | SISCOR: sem `price_basis` | B-07 / pergunta UI | “Este valor já inclui IOF?” por subgrupo |
| I-05 | Cotação A: **5 vidas** vs SISCOR **41** | Proposta ≠ universo SISCOR | Homologação: proposta manual **independente** ou subconjunto alinhado |
| I-06 | Cotação B: **2 perfis** + dental | Não é 1 proposta simples | Usar só perfil saúde ou marcar como caso complexo futuro |
| I-07 | Cotação B: **IOF não explícito** no PDF | Componente IOF ambíguo | Pergunta UI; conferência manual |
| I-08 | Faixas PDF usam rótulos “0–18”, “19–23”… | Mapear para índices 0–9 | Tabela de conversão no compilador |
| I-09 | Operadora A: **tipo_fiscal = operadora** | Sem IOF no motor | Válido — não excluir operadora |
| I-10 | Dental / odonto nas cotações | Fora escopo comparativo saúde | Ignorar na ETAPA 2 ou linha informativa |
| I-11 | Motor congelado: `soma_entao_aplica` / `no_total` → B-07 | Não configurável | Policy default `por_vida_entao_soma` |

---

## 6. Caso dourado privado (referência)

Definição operacional em `.private/etapa-2.0/caso-dourado-privado.md`.

**Resumo anonimizado:**

| Atributo | Valor |
|----------|-------|
| Tipo | Renovação |
| Fonte cadastral | Planilha SISCOR inspecionada |
| Operadora posição atual | Operadora sem IOF (mesma do SISCOR) |
| Planos no SISCOR | 2 (homologação usa **1 plano**, subconjunto ≤29 vidas) |
| Proposta | Entrada manual baseada em cotação operadora A (mesma família operadora) |
| Regime copart | Sem coparticipação (conforme título da cotação A) |
| Escopo excluído | Dental, seguro vida, rede |

---

## 7. Wireframes — linguagem não técnica

Referência visual: template PPTX slide “Comparativo financeiro” (estrutura: título, cenário, tabelas lado a lado).

### Tela 1 — Novo estudo
```
┌─ Novo estudo de renovação ─────────────────────────────┐
│ Quantidade de vidas: até 29                            │
│ [ Enviar planilha de beneficiários ]                   │
│ Pré-visualização: 41 registros encontrados → 29 usados │
│ Planos detectados: 2  (selecione 1 para este estudo)   │
└────────────────────────────────────────────────────────┘
```

### Tela 2 — Revisar beneficiários (lote)
```
┌─ Beneficiários importados ──────────────────────────────┐
│ Plano A — 36 pessoas   [ Confirmar todas ]  [ Revisar ] │
│ ⚠ 3 registros com alerta (expandir)                      │
│ ☐ Incluir no estudo (marca em lote por plano)          │
└─────────────────────────────────────────────────────────┘
```

### Tela 3 — Situação atual
```
┌─ Plano atual ───────────────────────────────────────────┐
│ Operadora: [auto]                                       │
│ Este valor mensal já inclui IOF?  ( ) Sim  (•) Não      │
│ Qual data usar para calcular idades? [____]             │
│ Reajuste esperado (%): [____]                           │
│ Valor de referência: ( ) Contrato vigente  ( ) Reajustado│
└─────────────────────────────────────────────────────────┘
```

### Tela 4 — Nova proposta (manual)
```
┌─ Digitar proposta ──────────────────────────────────────┐
│ Operadora: [________]  Plano: [________]                  │
│ Faixa etária │ Qtd │ Valor unitário │ Inclui IOF? │ ✓   │
│ Confirme a origem deste dado: [manual — analista]        │
│ Total informado no documento: R$ [________]              │
└─────────────────────────────────────────────────────────┘
```

### Tela 5 — Resultado (checkpoint)
```
┌─ Comparativo ───────────────────────────────────────────┐
│           │ Atual/mês │ Proposta/mês │ Diferença           │
│ Mensal    │           │              │                     │
│ Anual     │           │              │                     │
│ ⚠ Pendências: 0                                         │
│ [ Recalcular ]  [ Preparar versão para aprovação ]        │
└─────────────────────────────────────────────────────────┘
```

### Tela 6 — Revisor
```
┌─ Versão para aprovação ─────────────────────────────────┐
│ (mesmos números da tela anterior — somente leitura)      │
│ Identificador desta versão: a1b2…                         │
│ Marca: RASCUNHO INTERNO                                   │
│ [ Aprovar esta versão ]  [ Solicitar correção ]           │
└─────────────────────────────────────────────────────────┘
```

### Tela 7 — Apresentação
```
┌─ Gerar apresentação ──────────────────────────────────────┐
│ Versão aprovada: a1b2…                                    │
│ [ Gerar PowerPoint ]                                      │
│ O arquivo usará exatamente os valores aprovados.          │
└─────────────────────────────────────────────────────────┘
```

**Área de auditoria (colapsada):** códigos B-02…B-08, `price_basis`, hash, versão motor, versão compilador.

---

## 8. Perguntas pendentes para Wesley

| ID | Pergunta | Homologação provisória (responsável projeto) |
|----|----------|-----------------------------------------------|
| W-01 | Caso dourado: subconjunto 29 vidas **ou** aguardar planilha menor? | Subconjunto do plano majoritário |
| W-02 | Homologação com **1 plano** only, ignorando 5 vidas do plano secundário? | Sim, para caso simples |
| W-03 | Proposta homologada: mesma operadora (renovação pura) **ou** troca de operadora? | Mesma operadora na 2.0 |
| W-04 | Dental nas cotações: ignorar totalmente na ETAPA 2? | Ignorar |
| W-05 | IOF implícito cotação B: calcular 2,38% ou exigir digitação explícita? | Digitação explícita + pergunta UI |
| W-06 | Default `data_referencia_idade`: último dia mês vigência **ou** sempre manual? | Sempre manual (B-07) |
| W-07 | Autoaprovação no piloto (DP-14)? | Não — revisor distinto |
| W-08 | Template PPTX: master M3CASE **ou** provisório mínimo? | Provisório mínimo financeiro |
| W-09 | Retenção dados vidas pós-entrega (P9)? | 90 dias (default patch) |
| W-10 | Operadora primeira homologação — validar scorecard §9? | Ver recomendação §9 |

---

## 9. Recomendação — primeira operadora (entrada manual)

Scorecard com evidência dos documentos reais inspecionados (1–5; **não** baseado em fixtures de teste):

| Critério | Op. A (sem IOF) | Op. B (seguradora, 4 vid.) | Op. C (seguradora, 15 pág.) |
|----------|-----------------|----------------------------|-----------------------------|
| Frequência na operação (este corpus) | **5** — SISCOR 100% mesma operadora | 2 — amostra pequena | 2 — amostra desalinhada ao SISCOR |
| Qualidade cotação p/ manual | **4** — tabela faixa clara | 3 — 2 perfis, dental | 2 — extenso |
| Estabilidade layout | 4 | 4 | 3 |
| Facilidade entrada/conferência | **5** — sem IOF, totais claros | 3 — IOF ambíguo | 2 |
| Totais + faixa | **5** | 4 | 4 |
| Complexidade caso | 3 — dental presente | 2 — multi-perfil | 1 — muito complexo |
| Estudo completo homologação | **5** — SISCOR + cotação alinhados | 2 — vidas diferentes | 2 |
| **Total** | **31** | 20 | 18 |

### Recomendação

**Operadora A (sem IOF, mesma do SISCOR inspecionado)** como caso de homologação da **entrada manual**.

**Justificativa:** única combinação onde posição cadastral real e cotação disponível pertencem à mesma operadora; tabela por faixa etária explícita; entrada manual sem decomposição IOF; menor atrito para primeira fatia. Não exclui operadoras com IOF em etapa posterior.

**Plano B:** operadora B, se Newport indicar que renovações com troca para essa seguradora são mais frequentes que renovações na operadora do SISCOR disponível.

---

## 10. Recomendação — formato do walking skeleton (2.1)

| Decisão | Recomendação |
|---------|--------------|
| Interface homologação | **SPA React** servida pelo FastAPI (ou Vite dev proxy) |
| Backend | **FastAPI** enxuto — rotas REST, sem auth na 2.1 |
| Rascunho | **SQLite** via `StudyRepository` — não JSON mutável |
| CLI | Script `python -m newport_app diagnose` — dump bloqueios, **não** homologação |
| Comparativo | Página única pós-cálculo; textos traduzidos |
| Fixture inicial | Equivalente anonimizado a `renovacao_1plano_12vidas` — **não** corpus real |
| Escopo 2.1 | Sem SISCOR, sem PPTX, sem snapshot — só fictício → motor → comparativo |

---

## 11. Próximo passo

Aguardar revisão desta caracterização. **Não iniciar ETAPA 2.1** até aprovação.

Após aprovação: implementar walking skeleton conforme §10 e `docs/05-PLANO-ETAPA-2-VALIDACAO-OPERACIONAL.md`.
