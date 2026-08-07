# 05 — Ingestão cotação PDF

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. Pipeline de extração de cotações PDF, famílias de template, parsers, reconciliação e maturidade.

Versão de pipeline: `PIPELINE_COTACAO_VERSAO = "cotacao-pdf@2.5.6"` (`models/cotacao_pdf.py:12`).

---

## Pipeline completo (`pipeline.py`)

Função `parse_cotacao_pdf` (`src/newport_app/cotacao_pdf/pipeline.py:25-181`):

1. **Hash SHA-256** do conteúdo (`pipeline.py:21-22`, `35`).
2. Monta `DocumentoCotacaoPDF` (id, nome, hash, páginas=0).
3. **PDF-F01** se não começa com `%PDF` → estado `"erro"`, severidade bloqueio (`pipeline.py:44-61`).
4. Abre `PdfDocumento`; preenche `numero_paginas`.
5. **`identificar_familia(doc)`** (`template_families.py`) — identificação **antes** da extração.
6. Se família `None` ou `extrator is None`:
   - Se `operadora_candidata` → `PDF-TPL-001` (alerta), estado `"nao_reconhecido"`.
   - Senão → `PDF-F02` (info: use entrada manual), estado `"nao_reconhecido"`.
   - (`pipeline.py:68-95`)
7. Caso contrário: `familia.extrator(doc, documento_hash=...)` → `(opcoes, alertas, meta)`.
8. Para cada opção: `reconciliar_opcao(op)` (`pipeline.py:98-99`).
9. Preenche documento: `operadora_detectada`, `template_id`, `parser_versao`.
10. Estado:
    - `"extraido"` se há opções; senão `"ocr_parcial"`.
    - Amil visual sem opções → `"ocr_pendente"`.
    - Omint sem `ocr_utilizado` → `"ocr_pendente"`.
    - (`pipeline.py:105-109`)
11. Meta → campos documento: número cotação, data emissão, validade, qtd vidas (`pipeline.py:118-157`).
12. `normalizar_extracao(extracao)` (`conferencia.py`).
13. Exceção genérica → **PDF-F03**, estado `"erro"` (`pipeline.py:164-181`).

API de entrada: `POST /api/estudos/{id}/importar-cotacao-pdf` (`main.py:433-453`) — rejeita > limite bytes (413) e não-PDF (400).

---

## Famílias de template (tabela completa)

Definidas em `template_families.py` via `_registrar_familias` (`template_families.py:78-210`). **12 famílias** registradas em `FAMILIAS`.

| ID | Operadora | Âncoras obrigatórias | Âncoras proibidas | Páginas | Extrator |
|----|-----------|----------------------|-------------------|---------|----------|
| `porto-demonstrativo-27` | Porto Seguro | `PORTO`, `TABELA GERAL DE PREM`, `DEMONSTRATIVO TOTAL` | — | 25–30 | `porto.parse` |
| `porto-tabela-geral-15` | Porto Seguro | `PORTO`, `TABELA GERAL DE PREM`, `BX865J` | `DEMONSTRATIVO TOTAL` | 14–18 | `porto.parse` |
| `sulamerica-pme-sem-cp-13` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS`, `SEM COPART` | `COM COPARTICIP`, `30% DE COPART` | 12–14 | `sulamerica.parse` |
| `sulamerica-pme-copart-13` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS` | `SEM COPARTICIP` | 12–14 | `sulamerica.parse` |
| `sulamerica-pme-ajustes-dual` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS` | — | 12–14 | `sulamerica.parse` |
| `sulamerica-pme-sem-cp-v2` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS`, `SEM COPARTICIP` | `30% DE COPART`, `COM COPARTICIP` | 10–12 | `sulamerica.parse` |
| `sulamerica-pme-copart-v1` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS`, `COM COPARTICIP` | `SEM COPARTICIP` | 10–11 | `sulamerica.parse` |
| `sulamerica-pme-sem-cp-v1` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS`, `SEM COPART` | `COM COPARTICIP`, `30% DE COPART`, `PROPOSTA COMERCIAL PME MAIS`, `SEM COPARTICIP` | 9–10 | `sulamerica.parse` |
| `sulamerica-pme-copart-pct-11` | SulAmérica | `SUL`, `AMERICA`, `TABELA DE PRECOS`, `30% DE COPART` | `SEM COPARTICIP`, `COM COPARTICIP` | 10–11 | `sulamerica.parse` |
| `amil-cotacao-texto-4p` | Amil | `AMIL`, `COTAC` | — | 3–5 | `amil.parse` |
| `amil-cotacao-visual-8p` | Amil | `AMIL`, `COTAC` | — | 7–9 | `amil.parse` |
| `omint-ocr-v1` | Omint | `OMINT` | — | 1–999 | `omint.parse` |

