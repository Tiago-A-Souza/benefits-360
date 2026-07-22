# RELATÓRIO — ETAPA 2.3 (importação SISCOR)

> Conclusão: **2026-07-22** · Motor intocável · Demos `demo-12` / `demo-41` preservados  
> Base: ETAPA 2.2.6 (`19899c0`)

---

## 1. Objetivo entregue

Importar planilha SISCOR (layout piloto `.xlsx`) para uma camada **candidata** (`ImportacaoSiscorCandidata`), com conferência humana antes de aplicar vidas ao `RascunhoEstudo`. Sem cálculo automático pós-importação; sem proposta, PDF, PPTX, snapshot ou autenticação.

---

## 2. Decisões Newport aplicadas

| Decisão | Implementação |
|---------|---------------|
| Empresa = coluna **CLIENTE** (sem CNPJ) | `empresa_sugerida` na candidata; `EmpresaCliente(nome=…)` no rascunho |
| Status **ATIVO** (trim + case-insensitive) sugere inclusão | `normalizar_status`; demais → alerta `APP-SIS-005`, `incluida_sugerida=false` |
| Reimportação sempre exige decisão do usuário | `ImportacaoRequerDecisaoError` → HTTP 409; opções `substituir` ou `nova_versao` |
| Mesmo importador para estudo novo e vazio | `importar_planilha` cria rascunho vazio se ausente |
| Estudo com importação/vidas não sobrescreve silenciosamente | Bloqueio sem `modo`; fluxo explícito de reimportação |
| Camada `ImportacaoSiscorCandidata` | Linhas, alertas, confirmações, proveniência, estatísticas, correspondências sugeridas |
| `tipo_fiscal` e `regime_copart_id` opcionais pós-SISCOR | Subgrupos sugeridos sem valores fictícios; compilador `APP-IMP-001` / `APP-IMP-002` |
| Erros de arquivo vs alertas de linha | `APP-SIS-F01…F07` bloqueiam; `APP-SIS-001…009` não bloqueiam candidata |
| IDs opacos (UUID) | Sem hash de PII; SHA-256 **somente do arquivo completo** |
| Valores com `Decimal` | `siscor_importer/money.py` — nunca `float` na conversão |
| Proveniência extraída | `origem=extraido`, `confirmado=false`, `price_basis=desconhecido` |
| Confirmação em lote | Apenas linhas sem exceção; registra `confirmado_em` / `confirmado_por`; edição manual reseta confirmação |
| Dados reais separados | `.private/runtime` (uploads + `importacoes.db`); demos em `.data` |
| Sem PII em logs | Parser/serviço não registram nomes, nascimentos ou valores |
| Whitelist de colunas | CLIENTE, SEGURADO, PARENTESCO, DATA DE NASCIMENTO, PLANO, SEGURADORA, VALOR, STATUS SEGURADO |
| Fórmulas rejeitadas | Alerta `APP-SIS-F07` por célula; valor não confiado |
| Localhost para dados reais | CORS restrito a `127.0.0.1` / `localhost` (sem `--host 0.0.0.0` documentado) |

---

## 3. Arquitetura

```text
Upload .xlsx
    │
    ▼
parse_planilha_siscor()  ── erros APP-SIS-F* → aborta
    │
    ▼
ImportacaoSiscorCandidata  (SQLite .private/runtime/importacoes.db)
    │
    ├─ GET conferencia-siscor
    ├─ PATCH linha (revalidação + reset confirmação)
    └─ POST confirmar-lote
            │
            ▼
    aplicar_candidata_ao_rascunho()  → RascunhoEstudo (vidas confirmadas, sem exceção)
            │
            ▼
    compile()  → APP-IMP-001/002 até tipo fiscal e regime preenchidos
```

---

## 4. Módulos novos

