# Auditoria do working tree — 2026-08-07

Estado do repositório **antes de qualquer commit**. Suíte: **331 passed** (pytest).

Legenda de risco ao reverter:
- **Baixo** — bugfix isolado ou cosmético
- **Médio** — funcionalidade visível sem teste dedicado
- **Alto** — fluxo principal quebrado ou testes falham

---

## Resumo por origem

| Grupo | Arquivos | Linhas (± diff stat) | Notas |
|-------|----------|----------------------|-------|
| Trava de confirmação (sessões anteriores) | 14 | ~741 citadas pelo operador; ~1 564 linhas tocadas nos 14 abaixo | **Não commitar em `main`** — branch separada |
| Tarefa defeitos + diagnóstico | 12+ | ~2 500 | Escopo fechado recente, testado |
| Documentação handoff | 12 | novos | Fora do escopo operacional |

---

## 1. Quatorze arquivos — fluxo de confirmação e UI correlata

### Backend / domínio

| Arquivo | O que mudou (1 frase) | Intencional? | Teste? | Risco reverter |
|---------|----------------------|--------------|--------|----------------|
| `src/newport_app/cotacao_pdf/apply.py` | `_prov_extraida` usa `confirmado=aceito` (valor presente); `_comp`/`_regime_id`/`_modalidade` ignoram `campo.confirmado`; aplica faixas/operadora sem confirmação; remove opções desmarcadas ao reaplicar; `_validade_documento` | **Destravar fluxo** — remove trava humana | `test_cotacao_apply_sem_confirmar`, `test_apply_remove_deselected` | **Alto** (2 testes + apply quebrado na UI) |
| `src/newport_app/cotacao_pdf/validation.py` | `pendencias_opcao` deixa de exigir «confirme após revisar»; só exige valor ausente ou zero faixas | **Destravar fluxo** — alinhado ao apply | Indireto via `test_apply_sem_confirmar` | **Alto** (UI bloqueia de novo) |
| `src/newport_app/cotacao_pdf/confirmacao.py` | **Novo.** Confirmação implícita ao selecionar/aplicar (`confirmar_opcao_implicita`, `confirmar_extracao_selecionadas`) | **Intencional** — substituto parcial da trava | `test_cotacao_confirmacao_implicita` | **Alto** (service importa) |
| `src/newport_app/services/extracao_cotacao.py` | Chama confirmação implícita em seleção/aplicar; edição de campo marca `confirmado=True`; remoção limpa `documentos_cotacao`; **+** log diagnóstico (misturado) | **Destravar fluxo** (+ diagnóstico acidental no mesmo diff) | `test_cotacao_confirmacao_implicita`, `test_cotacao_remover_extracao`, `test_importacao_pdf_registra_diagnostico` | **Alto** |
| `src/newport_app/adapters/motor_out.py` | Exibe `regime_coparticipacao` no plano atual do comparativo | **Intencional** — corrige lacuna de exibição | Nenhum dedicado | **Baixo** |
| `src/newport_app/cotacao_pdf/parsers/porto.py` | Operadora extraída ganha `trecho` e `estado="confirmar"` | **Intencional** — melhora rastreabilidade/evidência | Regressão PDF existente | **Baixo** |
| `src/newport_app/repository/extracao_cotacao.py` | Corrige typo `row` → `r` em list comprehension (`listar_por_estudo`) | **Bugfix acidental** | Coberto indiretamente por fluxo PDF | **Médio** (quebra listagem se revertido) |

### Frontend

| Arquivo | O que mudou (1 frase) | Intencional? | Teste? | Risco reverter |
|---------|----------------------|--------------|--------|----------------|
| `web/src/CotacaoPdfPanel.jsx` | Refatoração grande de UI; `resumirMotivosBloqueio`; menos bloqueios por `estado=revisar`; **+** upload lote e recuperação zero opções (tarefa recente, mesmo arquivo) | **Misto** — UI + destravar confirmação + tarefa | Vitest upload/prefill; regressão manual | **Alto** |
| `web/src/cotacaoPdf/utils.js` | Remove motivos «revisar/confirme» de `situacaoOpcao`; adiciona `resumirMotivosBloqueio` filtrando «confirme após revisar» | **Destravar fluxo** | Nenhum JS dedicado | **Alto** |
| `web/src/comparativo/format.js` | Exporta `classeVariacao()` para cores de variação | **Intencional** — UI comparativo | Nenhum | **Baixo** |
| `web/src/ConfigEstudo.jsx` | Redesign da etapa «Plano atual» (layout, cabeçalho, remoção de detalhes colapsáveis) | **Intencional** — UX | Nenhum | **Médio** |
| `web/src/MeusEstudos.jsx` | Redesign da lista de estudos | **Intencional** — UX | Nenhum | **Médio** |
| `web/src/SiscorPanel.jsx` | Redesign da importação SISCOR | **Intencional** — UX | Nenhum | **Médio** |
| `web/src/styles.css` | Grande expansão de tokens/classes (fluxo, comparativo, cotação, diagnóstico, recuperação) | **Intencional** — suporta redesign + tarefa | Nenhum | **Alto** (UI quebra visualmente) |

