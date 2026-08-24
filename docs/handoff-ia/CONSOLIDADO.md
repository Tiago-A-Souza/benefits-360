# CONSOLIDADO — Sistema de Estudos Newport (handoff para IA externa)

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento **autocontido**. Não depende de acesso ao repositório. Onde documentação canônica e código divergirem, **código prevalece**. Citações no formato `arquivo:linha` referem-se a caminhos sob `src/` ou `docs/` do commit citado.

---

## 1. O que é o sistema e em que estágio está

O **Sistema de Estudos Newport** monta um **comparativo financeiro** entre o plano de saúde coletivo atual de um cliente PME e propostas de operadoras/seguradoras. Entrada típica: planilha SISCOR (vidas e valores) + PDFs de cotação (ou digitação manual). Saída típica hoje: **HTML autocontido** (modos por faixa etária ou por beneficiário), após cálculo, snapshot com hash e aprovação local.

O núcleo financeiro é um **motor puro** `calcular(EstudoInput, EffectivePolicy) → MotorResult` (`newport_motor/engine.py:29-33`) que trabalha só com **centavos inteiros** e taxas em basis points — sem float. A aplicação (`newport_app` + React/Vite) cuida de ingestão, conferência humana, wizard, persistência SQLite e apresentação.

**Não é** portal do cliente final, nem plataforma multi-tenant com login. Público-alvo: analistas Newport, revisor local provisório, e agentes/IAs que discutem arquitetura sem abrir o repo.

### Estágio real (código + git) vs AGENTS.md

| Camada | Estado |
|--------|--------|
| Motor financeiro + suítes A–H | **implementado** (piloto; políticas provisórias) |
| SISCOR + conferência | **implementado** (homologação com corpus privado ainda operacional/pendente) |
| Cotação PDF (Porto, SulAmérica, Amil, Omint) | **parcial** — templates reconhecidos; `extracao_financeira_homologada` **sempre false** (`cotacao_pdf/maturidade.py:58`) |
| Wizard operacional (ETAPA 3.0+) | **implementado** até confirmação do comparativo e HTML |
| Snapshot / aprovação / HTML | **implementado** |
| PPTX / rede / reembolso / odonto / seguro de vida | **inexistente** no software |
| Auth / cloud / link público | **inexistente** (proibidos sem autorização) |

**Divergência de rótulo de etapa:** `AGENTS.md:5` ainda diz «ETAPA 2.8.1 concluída»; o `git log` chega a **ETAPA 3.0** (`855ed7b`) + hotfixes 3.0.1–3.0.3 + commits de comparativo/apresentação até `2a69d4c`. **Código e histórico git prevalecem** sobre o rótulo em `AGENTS.md`.

Faixa comercial homologada: **1–29 vidas** (alerta **H-01** acima disso). **B-08** no código = estudo **sem vidas incluídas**, não “>29” (`validations.py:27-44`). API: `API_VERSAO = "2.8.2"` (`api/main.py:124`).

### Três invariantes

1. **Dinheiro nunca é float.** Tudo é `MoneyCents` (int). IOF padrão 238 bps só para `tipo_fiscal=seguradora`. `price_basis=desconhecido` bloqueia (B-02). Conferência humana (`confirmado`) é obrigatória para valores de IA/extração em alerta (B-03). Defaults de confirmação no draft/PDF começam em `false`; no motor o default de `ProvenienciaCampo.confirmado` é `True` — o compilador precisa carregar o estado certo.
2. **O entregável cliente histórico (PPTX com 12 partes) não foi portado.** O sistema cobre o núcleo financeiro + classificação de copart; rede, reembolso, odonto, seguro de vida e PPTX estão fora. HTML é o entregável real; banner “RASCUNHO INTERNO” permanece enquanto políticas forem provisórias.
3. **Governança:** calcular → snapshot (hash) → revisar → aprovar (`confirmo_conteudo`) → HTML. Aprovação sem atestado é rejeitada; HTML exige snapshot `aprovado`. Extração PDF “pronta para aplicar” **não** significa homologação financeira.

---

## 2. Domínio (resumo operacional)

| Conceito | Definição operacional | Maturidade |
|----------|----------------------|------------|
| Renovação | Cliente já tem plano; baseline vigente/reajustado; atribuição por **subgrupo** | implementado (caminho principal) |
| Seguro novo | Sem bloco “atual”; atribuição por **vida**; fora da autorização de produção | parcial (motor existe; UI otimizada para renovação) |
| Vida | Beneficiário incluído ou não; unidade de prêmio/faixa | implementado |
| 10 faixas ANS | Índices 0–9: ≤18…≤58, senão 59+ (`faixa.py:7-24`) | implementado |
| Copart | `sem` / `parcial` / `percentual` — **particiona seções**, não calcula % sobre atos | implementado como classificação |
| Reajuste | `reajuste_bps` (ex. 11,98% → 1198); negativo → B-07 | implementado |
| Baseline | Vigente e reajustado sempre calculados; apresentado via `EffectivePolicy.baseline_escolhido` | implementado |
| Precedência | Fatura × tabela atual (`PrecedenciaAtualVida`); ambos + `None` → B-07 | implementado |
| Price basis / IOF | `inclui_iof` \| `exclui_iof` \| `desconhecido`; IOF 238 bps só seguradora | implementado |
| Rede / reembolso / CPT / carência / odonto / seguro de vida | Fora do software | inexistente |

