# RELATÓRIO — ETAPA 2.2 (compilador/mapper único)

> Conclusão: **2026-07-22** · Motor intocável · API/UI demos preservados  
> Commit base walking skeleton: `3341b87` (ETAPA 2.1 aprovada)

---

## 1. Objetivo entregue

Centralizar a tradução **RascunhoEstudo v1 → EstudoInput + EffectivePolicy** no módulo `draft_compiler`, com:

- schema v1 compatível com etapas 2.3, 2.4 e 2.8 (campos reservados/opcionais);
- separação **escolhas do analista** vs **PolicySet administrativo**;
- compilação estrita para cálculo; persistência de rascunhos incompletos;
- testes de **paridade** com rascunhos nativos da aplicação.

---

## 2. Subentregas

| Subentrega | Entrega | Status |
|------------|---------|--------|
| **2.2.1** | `RascunhoEstudo` v1, `ResultadoCompilacao`, `PolicySetRegistry` | Concluída |
| **2.2.2** | `draft_compiler` (estrutural + mapper + `compile`) | Concluída |
| **2.2.3** | Seeds migrados + fixtures `tests/fixtures/rascunhos/` + testes paridade | Concluída |
| **2.2.4** | `CalculoService`, API (PUT salvar, 422 calcular), SQLite migrado | Concluída |
| **2.2.5** | Testes de paridade + este relatório | Concluída |
| **2.2.6** | Endurecimento contrato financeiro, fixtures integrais, sanitização API | Concluída |

---

## 3. Arquitetura

```text
RascunhoEstudo v1 (SQLite JSON provisório)
        │
        ├─ salvar → validar_estrutura() [rejeita corrupção estrutural]
        │
        └─ calcular → compile() estrito
                ├─ PolicySetRegistry.resolve(policy_set_versao)
                ├─ mapear_estudo_input()
                └─ mapear_effective_policy(escolhas + PolicySet)
                        │
                        ▼
                newport_motor.calcular()  [intocável]
```

**Único ponto de montagem** de `EstudoInput` e `EffectivePolicy`: `newport_app.draft_compiler.compile()`.

---

## 4. RascunhoEstudo v1 — resumo do schema

| Grupo | Campos principais | Obrigatório na 2.2 |
|-------|-------------------|---------------------|
| Metadados | `rascunho_versao`, `policy_set_versao`, `id`, `titulo`, `formato` | Sim |
| Cliente | `empresa_cliente.nome` (sem CNPJ) | Demos: `Empresa Demonstração Ltda.` |
| Vidas | `nome`, `nascimento`, `parentesco`, motivos, `valor_fatura` por componente | Demos: mínimo atual |
| Plano atual | `subgrupos_atuais[]` com `acomodacao`, `modalidade`, `price_basis` por faixa | Sim (demos) |
| Proposta | `opcoes_proposta[]` + componentes financeiros desagregados | Sim (demos) |
| Cotação | `documentos_cotacao[]`, `validade_oficial`, `vigencia_pretendida` | Reservado (vazio) |
| Escolhas | `data_referencia_idade`, `baseline_escolhido`, `precedencia_atual_vida` com `confirmado` | Confirmadas nos demos |
| PPTX | `metadados_pptx` (sem `marca_rascunho` editável) | Opcional |
| Observações | `observacoes` | Opcional |

**Modalidade:** `adesao` | `compulsorio` | `desconhecido`.

**Price basis no rascunho:** `inclui_iof` | `exclui_iof` | `desconhecido` | `nao_aplica` (somente `tipo_fiscal=operadora` → mapeia para `exclui_iof` no motor).

**Sem defaults silenciosos (2.2.6):** `rascunho_versao`, `tipo_fiscal`, `price_basis` de faixa e `proveniencia.confirmado` são explícitos nos seeds e exigidos pelo compilador para valores utilizados no cálculo.

---

## 5.1 Subentrega 2.2.6 — endurecimento

| Correção | Implementação |
|----------|---------------|
| Contrato sem defaults silenciosos | `rascunho_versao` obrigatória; `tipo_fiscal` explícito; `price_basis` de faixa obrigatório; proveniência nasce `confirmado=false` |
| Validação financeira estrita | `finance_validation.py`: centavos, basis conhecido, proveniência confirmada |
| Custos únicos | Zero explícito permitido; `centavos=None` → `APP-FIN-003` |
| `quantidade_cotada` | `int \| None`; zero explícito vs ausente; proposta com `None` → `APP-QTD-001` |
| Documentos de cotação | Mapeados para `EstudoInput.documentos`; `pendente` → `APP-DOC-001` na proposta vinculada |
| Fixtures integrais | `rascunho.json`, `expected_estudo_input.json`, `expected_policy.json`, `expected_motor_result.json` |
| H-01 na UI | `motor_out` usa `MotorResult.politicas_efetivas`, não reconsulta registry |
| Erros Pydantic | Handler sanitizado (`APP-REQ-001`); sem `input` bruto, nomes ou valores |
| `motor_in.py` | Removido — compilador é o único caminho |