| Módulo | Responsabilidade |
|--------|------------------|
| `models/siscor_import.py` | `ImportacaoSiscorCandidata`, `LinhaSiscorCandidata`, alertas, estatísticas |
| `models/responses_siscor.py` | Respostas API de importação e conferência |
| `siscor_importer/` | Parser XLSX, normalização, `Decimal`, revalidação por linha |
| `siscor_mapper/apply.py` | Aplica linhas confirmadas ao rascunho |
| `repository/importacao_siscor.py` | Persistência candidatas (versões, ativa) |
| `services/importacao_siscor.py` | Orquestração import / conferência / lote / reimportação |
| `config/paths.py` | `.data` vs `.private/runtime` |

---

## 5. API (versão 2.3.0)

| Método | Rota | Descrição |
|--------|------|-----------|
| POST | `/api/estudos` | Cria estudo vazio |
| POST | `/api/estudos/{id}/importar-siscor` | Upload multipart; query `modo`, `titulo` |
| GET | `/api/estudos/{id}/conferencia-siscor` | Conferência da candidata ativa |
| POST | `/api/estudos/{id}/conferencia-siscor/confirmar-lote` | Confirma linhas válidas e aplica rascunho |
| PATCH | `/api/estudos/{id}/conferencia-siscor/linhas/{linha_id}` | Edição / confirmação unitária |

Reimportação sem `modo` → **409** com `opcoes`: `substituir` (sem confirmações prévias) ou `nova_versao` (com confirmações).

---

## 6. Códigos de erro

### Arquivo (bloqueiam candidata)

| Código | Situação |
|--------|----------|
| APP-SIS-F01 | Arquivo vazio ou ilegível |
| APP-SIS-F02 | Não é `.xlsx` |
| APP-SIS-F03 | Sem cabeçalho |
| APP-SIS-F04 | Cabeçalhos duplicados |
| APP-SIS-F05 | Colunas obrigatórias ausentes |
| APP-SIS-F06 | Sem linhas utilizáveis |

### Linha (candidata criada; linha com exceção não entra no rascunho)

| Código | Situação |
|--------|----------|
| APP-SIS-001 | Data inválida |
| APP-SIS-002 | Nascimento futuro |
| APP-SIS-003 | Valor zerado |
| APP-SIS-004 | Plano ausente |
| APP-SIS-005 | Status desconhecido |
| APP-SIS-006 | Possível duplicidade |
| APP-SIS-007 | Nome ausente |
| APP-SIS-008 | Parentesco desconhecido |
| APP-SIS-009 | Valor ilegível |
| APP-SIS-F07 | Fórmula na célula |

### Compilador pós-importação

| Código | Situação |
|--------|----------|
| APP-IMP-001 | `tipo_fiscal` ausente no subgrupo atual |
| APP-IMP-002 | `regime_copart_id` ausente no subgrupo atual |

---

## 7. Testes

| Suíte | Casos |
|-------|-------|
| `tests/test_siscor_import.py` | Parser 12/41 vidas, 2 planos, alertas, erros de arquivo, IDs opacos, proveniência, serviço |
| `tests/test_siscor_api.py` | CRUD importação, 409 reimportação, conferência, lote, 422 pós-SISCOR, sanitização |
| Fixtures XLSX versionadas | `tests/fixtures/siscor/demo_12_vidas.xlsx`, `demo_41_vidas_2_planos.xlsx` |

**Total após 2.3:** 170 testes passando (`python -m pytest`).

Homologação privada (checklist operacional — planilha real fora do Git):

- [ ] 41 vidas encontradas
- [ ] 2 planos detectados
- [ ] Nenhuma vida truncada
- [ ] Nenhuma coluna proibida persistida
- [ ] Todas as vidas inicialmente não confirmadas
- [ ] Nenhuma PII em logs, commits ou relatório

---

## 8. Fora de escopo (ETAPA 2.4+)

- Proposta manual, PDF, PPTX, `quantidade_cotada`, snapshot
- Autenticação e multiusuário
- Merge automático na reimportação
- Confirmação de `price_basis` / IOF (decisão separada da confirmação do valor extraído)
- Coluna SEXO

---

## 9. Próximo passo

**ETAPA 2.4** — conferência UI / fluxos de revisão (quando especificada). Esta entrega para antes da 2.4.
