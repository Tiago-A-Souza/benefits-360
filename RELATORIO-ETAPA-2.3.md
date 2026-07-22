# RELATÓRIO — ETAPA 2.3 (importação SISCOR)

> Atualizado: **2026-07-22** · Subentrega **2.3.6** · Motor intocável  
> **Status:** implementação técnica concluída; **homologação privada ainda pendente**

---

## 1. Objetivo

Importar planilha SISCOR (layout piloto `.xlsx`) para camada **candidata** (`ImportacaoSiscorCandidata`), conferir no navegador e aplicar vidas confirmadas ao `RascunhoEstudo` — sem proposta manual, PDF, PPTX, snapshot ou autenticação.

---

## 2. Subentregas

| Subentrega | Entrega | Status |
|------------|---------|--------|
| 2.3.1 | Modelos candidata + campos opcionais pós-SISCOR | Concluída |
| 2.3.2 | Parser XLSX, Decimal, alertas por linha | Concluída |
| 2.3.3 | Repositório, serviço, apply ao rascunho | Concluída |
| 2.3.4 | Rotas API importação/conferência | Concluída |
| 2.3.5 | Fixtures XLSX sintéticas + testes iniciais | Concluída |
| **2.3.6** | UI SISCOR, separação de dados, endurecimento, reimportação segura | Concluída |

---

## 3. UI no navegador (2.3.6)

Abas em `web/src/App.jsx`:

- **Importação SISCOR** (`SiscorPanel.jsx`): criar/selecionar estudo, upload XLSX, estatísticas (vidas/planos/exceções), tabela de conferência, edição por linha, exclusão com motivo, confirmação individual ou em lote, diálogo de reimportação (`substituir` / `nova_versao`).
- **Comparativo**: fluxo demo existente (sem formulário de proposta).

Dev: `npm run dev` em `web/` + API em `127.0.0.1:8000`. Integrado: `npm run build` + FastAPI serve `web/dist/`.

---

## 4. Separação de dados (2.3.6)

| Modo | Variável | Banco estudos | Importações | Uploads |
|------|----------|---------------|-------------|---------|
| Demo (default) | `NEWPORT_MODO=demo` | `.data/newport_app.db` | `.data/importacoes_demo.db` | `.data/uploads_demo/` |
| Real | `NEWPORT_MODO=real` | `.private/runtime/estudos.db` | `.private/runtime/importacoes.db` | `.private/runtime/uploads/` |

Modo real exige bind local (`NEWPORT_BIND_HOST=127.0.0.1`). Demos seedados apenas em modo demo.

Testes: `tests/test_siscor_236.py` (`test_modo_demo_usa_data_dir`, `test_modo_real_usa_private_runtime`, `test_estudo_real_nao_grava_em_data`).

---

## 5. Endurecimentos 2.3.6

| Correção | Implementação |
|----------|---------------|
| Exceções por linha | Nascimento, parentesco, plano, operadora (`APP-SIS-010`), valor, status ausentes/inválidos; negativo (`APP-SIS-012`) |
| Linha incompleta | Não confirmável (`LinhaIncompletaConfirmacaoError` → HTTP 422) |
| Edição manual | Histórico `EdicaoManualSiscor`; reseta confirmação; valor ausente pode ser informado; plano remonta subgrupos; duplicidades recalculadas |
| Exclusão | Exige motivo (`ExclusaoSemMotivoError`) |
| Fórmulas | Leitura dual `data_only` + detecção `data_type=f`; teste com célula `=850+1` |
| Duplicidades | Todas as ocorrências marcadas (`APP-SIS-006`) |
| Reimportação segura | Parse antes de persistir; inválida não desativa anterior; `modo` só `substituir`/`nova_versao`; sem arquivo órfão |
| Documento SISCOR | `documentos_siscor[]` no rascunho; mapeado para `EstudoInput.documentos` (evita B-05) |
| Upload | Limite 10 MiB (`NEWPORT_UPLOAD_MAX_BYTES`); HTTP 413 sem PII |

---

## 6. API (versão 2.3.6)

| Método | Rota |
|--------|------|
| GET | `/api/config` |
| POST | `/api/estudos` |
| POST | `/api/estudos/{id}/importar-siscor` |
| GET | `/api/estudos/{id}/conferencia-siscor` |
| POST | `/api/estudos/{id}/conferencia-siscor/confirmar-lote` |
| PATCH | `/api/estudos/{id}/conferencia-siscor/linhas/{linha_id}` |

---

## 7. Testes

| Suíte | Foco |
|-------|------|
| `tests/test_siscor_import.py` | Parser e serviço base |
| `tests/test_siscor_api.py` | Contrato HTTP |
| `tests/test_siscor_236.py` | Correções 2.3.6 |

**Comando (venv do projeto):**

```powershell
.venv\Scripts\python.exe -m pytest
```

**Resultado:** **186 testes passando** (2026-07-22).

---

## 8. Homologação privada

Checklist operacional com planilha real (fora do Git) — **ainda não executada nesta entrega**:

- [ ] 41 vidas encontradas
- [ ] 2 planos detectados
- [ ] Nenhuma vida truncada
- [ ] Nenhuma coluna proibida persistida
- [ ] Todas as vidas inicialmente não confirmadas
- [ ] Nenhuma PII em logs, commits ou relatório

---

## 9. Próximo passo

**ETAPA 2.4 — entrada manual da proposta** (conforme `docs/05-PLANO-ETAPA-2-VALIDACAO-OPERACIONAL.md`). Não iniciada.

Fora de escopo desta etapa: PDF, PPTX, snapshot, autenticação, merge automático na reimportação, confirmação de IOF separada do valor extraído.