`Vida.faixa_override` existe (`newport_motor/models.py:132`) e **não é lido** pelo cálculo (`calculation.py` usa `faixa_em`).

---

## 3. Modelo de dados — entidades centrais (campos e tipos)

Persistência: domínio editável em `rascunhos.payload` (JSON). Candidatas SISCOR/PDF e snapshots têm tabelas próprias com `payload` JSON. Colunas de `rascunhos`: `id`, `payload`, `atualizado_em`, `rascunho_versao`, `policy_set_versao` (`repository/migration.py:42-48`).

### 3.1 `ProvenienciaCampo` (motor) — `newport_motor/provenance.py:21-28`

| Campo | Tipo | Default |
|-------|------|---------|
| `origem` | `OrigemValor` (`extraido`\|`calculado`\|`manual`\|`ia`) | obrigatório |
| `documento_id` | `str \| None` | |
| `extrator_versao` | `str` | `"manual"` |
| `evidencia_pagina` | `int \| None` | |
| `evidencia_trecho` | `str \| None` | |
| `confirmado` | `bool` | **`True`** |
| `valor_anterior_centavos` | `int \| None` | |

Espelho no draft: `ProvenienciaRascunho` (`models/draft.py:42-54`) — `origem`, `documento_id`, `documento_hash`, `extrator_versao`, `linha_origem`, `celula_origem`, `pagina`, `evidencia`, `coordenadas`, `confirmado` (**default `False`**), `confirmado_por`, `confirmado_em`. Mapper copia só `origem`, `documento_id`, `extrator_versao`, `confirmado` (`draft_compiler/mapper.py:83-89`).

### 3.2 `RascunhoEstudo` — campos-chave (`models/draft.py:245-275`)

| Campo | Tipo | Default / nota |
|-------|------|----------------|
| `rascunho_versao` | `str` | deve ser `"1.0"` (`RASCUNHO_VERSAO_ATUAL`) |
| `policy_set_versao` | `str` | |
| `id`, `titulo` | `str` | |
| `formato` | `Literal["renovacao","novo"]` | `"renovacao"` |
| `empresa_cliente` | `EmpresaCliente \| None` | `nome: str` |
| `vidas` | `list[VidaRascunho]` | obrigatório |
| `subgrupos_atuais` | `list[SubgrupoAtualRascunho]` | `[]` |
| `opcoes_proposta` | `list[OpcaoPropostaRascunho]` | `[]` |
| `regimes_copart` | `list[RegimeCopartRascunho]` | `id` + `tipo` sem/parcial/percentual |
| `cenarios` | `list[CenarioRascunho]` | atribuições `alvo_tipo` subgrupo\|vida |
| `documentos_cotacao` / `documentos_siscor` | listas tipadas | `[]` |
| `escolhas` | `EscolhasEstudo` | `data_referencia_idade`, `baseline_escolhido`, `precedencia_atual_vida` (campos confirmáveis) |
| `selecao_apresentacao` | `SelecaoApresentacaoRascunho \| None` | `opcao_ids`, `ordem` |
| `confirmacao_comparativo` | `ConfirmacaoComparativoRascunho \| None` | hash + fingerprint + `confirmado_em` |
| `observacoes` / `metadados_pptx` | opcionais | PPTX metadados existem; renderer PPTX **não** |

**`VidaRascunho`** (`draft.py:156-166`): `id`, `nome`, `nascimento: date`, `parentesco`, `incluida: bool=True`, motivos, `subgrupo_atual_id`, `valor_fatura` / `valor_conferencia` (`ComponenteFinanceiroRascunho`: `centavos`, `price_basis`, `proveniencia`).

**`SubgrupoAtualRascunho`** (`draft.py:191-202`): `id`, `operadora`, `plano_nome`, `regime_copart_id`, `tipo_fiscal` seguradora\|operadora, `acomodacao`, `modalidade`, `reajuste_bps`, `fatura_price_basis`, `subtotal_atual_impresso`, `tabela_atual`.

### 3.3 `OpcaoPropostaRascunho` — `draft.py:205-224`

| Campo | Tipo |
|-------|------|
| `id`, `operadora`, `plano_nome` | `str` |
| `regime_copart_id` | `str \| None` |
| `tipo_fiscal` | `Literal["seguradora","operadora"] \| None` |
| `acomodacao` / `modalidade` | opcionais |
| `tabela` | `list[TabelaFaixaRascunho]` — `faixa` 0–9, `valor_centavos`, `quantidade_cotada`, `price_basis`, `proveniencia` |
| `premio_saude`, `iof`, `total_recorrente`, `total_primeira_parcela`, `subtotal_impresso` | `ComponenteFinanceiroRascunho \| None` |
| `custos_unicos` | `list[CustoUnicoRascunho]` |
| `documento_cotacao_id`, `extracao_id`, `extracao_opcao_id` | `str \| None` |
| `validade_oficial` | `date \| None` |
| `observacoes` | `str \| None` |

No motor o equivalente é `OpcaoPlano` (`newport_motor/models.py:79-99`) com `regime_copart_id: str` **obrigatório**.

### 3.4 `EstudoInput` — `newport_motor/models.py:177-210`

