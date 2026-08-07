# 08 — Testes e qualidade

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

Documento operacional para IA sem acesso ao código. Suítes A–H, como rodar, inventário de 326 testes, fixtures, marcador `private_corpus`, lacunas e hotfixes.

---

## Como rodar

```text
.venv\Scripts\python.exe -m pytest
```

Fonte: `AGENTS.md:50-51`. Coleta verificada neste workspace: **326 tests collected**.

Para excluir corpus privado (quando o ambiente não tiver PDFs fora do Git):

```text
.venv\Scripts\python.exe -m pytest -m "not private_corpus"
```

Marcador registrado em `pyproject.toml:36-37`: `private_corpus: testes que dependem de PDFs reais fora do Git`.

---

## Suítes A–H (motor puro — ETAPA 1)

Fonte de escopo e contagens históricas: `RELATORIO-IMPLEMENTACAO.md:69-90`, `197-208`. Arquivos atuais sob `tests/test_suite_*.py`.

| Suíte | Arquivo | Contagem (coleta) | Cobre | Deliberadamente **não** cobre |
|-------|---------|-------------------|-------|-------------------------------|
| **A** — Tipos/aritmética | `test_suite_a_types.py` | 7 | `MoneyCents`, bps IOF 238, half-up, ordem `por_vida_entao_soma` (`test_suite_a_types.py:1-40`) | Compilação de rascunho, API, UI, PDF |
| **B** — Reconciliação | `test_suite_b_reconciliation.py` | 5 | B-02 totais/subtotais; total ausente; subtotal zero (`RELATORIO` §2; docstring suíte B) | Rede, reembolso, PPTX; B-01 (app) |
| **C** — IOF / price_basis | `test_suite_c_iof_price_basis.py` | 3 | Seguradora com IOF; operadora sem; `desconhecido` bloqueia | Parsers PDF; confirmação de UI |
| **D** — Atual/reajuste | `test_suite_d_atual_reajuste.py` | 2 | Vigente/reajustado/diferenças; baseline vigente | Seguro novo E2E; reajuste tabelado CSV |
| **E** — Idade/faixa/precedência | `test_suite_e_idade_faixa.py` | 6 | `faixa_em`, B-07 data ausente, B-04 idade, precedência fatura×tabela (DP-01/DP-08) | `faixa_override` (campo não lido pelo cálculo) |
| **F** — Cenários/seções | `test_suite_f_cenarios_secoes.py` | 2 | Seções disjuntas por regime; B-06 atribuição ausente | Sync automático de cenários da app (`cenarios_sync`) |
| **G** — Pureza/policy | `test_suite_g_pureza_policy.py` | 3 | Determinismo; políticas embutidas; tolerâncias afetam resultado | Persistência SQLite; PolicySet em tabelas SQL |
| **H** — Formas/escala/proveniência | `test_suite_h_formas_escala.py` | 6 | Escala 1–29; H-01 acima do max; copart sem/parcial/%; 2 planos; proveniência; B-03 IA | B-08 antigo “>29 bloqueia” (docs desatualizados); `quantidade_cotada` vs vidas |

Extensões motor documentadas no mesmo relatório (não são A–H, mas complementam):

| Extensão | Arquivo | Contagem | Foco |
|----------|---------|----------|------|
| 1.1.1 | `test_suite_111_correcoes.py` | 9 | Correções piloto |
| 1.2 | `test_suite_12_endurecimento.py` | 19 | Endurecimento entrada/saída |
| 1.2.1 | `test_suite_121_subtotais.py` | 8 | Subtotais / B-03 |
| 1.2.2 | `test_suite_122_escopo_vidas.py` | 7 | Escopo vidas / B-08 zero / H-01 |
| Fixtures JSON | `test_fixtures_json.py` | 16 | Oráculos `expected.json` |

`RELATORIO-IMPLEMENTACAO.md:208` confirma que a entrega do motor **não** inclui FastAPI, React, Postgres, worker, PPTX, parser PDF ou IA — essas camadas têm suítes próprias posteriores.

---

## 326 testes coletados (por arquivo)

Contagens via `pytest --collect-only` (parametrizações incluídas):

| # | Arquivo |
|---|---------|
| 31 | `tests/test_draft_compiler_paridade.py` |
| 19 | `tests/test_siscor_import.py` |
| 19 | `tests/test_suite_12_endurecimento.py` |
| 17 | `tests/test_etapa_281.py` |
| 16 | `tests/test_fixtures_json.py` |
| 16 | `tests/test_siscor_236.py` |
| 13 | `tests/test_apresentacao_linguagem.py` |
| 12 | `tests/test_seguranca_modo.py` |
| 12 | `tests/test_snapshot_apresentacao.py` |
| 11 | `tests/test_cotacao_pdf_regressao.py` |
| 9 | `tests/test_cenarios_sync.py` |
| 9 | `tests/test_siscor_api.py` |
| 9 | `tests/test_suite_111_correcoes.py` |
| 9 | `tests/test_template_families.py` |
| 8 | `tests/test_api_walking_skeleton.py` |
| 8 | `tests/test_hotfix_303.py` |
| 8 | `tests/test_suite_121_subtotais.py` |
| 7 | `tests/test_comparativo_confirmacao.py` |
| 7 | `tests/test_cotacao_pdf_anistia.py` |
| 7 | `tests/test_hotfix_302.py` |
| 7 | `tests/test_suite_122_escopo_vidas.py` |
| 7 | `tests/test_suite_a_types.py` |
| 6 | `tests/test_hotfix_291.py` |
| 6 | `tests/test_suite_e_idade_faixa.py` |
| 6 | `tests/test_suite_h_formas_escala.py` |
| 5 | `tests/test_cotacao_pdf.py` |
| 5 | `tests/test_suite_b_reconciliation.py` |
| 4 | `tests/test_comparativo_experiencia.py` |
| 4 | `tests/test_coords_extract_nomes.py` |
| 4 | `tests/test_corpus_aceite_privado.py` |
| 3 | `tests/test_comparativo_multiplas_propostas.py` |
| 3 | `tests/test_fluxo_245.py` |
| 3 | `tests/test_hotfix_301.py` |
| 3 | `tests/test_suite_c_iof_price_basis.py` |
| 3 | `tests/test_suite_g_pureza_policy.py` |
| 2 | `tests/test_cotacao_confirmacao_implicita.py` |
| 2 | `tests/test_etapa_282.py` |
| 2 | `tests/test_suite_d_atual_reajuste.py` |
| 2 | `tests/test_suite_f_cenarios_secoes.py` |
| 1 | `tests/test_cotacao_apply_sem_confirmar.py` |
| 1 | `tests/test_cotacao_remover_extracao.py` |