### Regras extras de desempate (`identificar_familia`, `template_families.py:217-275`)

- `sulamerica-pme-ajustes-dual` só se `_tem_regime_duplo_tabela` (sem + % copart em tabelas distintas).
- Famílias “sem-cp” listadas **não** competem se dual.
- `sulamerica-pme-copart-13` exige `30% DE COPART` ou `COM COPARTICIP` e não dual.
- Amil texto: página 0 com **≥ 80** palavras PyMuPDF; visual: **&lt; 80**.
- Empate de score + especificidade → `None` (ambíguo).

`operadora_candidata` (`template_families.py:278-288`): PORTO/BX865J, SUL+AMERICA, AMIL, OMINT — sem Bradesco.

---

## O que cada parser extrai / ignora

### Porto (`parsers/porto.py`, `PARSER_VERSAO = "porto@2.0.1"`)

**Extrai:**

- Plano do resumo financeiro (págs. preferidas 5/2/3/1) — código `P###…` (`porto.py:41-50`).
- Prêmio (Subtotal), IOF, valor total mensal; datas; nº cotação; qtd vidas (`porto.py:53-93`).
- Páginas com “Tabela Geral de Prêmios”; linhas tarifárias por coordenadas; regime; quantidades por faixa quando o código do resumo casa com o nome do plano (`porto.py:317-340`).
- Acomodação inferida de sufixo Q/E no nome (`porto.py:96+`).

**Ignora / limita:**

- Sem tabela geral → só alerta `PDF-PORTO-004`, zero opções (`porto.py:258-269`).
- Página de tabela ilegível → `PDF-PORTO-002`, pula página.
- Regime ambíguo → alerta `PDF-PORTO-003`, ainda inclui seção.
- Quantidades só na opção associada ao plano do resumo; demais linhas sem qtds do resumo.
- Bradesco/outras operadoras: não é chamado (só via família Porto).

### SulAmérica (`parsers/sulamerica.py`, `sulamerica@2.1.0`)

**Extrai:**

- Seções de tabela (págs. localizadas); nome do plano; 10 valores de faixa; regime + % copart; validade; validação estrutural (`tarifa_validation`).
- Prêmio/IOF/total **somente** se há exatamente 1 seção e 1 linha (`sulamerica.py:174-194`).

**Ignora / limita:**

- Regime `"ambíguo"` → alerta `PDF-SUL-003` e **não** adiciona a seção (`sulamerica.py:83-95`).
- Sem seções → `PDF-SUL-001`, lista vazia.
- `quantidade` por faixa sempre `None` na montagem (`sulamerica.py:127`).

### Amil (`parsers/amil.py`, `amil@1.0.0`)

**Extrai:**

- Linhas com ≥10 valores monetários após cabeçalho com faixas 18/19; até **4** planos (`amil.py:90`).
- Regime hardcoded `"parcial"` com estado `revisar`.
- Tentativa de primeira parcela em texto com “parcela”.

**Ignora / limita:**

- Sem planos → `PDF-AMIL-001` + mensagem entrada manual.
- Planos além do 4º descartados (`planos[:4]`).
- Não monta prêmio/IOF desagregados da tabela geral Amil além do total opcional.

### Omint (`parsers/omint.py`, `omint@1.0.0`)

**Extrai:**

- Se texto útil &lt; 100 chars: tenta OCR por página (`omint.py:30-36`).
- Sem OCR: opção-esqueleto (operadora Omint + nome “revisão manual”) + `PDF-OMINT-OCR`.
- Com OCR: alerta `PDF-OMINT-PARCIAL` e **retorna lista vazia de opções** (`omint.py:68-75`) — extração financeira não implementada além do OCR.

### Bradesco — **órfão**

`parsers/bradesco.py` existe (`bradesco@1.0.0`, alerta `PDF-BRA-001`), com parse de tabelas pdfplumber e totais na pág. 2.

**Não está registrado** em `_registrar_familias` / `FAMILIAS` (`template_families.py:81-210`). `operadora_candidata` também não detecta Bradesco. Na prática o pipeline **nunca** chama `bradesco.parse` pela identificação de família — parser órfão / reservado.

---

## Faixas: rótulo → índice (`faixas.py`)