| Campo | Tipo |
|-------|------|
| `id` | `str` |
| `formato` | `FormatoEstudo` (`novo`\|`renovacao`) |
| `vidas` | `list[Vida]` |
| `subgrupos_atuais` | `list[SubgrupoAtual]` |
| `opcoes_plano` | `list[OpcaoPlano]` |
| `regimes_copart` | `list[RegimeCopart]` (`id`, `tipo`, `escopo_procedimentos`, `percentual_bps`) |
| `cenarios` | `list[Cenario]` (`id`, `rotulo`, `baseline_escolhido`, `atribuicoes`) |
| `documentos` | `list[DocumentoCotacao]` |

Enums motor (`types.py`): `PriceBasis`, `TipoFiscal`, `BaselineEscolhido`, `RegimeCopartTipo`, `RoundingStrategy`, `PrecedenciaAtualVida`, `AlvoTipo`, `OrigemValor`, `EstadoExtracao`; `MoneyCents = NewType("MoneyCents", int)` (`types.py:8`).

### 3.5 `EffectivePolicy` — `newport_motor/policy.py:17-74`

| Campo | Tipo | Default |
|-------|------|---------|
| `policy_set_versao` | `str` | `"v2026.07-provisoria"` |
| `data_referencia_idade` | `date \| None` | `None` |
| `baseline_escolhido` | `BaselineEscolhido \| None` | `None` |
| `precedencia_atual_vida` | `PrecedenciaAtualVida \| None` | `None` |
| `iof_bps` | `RateBasisPoints` | `238` |
| `tolerancias` | `TolerancePolicy` | por_vida=1c, subtotal=2c, total=5c |
| `estrategia_arredondamento` | `RoundingStrategy` | `POR_VIDA_ENTAO_SOMA` |
| `max_vidas_homologadas` | `int \| None` | `29` |
| `politicas_resolvidas` | `dict[str, object]` | `{}` |

Contrato: política **já resolvida fora do motor** (`policy.py:30-31`).

### 3.6 `MotorResult` — `newport_motor/result.py:66-71`

| Classe | Campos |
|--------|--------|
| `Validacao` | `codigo`, `severidade`, `mensagem`, `alvo_ref` |
| `ValorCalculado` | `centavos: int`, `proveniencia`, `fontes: list[LinhagemReferencia]` |
| `ResultadoVida` | `vida_id`, `idade`, `faixa`, `atual_vigente_centavos`, `atual_reajustado_centavos`, `proposta_centavos`, `diff_mes_centavos`, `diff_ano_centavos` |
| `ResultadoSubgrupo` | `subgrupo_id`, `opcao_plano_id`, subtotaais, `vidas` |
| `ScenarioSectionResult` | `regime_tipo`, `rotulo_derivado`, `subgrupos`, totais/diffs |
| `ScenarioResult` | `cenario_id`, `baseline_apresentado`, `secoes`, totais/diffs |
| **`MotorResult`** | `estudo_id`, `cenarios`, `validacoes`, `politicas_efetivas: dict`, `bloqueios_abertos: list[str]` |

### 3.7 `ImportacaoSiscorCandidata` — `models/siscor_import.py:97-117`

| Campo | Tipo |
|-------|------|
| `id`, `estudo_id` | `str` |
| `versao` | `int` |
| `importador_versao` | `str` |
| `documento_id`, `documento_hash_sha256` | `str` |
| `estado` | `Literal["aguardando_conferencia","aplicada","substituida"]` |
| `empresa_sugerida` | `str \| None` |
| `linhas` | `list[LinhaSiscorCandidata]` — id, numero_linha, cliente, segurado, parentesco, nascimento, plano, operadora, valor_centavos, status, `incluida_sugerida`, alertas, flags confirmação, `subgrupo_sugerido_id`, excluida, edições (`siscor_import.py:44-69`) |
| `subgrupos_sugeridos` | `list[SubgrupoSiscorSugerido]` (plano × operadora) |
| `estatisticas` | contadores |
| `correspondencias_sugeridas` | reimport `nova_versao` |
| `criado_em` / `criado_por` | datetime / str |

### 3.8 `ExtracaoCotacaoCandidata` — `models/cotacao_pdf.py:106-123`

| Campo | Tipo |
|-------|------|
| `id`, `estudo_id` | `str` |
| `versao` | `int` |
| `documento` | `DocumentoCotacaoPDF` (id, nome_arquivo, hash_sha256, operadora_detectada, template_id, parser_versao, numero_paginas) |
| `estado` | `Literal["extraido","nao_reconhecido","ocr_pendente","ocr_parcial","erro"]` |
| `opcoes` | `list[OpcaoCotacaoCandidata]` — metadados como `ValorExtraido`, tabela, componentes, `reconciliacao`, excluida, `selecionada_para_comparativo` |
| `numero_cotacao`, `data_emissao`, `validade_oficial`, `quantidade_vidas_total`, `observacoes` | `ValorExtraido \| None` |
| `alertas` | `list[AlertaExtracaoCotacao]` |
| `criado_em` / `criado_por` | datetime / str |
| `versoes_anteriores` | `list[int]` |

Pipeline versão: `PIPELINE_COTACAO_VERSAO = "cotacao-pdf@2.5.6"` (`cotacao_pdf.py:12`).

---

## 4. Motor de cálculo

### Assinatura

```text
def calcular(estudo: EstudoInput, policy: EffectivePolicy) -> MotorResult
```

Fonte: `newport_motor/engine.py:29-33`. Função pura. **B-01 (aprovação) é da aplicação**, não do motor.