**Total: 326.**

---

## Fixtures (`tests/fixtures/`)

Diretórios presentes:

| Diretório | Uso típico |
|-----------|------------|
| `arredondamento_soma_entao_aplica`, `copart_parcial_1vida`, `copart_percentual_1vida`, `divergencia_*`, `mesma_opcao_dois_subgrupos`, `novo_1vida_sem_copart`, `price_basis_desconhecido`, `primeira_parcela_custos_unicos`, `renovacao_*`, `seguradora_tabela_inclui_iof`, `total_recorrente_ausente` | Casos motor / oráculos JSON (`RELATORIO-IMPLEMENTACAO.md:142-147`; gerador `tests/generate_fixtures.py`) |
| `rascunhos/` | Paridade compilador (`demo_12`, `demo_41`) — `test_draft_compiler_paridade.py` |
| `siscor/` | Planilhas / builders XLSX |
| `cotacao_pdf/` | Hashes de aceite / PDFs sintéticos de regressão |

Oráculo independente: `tests/oracle_independente.py` (`RELATORIO-IMPLEMENTACAO.md:144`).

---

## Marcador `private_corpus`

- Definição: `pyproject.toml:36-37`.
- Usado em: `test_corpus_aceite_privado.py`, `test_cotacao_pdf.py`, `test_cotacao_pdf_anistia.py`, `test_cotacao_pdf_regressao.py`, `test_template_families.py`, `test_hotfix_303.py` (trechos que leem corpus em disco).
- Comportamento típico: `pytest.skip` se diretório/PDF privado ausente (ex.: `test_hotfix_303.py:30-39`).

---

## Lacunas de cobertura conhecidas

| Lacuna | Evidência |
|--------|-----------|
| **Rede** (Básico/Intermediário/Gerencial/Diretoria) | Fora de escopo; sem testes de módulo inexistente — `docs/04-HANDOFF-IMPLEMENTACAO.md:19` |
| **Reembolso / procedimentos reembolsáveis** | Idem |
| **PPTX** | Não implementado; sem suíte — `AGENTS.md:24`; `RELATORIO-IMPLEMENTACAO.md:208` |
| **Seguro novo E2E** | Motor tem formato `NOVO`; jornada/autorização de produção exclui seguro novo — `AGENTS.md:25-28`; sem suíte E2E dedicada de jornada “novo” |
| **Família Bradesco não registrada em `FAMILIAS`** | Parser existe (`parsers/bradesco.py`); `_registrar_familias` importa amil/omint/porto/sulamerica **sem** bradesco (`template_families.py:78-210`) |
| **`quantidade_cotada` vs vidas atribuídas** | Motor **não verifica** — `RELATORIO-IMPLEMENTACAO.md:65`, `193`; `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md:68` |

---

## Hotfixes — arquivos de teste 291 / 301 / 302 / 303

| Arquivo | Contagem | Escopo (docstring / commits) |
|---------|----------|------------------------------|
| `tests/test_hotfix_291.py` | 6 | HOTFIX **2.9.1** — SulAmérica: extração, validação tarifária, sequência suspeita (`test_hotfix_291.py:1`) |
| `tests/test_hotfix_301.py` | 3 | HOTFIX **3.0.1** — migração corretiva de participação + confirmação SISCOR idempotente (`test_hotfix_301.py:1`) |
| `tests/test_hotfix_302.py` | 7 | HOTFIX **3.0.2** — herança IOF SISCOR + pendências por etapa (`test_hotfix_302.py:1`) |
| `tests/test_hotfix_303.py` | 8 | HOTFIX **3.0.3** — extração Porto, referência SISCOR, fluxo de revisão; parte `private_corpus` (`test_hotfix_303.py:1`) |

Commits correspondentes no log: `cc9e127` (3.0.1), `3b5ba5d` (3.0.2), `a5121e7` (3.0.3); `2f1b981` (HOTFIX 2.9.1).

---

## ⚠️ NÃO VERIFICADO

1. Quantos testes `private_corpus` passam neste workspace (dependem de `.private/` ausente do Git).
2. Cobertura de linha/% por pacote (não gerada neste handoff; só inventário `--collect-only`).
3. Se `test_suite_h` nome `test_b08_mais_de_29_vidas` ainda confunde leitores de relatório externo (asserção é H-01).
4. Tempo de execução completo da suíte 326 neste ambiente (não medido aqui).