`faixa_de_rotulo` (`faixas.py:35-42`) + tabela `_FAIXAS` (`faixas.py:7-18`):

| Índice | Padrões (regex, case-insensitive) | Rótulo canônico `ROTULOS_FAIXA` |
|--------|-----------------------------------|--------------------------------|
| 0 | `0 a 18`, `00-18`, `até 18`, … | `0 a 18` |
| 1 | `19 a 23` | `19 a 23` |
| 2 | `24 a 28` | `24 a 28` |
| 3 | `29 a 33` | `29 a 33` |
| 4 | `34 a 38` | `34 a 38` |
| 5 | `39 a 43` | `39 a 43` |
| 6 | `44 a 48` | `44 a 48` |
| 7 | `49 a 53` | `49 a 53` |
| 8 | `54 a 58` | `54 a 58` |
| 9 | `59+`, `59 ou`, `+59`, … | `59+` |

---

## Códigos REC-* e validação / tarifa

### Reconciliação (`reconcile.py`)

| Código | Condição | Fonte |
|--------|----------|-------|
| `REC-SUB` | Subtotal faixas (qtd×valor) ≠ subtotal informado / prêmio usado como subtotal | `reconcile.py:55-62` |
| `REC-PREMIO` | Prêmio ≠ soma faixas (com faixas e subtotal calc ≠ 0) | `reconcile.py:64-71` |
| `REC-IOF` | `premio + iof ≠ total_recorrente` | `reconcile.py:73-82` |
| `REC-1PARCELA` | `primeira ≠ total_recorrente + custos_unicos` | `reconcile.py:84-93` |

Status resultantes: `divergente` / `reconciliado` / `nao_conferivel` / `pendente` (`reconcile.py:109-128`).  
`ok=True` também em `nao_conferivel` (totais não conferíveis com população SISCOR).

Porto pode espelhar divergência como alerta `PDF-REC` (`porto.py:356-367`).

### Validação operacional antes de aplicar (`validation.py`)

`pendencias_opcao` exige valores em: `operadora`, `plano_nome`, `tipo_fiscal`, `regime_copart`; ao menos uma faixa com valor; bloqueia se `reconciliacao.status == "divergente"` (`validation.py:8-41`).  
**Não** exige confirmação campo a campo (comentário L23).

### Validação estrutural tarifária (`tarifa_validation.py`) — códigos PDF-SUL-*

| Código | Motivo |
|--------|--------|
| `PDF-SUL-004` | Sequência de valores suspeita / faixa fragmentada |
| `PDF-SUL-005` | ≠ 10 faixas com valor |
| `PDF-SUL-006` | Nome genérico / fragmentado |

---

## Todos os códigos `PDF-*` encontrados no código

| Código | Origem |
|--------|--------|
| `PDF-F01` | Magic PDF inválido — `pipeline.py:53` |
| `PDF-F02` | Não reconhecido — `pipeline.py:78` |
| `PDF-F03` | Exceção ao ler PDF — `pipeline.py:173` |
| `PDF-TPL-001` | Operadora detectada, família não — `pipeline.py:75` |
| `PDF-PORTO-001` | Plano do resumo não identificado — `porto.py:310` |
| `PDF-PORTO-002` | Tabela ilegível na página — `porto.py:280` |
| `PDF-PORTO-003` | Regime ambíguo — `porto.py:293` |
| `PDF-PORTO-004` | Sem Tabela Geral — `porto.py:261` |
| `PDF-PORTO-005` | Resumo não casa com linhas — `porto.py:346` |
| `PDF-REC` | Divergência faixas×totais (Porto) — `porto.py:360` |
| `PDF-SUL-001` | Sem tabela tarifária — `sulamerica.py:101` |
| `PDF-SUL-003` | Regime ambíguo — `sulamerica.py:86` |
| `PDF-SUL-004` | Faixa suspeita — `tarifa_validation.py:42` |
| `PDF-SUL-005` | ≠ 10 faixas — `tarifa_validation.py:55` |
| `PDF-SUL-006` | Nome fragmentado — `tarifa_validation.py:68` |
| `PDF-AMIL-001` | Tabela visual ausente — `amil.py:82` |
| `PDF-OMINT-OCR` | OCR indisponível — `omint.py:41` |
| `PDF-OMINT-PARCIAL` | OCR parcial — `omint.py:70` |
| `PDF-BRA-001` | Tabelas Bradesco ausentes — `bradesco.py:73` (órfão) |