### Regras MoneyCents

| Regra | Código |
|-------|--------|
| Dinheiro = `MoneyCents` (int) | `types.py:8` |
| Taxas = `RateBasisPoints` (int) | `types.py:9` |
| Sem float na aritmética | `money.py:1` |
| Half-up: `(numerador + denom//2) // denom` | `money.py:12-18` |
| Taxa/IOF: `valor * (10000 + bps)` half-up ÷ 10000 | `money.py:26-29` |
| IOF só se `tipo_fiscal == SEGURADORA` | `finance.py:15-16` |
| `exclui_iof` → aplica IOF; `inclui_iof` → não reaplica | `finance.py:76-82` |
| Só `por_vida_entao_soma` homologada; outras → B-07 | `validations.py:101-115` |

### Sequência em `calcular` (`engine.py:34-120`)

| # | Passo | Ação |
|---|-------|------|
| 1 | Escopo vidas | `validar_escopo_vidas` → B-08 / H-01 |
| 2 | Policy | `validar_b07_politica_obrigatoria` |
| 3 | Estrutura | `validar_entrada_estrutural` (B-02/B-05/B-06 + 1ª parcela) |
| 4 | Confirmação | `validar_b03_valores_nao_confirmados` |
| 5–8 | Atribuições / opções / nascimento / baseline | B-05/B-06 |
| 9 | Early exit | se `BLOQUEANTE` → cenários `[]` |
| 10 | Idade×valor | `validar_b04_idade_valor` |
| 11–12 | Dados opções + early exit | |
| 13 | Cálculo | `calcular_cenario` por cenário |
| 14 | Reconciliação | B-02 via `reconciliar_opcao_cenario` |
| 15–16 | Pós-check B-06 + retorno | `MotorResult` com `bloqueios_abertos` |

### Cálculo renovação por vida (outline)

1. `(idade, faixa) = faixa_em(nascimento, data_referencia_idade)`
2. Base atual via tabela e/ou fatura + `precedencia_atual_vida`
3. `vigente` = normalizar para recorrente (IOF se seguradora + `exclui_iof`)
4. `reajustado = apply_rate_bps(vigente, reajuste_bps)`
5. `proposta` = valor da faixa na opção, mesma normalização
6. Baseline apresentado conforme policy
7. `diff_mes = proposta - atual_baseline`; `diff_ano = diff_mes * 12`
8. Soma → subgrupo → seção (regime) → cenário

---

## 5. Bloqueios B-01…B-08 e alerta H-01 (completo)

| Código | Camada | Trigger | Mensagem / evidência |
|--------|--------|---------|----------------------|
| **B-01** | **App** (não motor) | Gerar apresentação sem snapshot `aprovado` / aprovação inválida | `"Somente snapshots aprovados podem gerar apresentação."` — `apresentacao.py:45-51`; motor declara fora em `engine.py:32` |
| **B-02** | Motor | `price_basis` desconhecido; fatura basis desconhecido; divergências conferência/subtotal/prêmio+IOF/1ª parcela | Várias mensagens em `reconciliation.py` / `validations.py:262-399` |
| **B-03** | Motor | Origem IA sem `confirmado`; não confirmado com documento em alerta/falha | `validations.py:478-492` |
| **B-04** | Motor | Diff fatura×tabela > tolerância por vida; (alerta) sem faixa na tabela | `validations.py:718-756` |
| **B-05** | Motor | Nascimento > referência; renovação sem subgrupo/fonte baseline; sem opções; opção/doc/regime inexistente; faixa inválida/duplicada; tabela incompleta | `validations.py:164-615` |
| **B-06** | Motor | Vidas sem cenários; novo com alvo ≠ vida; renovação com alvo ≠ subgrupo; alvo sem atribuição; pós-cálculo sem cenários | `validations.py:628-681`; `engine.py:106-110` |
| **B-07** | Motor | Sem `data_referencia_idade`; renovação sem baseline; sem reajuste / reajuste negativo; precedência obrigatória quando fatura+tabela; estratégia de arredondamento não piloto | `validations.py:57-147` |
| **B-08** | Motor | **0 vidas incluídas** | `"Estudo sem vidas incluídas."` — `validations.py:27-31` |
| **H-01** | Motor (alerta) | `count > max_vidas_homologadas` (default 29) | `"Vidas incluídas ({n}) excedem a faixa homologada..."` — `validations.py:38-44` |

**Atenção docs antigos:** `docs/04-HANDOFF-IMPLEMENTACAO.md:90` ainda descreve B-08 como “>29 bloqueia” — **incorreto**; isso é H-01 alerta. Nome de teste legado `test_b08_mais_de_29_vidas` asserta H-01 (`test_suite_h_formas_escala.py:55-58`).

---

## 6. Ingestão SISCOR

### Whitelist — 8 colunas obrigatórias (`siscor_importer/constants.py:5-14`)

| Coluna canônica |
|-----------------|
| `CLIENTE` |
| `SEGURADO` |
| `PARENTESCO` |
| `DATA DE NASCIMENTO` |
| `PLANO` |
| `SEGURADORA` |
| `VALOR` |
| `STATUS SEGURADO` |

Falta qualquer → `APP-SIS-F05` (`parser.py:166-177`). Colunas extras (CPF, endereço, etc.) não são persistidas na candidata (alinhado a P9). `sexo` opcional em P9 **não** é ingerido.