### Testes novos (fluxo confirmação)

| Arquivo | Cobertura | Depende do comportamento novo? |
|---------|-----------|-------------------------------|
| `tests/test_cotacao_apply_sem_confirmar.py` | Apply com `confirmado=False` em todos os campos ainda produz opção | **Sim — escrito para o apply relaxado** |
| `tests/test_cotacao_confirmacao_implicita.py` | Seleção/aplicação confirma campos preenchidos | **Sim — módulo `confirmacao.py`** |
| `tests/test_cotacao_remover_extracao.py` | Remoção limpa atribuições e `documentos_cotacao` | **Parcial** — remoção, não a trava em si |

---

## 2. Demais alterações (tarefa defeitos + diagnóstico)

| Arquivo | O que mudou | Teste? | Risco reverter |
|---------|-------------|--------|----------------|
| `src/newport_app/diagnostico.py` | Registrador JSONL anti-PII | `test_diagnostico.py` | Alto |
| `src/newport_app/config/paths.py` | `diretorio_dados`, `caminho_diagnostico_jsonl` | `test_diagnostico.py` | Alto |
| `src/newport_app/api/main.py` | `GET /api/diagnostico` | `test_api_diagnostico` | Alto |
| `src/newport_app/services/calculo.py` | Log bloqueios/compilação | `test_diagnostico` indireto | Médio |
| `src/newport_app/services/importacao_siscor.py` | Log erros SISCOR | Parcial | Médio |
| `src/newport_app/services/snapshot.py` | Log recusas snapshot/aprovação | Parcial | Médio |
| `src/newport_app/services/apresentacao.py` | Log apresentação recusada | Parcial | Médio |
| `src/newport_app/cotacao_pdf/parsers/omint.py` | Esqueleto quando zero opções (Opção A) | `test_regressao_omint_*` | Alto |
| `tests/test_cotacao_pdf_regressao.py` | Omint determinístico + outros | Sim | Alto |
| `tests/test_diagnostico.py` | Novo | Sim | Alto |
| `web/src/cotacaoPdf/uploadLote.js` + test | Upload lote resiliente | Vitest | Alto |
| `web/src/cotacaoPdf/prefillManual.js` + test | Prefill manual pós-extração vazia | Vitest | Alto |
| `web/src/DiagnosticoPanel.jsx` | UI diagnóstico | Manual | Médio |
| `web/src/PropostaPanel.jsx` | Manual desde extração + `_documento_meta` | Vitest prefill | Médio |
| `web/src/App.jsx`, `web/src/api.js` | Rodapé diagnóstico | Manual | Baixo |
| `web/package.json`, `package-lock.json`, `vitest.config.js` | Vitest | Vitest | Baixo |

---

## 3. Não rastreados

| Caminho | Nota |
|---------|------|
| `docs/handoff-ia/` | Documentação IA — 12 arquivos |
| `.gitattributes` | **Novo nesta auditoria** — normalização EOL |

---

## 4. `.gitattributes` e contagem `git status`

| Momento | `git status --short` | `git status -u --short` |
|---------|---------------------|-------------------------|
| **Antes** do `.gitattributes` | **39** entradas | **51** (expandido, inclui cada `docs/handoff-ia/*`) |
| **Depois** do `.gitattributes` + `git add --renormalize .` | **40** (+ `.gitattributes` untracked) | **52** |

**Fixtures JSON:** nenhum arquivo em `tests/fixtures/**/*.json` apareceu no diff após renormalização neste clone — o ruído CRLF/LF citado (73 arquivos) **não se manifestou aqui**; o `.gitattributes` fica como prevenção para clones Windows futuros.

**Nota:** `git add --renormalize` chegou a stagedar os 26 modificados; foi feito `git reset HEAD` para manter tudo unstaged até aprovação.