Mensagens UI espelhadas em `web/src/cotacaoPdf/utils.js:225-234` (subconjunto).

---

## Estados de confirmação

### `ValorExtraido.estado`

Literal: `"confirmar" | "revisar" | "ausente"` — default `"ausente"` (`cotacao_pdf.py:37`).

Flags: `confirmado`, `confirmado_por`, `confirmado_em` (`cotacao_pdf.py:38-40`).

### Confirmação implícita (`confirmacao.py`)

- `confirmar_opcao_implicita`: marca preenchidos como confirmados ao selecionar/aplicar; defaults `tipo_fiscal="seguradora"`, `regime_copart="sem"` se texto vazio (`confirmacao.py:52-74`).
- Comentário do módulo: *“seleção ou aplicação implica revisão ok”* (`confirmacao.py:1`, `64`).
- `confirmar_extracao_selecionadas`: só opções `selecionada_para_comparativo` (`confirmacao.py:104-124`).
- API `POST .../confirmar-lote` → `cotacao.confirmar_lote_sem_alerta` (`main.py:546-557`).

### Estado da extração candidata

`ExtracaoCotacaoCandidata.estado`: `extraido | nao_reconhecido | ocr_pendente | ocr_parcial | erro` (`cotacao_pdf.py:111-113`).

---

## `extracao_financeira_homologada` sempre `False`

`avaliar_maturidade` (`maturidade.py:24-60`) retorna:

```
"extracao_financeira_homologada": False   # maturidade.py:58
```

**Por quê:** o docstring e comentários separam estágios técnicos (`template_reconhecido`, `tabela_extraida`, `valores_reconciliados`, `proposta_pronta_aplicacao`) de **homologação financeira**. Explicitamente: *“Reconhecer o template não implica extração financeira homologada”* (`maturidade.py:32`).  
`docs/CORPUS-COTACAO-PDF.md:34-44` confirma: nível permanece `false` nesta etapa / pré-homologação do corpus privado.  
Modelo HTTP: `MaturidadeExtracaoResponse.extracao_financeira_homologada: bool = False` (`responses_cotacao.py:15`).

Não é bug de flag esquecida — é **política de maturidade** até aceite privado.

---

## Fallback manual

1. Pipeline / alertas: `PDF-F02`, `PDF-AMIL-001` orientam *“use entrada manual”* (`pipeline.py:77`; `amil.py:83`).
2. Spec IS-07: entrada manual é o fallback principal (`docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md` — IS-07).
3. UI: `PropostaPanel.jsx` — contingência “Não foi possível importar? Preencher manualmente.”; grava `opcoes_proposta` com `proveniencia.origem: "manual"` via `PUT` rascunho (`PropostaPanel.jsx:46`, `181-215`, `146`).
4. PDF reconhecido mas não aplicável: revisão em `CotacaoPdfPanel` (editar campos, selecionar, aplicar) embutido em `PropostaPanel.jsx:169`.

---

## Flags de maturidade

`avaliar_maturidade` (`maturidade.py:53-60`):

| Flag | Significado |
|------|-------------|
| `template_reconhecido` | Estado ≠ nao_reconhecido/erro **e** `template_id` |
| `tabela_extraida` | Há opções ativas e **sem** alertas `PDF-PORTO-004` / `PDF-SUL-001` |
| `valores_reconciliados` | Todas ativas com `reconciliacao.ok` |
| `proposta_pronta_aplicacao` | Alvo (selecionadas se consciente, senão todas) sem `pendencias_opcao` |
| `extracao_financeira_homologada` | **sempre False** |
| `exige_selecao_consciente` | Template `porto-*` **ou** &gt; 3 opções ativas (`LIMIAR_SELECAO_CONSCIENTE = 3`, `maturidade.py:8-21`) |

Retornada no import PDF (`services/extracao_cotacao.py` + `ResultadoImportacaoCotacaoResponse`).

---

## ⚠️ NÃO VERIFICADO

- Resultados de aceite privado por hash (`test_corpus_aceite_privado.py`) neste workspace (corpus pode estar ausente).
- Cobertura real das 12 famílias no corpus privado atual (doc `CORPUS-COTACAO-PDF.md` cita 10/12 em um snapshot; pode divergir).
- Qualidade OCR Omint/Tesseract no ambiente do operador.
- Uso futuro do parser Bradesco (órfão hoje).
- Paridade centavo-a-centavo com totais impressos de PDFs comerciais fora dos testes sintéticos.
- Homologação financeira formal por Wesley/Newport (flag permanece false por política).