### Alertas-chave

**Arquivo:** `APP-SIS-F01`…`F07` — vazio/inválido, não-xlsx, sem cabeçalho, colunas duplicadas, layout incompleto, sem linhas, célula com fórmula (`parser.py:98-386`).

**Linha:** `APP-SIS-001`…`010`, `012` (**não existe `011`**):

| Código | Condição |
|--------|----------|
| 001/002 | Nascimento ausente/inválido / futuro |
| 003/009/012 | Valor zerado / ilegível / negativo |
| 004/010 | Plano / operadora ausente |
| 005 | Status ausente ou ≠ ATIVO normalizado |
| 006 | Duplicidade `(segurado, nascimento, plano)` |
| 007/008 | Nome / parentesco ausente ou não mapeado |

Só `STATUS = ATIVO` sugere inclusão (`constants.py:18`; `parser.py:343`). Valor → centavos via `Decimal` half-up, nunca float (`siscor_importer/money.py:1-32`). Subgrupos: chave `(plano, operadora)` (`subgrupos.py:14-30`).

Fluxo: `POST importar-siscor` → conferência → PATCH linhas / `confirmar-lote` → `aplicar_candidata_ao_rascunho`. Reimportação: `substituir` \| `nova_versao` (409 se modo omitido com dados existentes).

---

## 7. Ingestão cotação PDF

### Famílias registradas (12) — `template_families.py:78-210`