`compiler_versao`: **2.2.6**

---

## 5. Decisões Newport aplicadas

| # | Decisão | Implementação |
|---|---------|---------------|
| D-1 | `policy_set_versao = "v2026.07-provisoria"` | `PolicySetRegistry`; falha `APP-POL-001` se irresolvível |
| D-2 | Sem sugestões globais de baseline/precedência | `CampoConfirmavel*` só com `valor` + `confirmado`; demos explicitamente confirmados |
| D-3 | `nao_aplica` explícito no rascunho | Erro `APP-BAS-001` em seguradora |
| D-4 | Empresa fictícia nos demos | `Empresa Demonstração Ltda.` |
| — | Modalidade adesão/compulsório | Enum `ModalidadeRascunho` |
| — | Marca PPTX não editável | Removida de `MetadadosPptxRascunho` |
| — | Salvar vs estrutural | Incompleto OK; duplicata/referência inválida → 400 no PUT |
| — | Avisos contextuais | Validade só com documento vinculado (`APP-AVI-001`) |
| — | Sem modo `preview` | Apenas compilação estrita |

---

## 6. Migrações realizadas

### 6.1 Seeds `demo-12` / `demo-41` (atualizado 2.2.6)

- `rascunho_versao: "1.0"` e `policy_set_versao: "v2026.07-provisoria"` explícitos.
- `escolhas` com `CampoConfirmavel*` e `confirmado: true`.
- `tipo_fiscal: "seguradora"` explícito em subgrupo e proposta.
- Faixas com `price_basis`, `proveniencia.confirmado: true` e `quantidade_cotada` explícita na proposta (`0`).
- Tabela atual com `quantidade_cotada: null` (não exigida para compilação).
- `empresa_cliente`: `Empresa Demonstração Ltda.`

### 6.2 SQLite (provisório — endurecimento na ETAPA 2.6)

- Colunas novas via `ALTER TABLE`: `rascunho_versao`, `policy_set_versao`.
- Payload JSON continua na coluna `payload`.
- Comentário no código do repositório registra provisoriedade.

### 6.3 API

- **PUT** `/api/estudos/{id}` — salva rascunho (400 se estruturalmente inválido).
- **POST** `/api/estudos/{id}/calcular` — **422** se não compilável (escolhas pendentes, policy ausente, etc.).
- Rotas GET existentes inalteradas na forma pública.

---

## 7. Testes

| Suíte | Escopo | Casos | Resultado |
|-------|--------|-------|-----------|
| Motor + fixtures JSON | Motor puro (`tests/fixtures/renovacao_*`) | 93 | Pass |
| API walking skeleton + apresentação | Rotas HTTP, linguagem UI, integração demos | 18 | Pass |
| **Paridade integral compilador** | `rascunho.json` → compilação → `MotorResult` completo | 33 | Pass |
| **Total** | | **144** | **Pass** |

### 7.1 Paridade integral (não resumo)

Fixtures em `tests/fixtures/rascunhos/demo_12/` e `demo_41/`:

- comparação **integral** de `EstudoInput`, `EffectivePolicy` e `MotorResult`;
- teste anti-deriva: seeds Python ≡ `rascunho.json`.

### 7.2 Testes de endurecimento 2.2.6 (amostra)

- `price_basis` / proveniência ausentes ou não confirmados
- custo zero explícito vs custo sem valor
- `quantidade_cotada` zero vs `null` na proposta
- documento vinculado no `EstudoInput`; documento `pendente` bloqueia
- erro Pydantic sanitizado sem PII
- H-01 usa `politicas_efetivas` do motor
- `rascunho_versao` ausente rejeitada

### 7.3 Testes de API

Walking skeleton (`test_api_walking_skeleton.py`) e apresentação (`test_apresentacao_linguagem.py`) validam contrato HTTP e experiência dos demos — **não** substituem a paridade integral do compilador.

---

## 8. O que não foi feito (conforme escopo)

- Importação SISCOR (2.3)
- Entrada manual de proposta real (2.4)
- UI de novos campos
- Resolução de correspondência `quantidade_cotada` vs população (decisão 2.4/2.5)
- Snapshot / PPTX (2.7–2.8)
- Persistência relacional definitiva (2.6)
- Alteração do motor financeiro

---

## 9. Próximo passo

**ETAPA 2.3** — importador SISCOR (whitelist + revisão humana em lote), sobre o schema v1 e o compilador já homologado.

**Não iniciar 2.3** até aprovação explícita.