| ID | Operadora | Extrator |
|----|-----------|----------|
| `porto-demonstrativo-27` | Porto Seguro | `porto.parse` |
| `porto-tabela-geral-15` | Porto Seguro | `porto.parse` |
| `sulamerica-pme-sem-cp-13` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-copart-13` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-ajustes-dual` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-sem-cp-v2` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-copart-v1` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-sem-cp-v1` | SulAmérica | `sulamerica.parse` |
| `sulamerica-pme-copart-pct-11` | SulAmérica | `sulamerica.parse` |
| `amil-cotacao-texto-4p` | Amil | `amil.parse` |
| `amil-cotacao-visual-8p` | Amil | `amil.parse` |
| `omint-ocr-v1` | Omint | `omint.parse` |

**Bradesco:** `parsers/bradesco.py` existe mas **não** está em `FAMILIAS` — parser órfão; pipeline nunca o chama pela identificação.

### `extracao_financeira_homologada` sempre `False`

`avaliar_maturidade` (`maturidade.py:24-60`) retorna sempre `"extracao_financeira_homologada": False` (`maturidade.py:58`). Política explícita: reconhecer template ≠ homologação financeira. Flags técnicas: `template_reconhecido`, `tabela_extraida`, `valores_reconciliados`, `proposta_pronta_aplicacao`, `exige_selecao_consciente` (Porto ou >3 opções).

Códigos importantes: `PDF-F01`/`F02`/`F03`, `PDF-TPL-001`, `PDF-PORTO-*`, `PDF-SUL-*`, `PDF-AMIL-001`, `PDF-OMINT-*`, `REC-SUB`/`REC-PREMIO`/`REC-IOF`/`REC-1PARCELA`. Fallback: entrada manual (`PropostaPanel.jsx`).

---

## 8. API — endpoints (método + rota + propósito)

API FastAPI `API_VERSAO = "2.8.2"` (`api/main.py:124`). CORS: `localhost:5173` (`main.py:241-245`).

| Método | Rota | Propósito |
|--------|------|-----------|
| GET | `/api/config` | Modo, versão, limite upload |
| GET/POST | `/api/estudos` | Listar / criar estudo |
| GET | `/api/estudos/{id}` | Resumo |
| GET | `/api/estudos/{id}/rascunho` | Rascunho completo |
| GET | `/api/estudos/{id}/pendencias` | Pendências UI |
| PUT | `/api/estudos/{id}` | Salvar rascunho (invalida snapshot) |
| POST | `/api/estudos/{id}/importar-siscor` | Upload XLSX SISCOR |
| GET | `/api/estudos/{id}/conferencia-siscor` | Conferência |
| POST | `.../conferencia-siscor/confirmar-lote` | Confirma + apply |
| PATCH | `.../conferencia-siscor/linhas/{linha_id}` | Editar/confirmar/excluir linha |
| GET | `/api/estudos/{id}/resumo-plano-atual` | Resumo plano atual |
| POST | `/api/estudos/{id}/importar-cotacao-pdf` | Upload PDF |
| GET | `/api/estudos/{id}/extracao-cotacao` | Listar extrações |
| GET | `/api/estudos/{id}/extracao-cotacao/{eid}` | Detalhe |
| PATCH | `.../extracao-cotacao/{eid}/campos/{campo_id}` | Editar/confirmar campo |
| POST | `.../opcoes/{oid}/excluir` | Excluir opção |
| POST | `.../opcoes/{oid}/selecionar` | Selecionar (+ confirmação implícita) |
| POST | `.../extracao-cotacao/{eid}/confirmar-lote` | Confirmar sem alerta |
| POST | `.../extracao-cotacao/{eid}/aplicar` | Injetar no rascunho |
| DELETE | `/api/estudos/{id}/extracao-cotacao/{eid}` | Remover extração |
| GET | `.../documentos-cotacao/{did}/pdf` | Servir PDF |
| POST | `/api/estudos/{id}/calcular` | Compilar + motor |
| PUT | `.../comparativo/selecao-apresentacao` | Seleção de propostas |
| POST | `.../comparativo/confirmar` | Confirmação com hash |
| POST | `/api/estudos/{id}/snapshot` | Snapshot candidato |
| GET | `/api/estudos/{id}/snapshots` | Listar |
| GET | `/api/estudos/{id}/snapshots/{sid}` | Obter |
| POST | `.../snapshots/{sid}/aprovar` | Aprovar (`confirmo_conteudo`) |
| GET | `/api/estudos/{id}/snapshot-aprovado` | Snapshot aprovado atual |
| POST | `.../snapshots/{sid}/apresentacao/preview` | Preview ViewModel |
| POST | `.../apresentacao/gerar` | Gerar HTML |
| GET | `/api/estudos/{id}/historico` | Histórico |
| POST | `.../historico/vincular` | Vincular cliente/ciclo |
| POST | `.../historico/vinculos/confirmar` | Confirmar vínculo |
| POST | `.../historico/vinculos/confirmar-lote` | Lote |
| GET/POST | `/api/clientes` | Listar / criar cliente |
| GET | `/api/clientes/{cid}/ciclos` | Ciclos |
| GET | `.../entregaveis/{eid}/html` | Baixar HTML |
| POST | `/api/estudos/{id}/plano-contratado` | Registrar plano (explícito, nunca auto) |
| GET | `/api/estudos/{id}/planos-contratados` | Listar planos |
| GET | `/api/estudos/{id}/historico/posicoes` | Posições cadastrais |
| * | `/` (static) | SPA `web/dist` se existir |

---

## 9. Wizard, demo/real e portas

### Passos (`web/src/fluxo/passos.js:3-14`)

| Chave | Título | Visível |
|-------|--------|---------|
| `base` | Base atual | sempre |
| `plano` | Plano atual | sempre |
| `cotacoes` | Cotações | sempre |
| `selecionados` | Correspondência com planos atuais | só se `subgrupos_atuais.length > 1` |
| `comparativo` | Comparativo | sempre |
| `apresentacao` | Apresentação | sempre |

Conclusão heurística (`stepStatus.js`): `base` exige conferência sem exceções e confirmadas>0; `plano` exige escolhas confirmadas; `cotacoes` exige opções; `comparativo` exige cenários sync + `confirmacao_comparativo`; `apresentacao` **nunca** marcada concluída na heurística.

Mapa: `SiscorPanel` → `ConfigEstudo` → `PropostaPanel`/`CotacaoPdfPanel` → (`PlanosSelecionadosPanel`) → `ComparativoPanel` → `RevisaoApresentacaoPanel`.

### Portas

| Camada | Valor | Fonte |
|--------|-------|-------|
| Vite dev | **5173** (`strictPort`) | `web/vite.config.js:7-9` |
| Proxy `/api` → | **http://127.0.0.1:8002** | `vite.config.js:10-13` |

### Modos demo vs real (`config/runtime.py`, `config/paths.py`)

| | DEMO (default) | REAL |
|--|----------------|------|
| Env | `NEWPORT_MODO=demo` | `NEWPORT_MODO=real` (bind localhost) |
| Estudos DB | `.data/newport_app.db` | `.private/runtime/estudos.db` |
| Importações / uploads / cotação / entregáveis | `.data/*_demo` | `.private/runtime/*` |
| Seed | demos 12 e 41 vidas | sem seed |

---

## 10. Snapshot, hash e apresentação

### Hash canônico — campos (`snapshot/hashing.py:9-19`)

Payload canônico **sem timestamps**:

| Campo |
|-------|
| `rascunho` |
| `estudo_input` |
| `effective_policy` |
| `motor_result` |
| `comparativo` |
| `compiler_versao` |
| `motor_versao` |
| `policy_set_versao` |
| `documentos` |

Serialização: `json.dumps(..., sort_keys=True, separators=(",", ":"))` → SHA-256 hex (`hashing.py:22-36`). `gerado_em` persiste fora do hash.

Fluxo: calcular → snapshot `candidato` → revisão UI → aprovar (`confirmo_conteudo` + revisor; autoaprovação exige justificativa) → HTML só se `aprovado` (`apresentacao.py:45-51`).

Modos HTML: `faixas` (sem nomes) / `beneficiario` (PII). Banner default: «RASCUNHO INTERNO — políticas provisórias sujeitas a homologação.» (`models/presentation.py:117-119`). `MOTOR_VERSAO = "0.1.0"` no snapshot vs `motor@0.1.2` na proveniência interna — divergência conhecida.

Plano contratado: `POST .../plano-contratado` — **nunca** automático após aprovação (`AGENTS.md:38`).

---

## 11. Paridade com entregável manual (12 partes)

Referência: entregável PPTX Newport com 12 partes. Piloto cobre núcleo financeiro; HTML ≠ PPTX.

| Parte | Status | O que o sistema produz hoje | Gap |
|-------|--------|-----------------------------|-----|
| 1. Projeção Financeira Cenário 1 | **parcial** | Comparativo + HTML por faixas/regime (`builder.py:231-301`; `html_renderer.py:242-257`) | Não é PPTX; layout ≠ slides |
| 2. Projeção Financeira Cenário 2 | **parcial** | Demais seções por regime no mesmo HTML (`secoes_regime`) | Sem slides “Cenário 1/2” |
| 3. Coparticipação | **parcial** | Rótulo/meta de regime; **não** calcula % sobre atos | Sem tabela de procedimentos |
| 4. Procedimentos Reembolsáveis | **inexistente** | Nada | Parte ausente |
| 5. Reembolso | **inexistente** | Nada | Parte ausente |
| 6. Rede Básico | **só previsto em doc** | Nada | Ausente |
| 7. Rede Intermediário | **só previsto em doc** | Nada | Ausente |
| 8. Rede Gerencial | **só previsto em doc** | Nada | Ausente |
| 9. Rede Diretoria | **só previsto em doc** | Nada | Ausente |
| 10. Regras Comerciais | **parcial** | Lista `ressalvas` no HTML | Sem módulo estruturado |
| 11. Odonto | **inexistente** | Nada | Ausente |
| 12. Vida (seguro de vida) | **inexistente** | Nada — **≠** `Vida`/beneficiário de saúde | Ausente |

---

## 12. Divergências documentação × código

| ID | Doc diz | Código faz | Evidência |
|----|---------|------------|-----------|
| **B-08** | `docs/04:90` — «>29 bloqueia» | B-08 = zero vidas; >max = **H-01** alerta | `validations.py:21-46` |
| **B-01** | Handoffs antigos no motor | B-01 na **app** (aprovação) | `engine.py:32`; `validations.py:1` |
| **Estágio AGENTS** | ETAPA 2.8.1 | Git **3.0+** | `AGENTS.md:5` vs `git log` |
| **PolicySet tabelas** | Caderno: `PolicyEntry` SQL | Registry in-memory; sem tabelas SQL de policy | `policy/registry.py:13-41` |
| **`faixa_override`** | Campo no modelo | Não lido no cálculo | `models.py:132` (motor) |
| **Versões motor** | Uma versão semântica | Snapshot `"0.1.0"` vs proveniência `"motor@0.1.2"` | `models/snapshot.py:10`; `reconciliation.py:354` |
| **`confirmado` default** | Draft/PDF inicia `false` | Motor default `True` | `draft.py:52`; `provenance.py:27` |
| **PriceBasis draft** | Inclui `nao_aplica` | Motor só três valores | `draft.py:14-18` vs `types.py:12-15` |

---

## 13. Testes e qualidade (compacto)

- Coleta: **326** testes (`pytest --collect-only`).
- Suítes motor A–H: tipos, reconciliação, IOF, reajuste, idade/faixa, cenários, pureza/policy, formas/escala.
- Marcador `private_corpus` para PDFs fora do Git (`pyproject.toml:36-37`).
- Hotfixes cobertos: 2.9.1, 3.0.1, 3.0.2, 3.0.3.
- Lacunas deliberadas: rede, reembolso, PPTX, seguro novo E2E, Bradesco sem família, `quantidade_cotada` vs vidas não cruzada no motor (`RELATORIO-IMPLEMENTACAO.md:65`).

---

## 14. Próximos passos (impacto ÷ esforço)

| # | Ação | Por quê |
|---|------|---------|
| 1 | Atualizar `AGENTS.md` (3.0+) e corrigir/addendum B-08 em `docs/04` | Baixo esforço; evita erro de agentes |
| 2 | Registrar família Bradesco em `FAMILIAS` + testes | Parser já existe |
| 3 | Verificar `quantidade_cotada` × vidas (alerta ou B-xx) | Lacuna financeira explícita |
| 4 | E2E seguro novo na UI + testes | Motor parcial; produto incompleto |
| 5 | Renderer PPTX a partir do `PresentationViewModel` | Alto impacto; exige autorização |
| 6 | Auth corporativa + invalidação de autoaprovação solta | Governança |
| 7 | Rede / reembolso / odonto / seguro de vida | Fora do piloto; só após PPTX financeiro estável |

---

## 15. Glossário (termos principais)

| Termo | Definição | Código |
|-------|-----------|--------|
| Estudo / Rascunho | Unidade de trabalho / estado JSON editável | `RascunhoEstudo` |
| Renovação / Seguro novo | Com baseline atual / só propostas | `FormatoEstudo` |
| Vida | Beneficiário de saúde no cálculo | `Vida` / `VidaRascunho` |
| Seguro de vida | Produto fora do piloto (**≠** vida) | inexistente |
| Subgrupo | Fatia plano atual (operadora/plano) | `SubgrupoAtual*` |
| Opção / proposta | Plano cotado | `OpcaoPlano` / `OpcaoPropostaRascunho` |
| Cenário / Atribuição | Conjunto opção↔alvo | `Cenario` / `AtribuicaoPlano` / `AlvoTipo` |
| Regime copart | Classifica seções; não calcula atos | `RegimeCopartTipo` |
| Faixa ANS | Índice 0–9 | `faixa_em` / `ROTULOS_FAIXA` |
| Reajuste / Baseline / Precedência | bps; vigente\|reajustado; fatura\|tabela | campos policy/subgrupo |
| Price basis / Tipo fiscal / IOF | inclui/exclui/desconhecido; seguradora vs operadora; 238 bps | `PriceBasis` / `TipoFiscal` / `iof_bps` |
| MoneyCents / RateBasisPoints | Centavos int / taxa int | `types.py` |
| Proveniência / Confirmado | Origem + aceite humano | `ProvenienciaCampo` |
| EffectivePolicy / PolicySet | Regras efetivas / registry versionado | `policy.py` / `PolicySetRegistry` |
| Compilador / Motor / MotorResult | Rascunho→input / `calcular` / saída | `draft_compiler` / `engine.calcular` / `result.py` |
| B-01…B-08 / H-01 | Bloqueios e alerta de escala | ver §5 |
| Snapshot / Hash canônico | Congelamento + SHA-256 sem timestamps | `SnapshotCalculo` / `CAMPOS_PAYLOAD_CANONICO` |
| `confirmo_conteudo` | Atestado de revisão | `AprovarSnapshotRequest` |
| PresentationViewModel | Modelo neutro (centavos) | `presentation.py` |
| Modo faixas / beneficiário | HTML agregado / com nomes | `modo=` |
| RASCUNHO INTERNO | Banner políticas provisórias | DP-13 |
| SISCOR / Cotação PDF | Planilha base / proposta PDF | `ImportacaoSiscor*` / `ExtracaoCotacao*` |
| Família template / Maturidade | Layout reconhecido / flags técnicas | `FAMILIAS` / `avaliar_maturidade` |
| Homologação financeira | Aceite valores PDF | `extracao_financeira_homologada` = sempre False |
| Plano contratado | Registro histórico explícito | `RegistrarPlanoContratadoRequest` |
| Demo / Real | `.data/` vs `.private/` | `NEWPORT_MODO` |
| PPTX / Rede / Reembolso / Odonto | Fora do software | `AGENTS.md` |

---

## 16. ⚠️ NÃO VERIFICADO (lista consolidada)

Itens **não confirmados** ponta a ponta neste handoff a partir do commit citado — não inventar comportamento:

1. Se a UI de modalidade adesão dispara de fato o alerta DP-12 (campo existe; handler não rastreado E2E).
2. Semântica comercial exata de “copart parcial = só terapias” (afirmada em docs; motor não modela escopo de atos no draft).
3. Lista oficial ANS de nomes de faixa vs. `ROTULOS_FAIXA` — alinhamento regulatório não auditado além do código.
4. Estabilidade de schema do `payload` de snapshot entre versões de compiler/motor além das strings de versão gravadas.
5. Se `faixa_override` / `idade_valor_*` são preenchidos em algum caminho de app (existem no modelo; cálculo usa `faixa_em`).
6. Se `RegimeCopart.percentual_bps` / `escopo_procedimentos` são populados pelo mapper (draft só tem `id`+`tipo`).
7. Evolução de colunas em DBs já migrados vs. DDL inicial (`_ensure_column` / recreate).
8. Se `PriceBasisRascunho.nao_aplica` tem caminho de compilação aceito no motor.
9. Cobertura de testes para **cada** variante de mensagem B-02.
10. Comportamento de `quantidade_cotada` vs. vidas reais na reconciliação agregada.
11. Equivalência bit-a-bit de exemplos numéricos ficcionais com fixtures oficiais.
12. Interação H-01 × B-01 na UI de aprovação (alerta motor vs. confirmação extra na app).
13. Layout SISCOR de versões específicas do sistema corretora em produção além do piloto.
14. Homologação operacional com planilhas reais de clientes (status: pendente).
15. Presença de coluna `sexo` em exports reais (P9 opcional; código não ingere).
16. Fórmulas Excel cacheadas vs. fórmula viva (`data_only=True` paralelo).
17. Retenção/purge de `.xlsx` em `uploads/` (P9 menciona; purge não descrita no fluxo).
18. Resultados de aceite privado por hash neste workspace (corpus pode estar ausente).
19. Cobertura real das 12 famílias no corpus privado atual.
20. Qualidade OCR Omint/Tesseract no ambiente do operador.
21. Uso futuro do parser Bradesco (órfão hoje).
22. Paridade centavo-a-centavo com totais impressos de PDFs comerciais fora dos testes sintéticos.
23. Homologação financeira formal Newport (flag permanece false por política).
24. Processo exato de subida do uvicorn na porta 8002 neste ambiente (proxy Vite assume 8002).
25. Se `web/dist` está buildado no clone atual (mount static condicional).
26. Auth multi-usuário / `org_id` em runtime (walking skeleton local sem login).
27. Middleware `ModoRealLocalMiddleware` sob proxies não-localhost além de `cliente_eh_local`.
28. Contratos JSON campo a campo de todos os `*Response` (use modelos em `models/`).
29. Se todos os endpoints de histórico/planos-contratados têm UI completa neste commit.
30. Itens de apresentação/governança/testes marcados como ⚠️ nos arquivos `07`–`10` do pacote handoff quando a seção ficou sem corpo detalhado — tratar como “não verificado neste consolidado” e revalidar no código antes de afirmar.

---

## 17. Como uma IA externa deve usar este arquivo

- Tratar este documento como **fonte única** para discussão de produto/arquitetura sem repo.
- Em conflito: **código citado (file:line) > este consolidado > docs canônicos `docs/01–04`**.
- Não assumir PPTX, rede, reembolso, auth, cloud, ou `extracao_financeira_homologada=true`.
- Não confundir B-08 (zero vidas) com H-01 (>29 alerta).
- Não confundir `Vida` (beneficiário de saúde) com “seguro de vida” (parte 12 do entregável manual).
- Piloto = renovação 1–29 vidas, HTML interno com banner RASCUNHO INTERNO, aprovação local provisória.

*Fim do CONSOLIDADO — commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805`.*
