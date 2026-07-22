# Plano ETAPA 2 — Validação operacional (fatia vertical do piloto)

> Documento aprovado como **direção de implementação**.  
> Motor financeiro: commit base `453ebb7` + **ETAPA 1.2.2** (escopo de vidas).  
> UTF-8 · Versão 1.1 · 2026-07-22.

---

## 1. Objetivo

Permitir que um analista Newport conduza, de ponta a ponta, um **estudo real de renovação simples** (faixa homologada inicial **1–29 vidas**, 1 plano atual, 1 proposta, 1 regime de copart), com:

- importação SISCOR com **minimização de dados pessoais** — **todas as vidas importadas**, sem truncamento automático;
- revisão e confirmação humana dos campos;
- proposta por **entrada manual estruturada** (sem parser PDF nesta etapa);
- chamada ao motor **sem alterar suas regras**;
- visualização do comparativo **antes** de congelar e aprovar;
- snapshot candidato autossuficiente e PPTX financeiro mínimo derivado **exclusivamente** do snapshot aprovado.

A sequência é orientada à **validação do fluxo operacional**, não à infraestrutura como primeiro passo.

---

## 2. Princípios invariantes

| Princípio | Regra |
|-----------|-------|
| **Motor — escopo de vidas (1.2.2)** | `max_vidas_homologadas` na `EffectivePolicy` (default 29); **B-08** = zero vidas; **H-01** = acima da faixa (alerta, calcula); sem teto técnico; ver `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md`. |
| **Minimização de dados pessoais** | Persistir somente o estritamente necessário ao estudo. **Proibidos:** CPF, RG, endereço, telefone, e-mail, nome da mãe, PIS e demais campos não necessários. **Permitidos quando necessários:** nome (slide) e data de nascimento (idade/faixa). Nenhum dado pessoal em logs, fixtures versionadas, documentação publicada ou mensagens de erro. |
| **Corpus real privado** | Documentos reais fora do Git; usados desde a caracterização; exportações com dados pessoais só em storage privado controlado. |
| **Interface no navegador** | Homologação e uso operacional **obrigatoriamente** via UI web. CLI apenas como ferramenta auxiliar de diagnóstico. |
| **Linguagem do usuário** | A UI traduz conceitos técnicos. Códigos internos (`B-03`, `price_basis`, `EffectivePolicy`, etc.) só em área de auditoria/detalhes. |
| **JSON não mutável** | JSON em fixtures, snapshots imutáveis e exportações controladas — **nunca** como armazenamento mutável do produto. Rascunhos via `StudyRepository` (SQLite local na 2.1). |
| **Homologação provisória** | Decisões podem ser homologadas provisoriamente pelo responsável atual; registrar perguntas pendentes para Wesley antes do piloto operacional. |
| **Confirmação SISCOR em lote** | Confirmação em massa quando coerente; exceções tratadas individualmente. |
| **Snapshot autossuficiente** | Conteúdo mínimo definido na seção 9. |
| **Commits pequenos** | Integração contínua; feature flags só para comportamento implantável que precise ficar desligado. |

---

## 3. Sequência de subentregas

```text
2.0  Caracterização privada + dicionário + wireframes
2.1  Walking skeleton (navegador): rascunho fictício → motor → comparativo
2.2  Compilador/mapper único → EstudoInput + EffectivePolicy
2.3  Importador SISCOR (whitelist + revisão humana em lote)
2.4  Entrada manual genérica da proposta
2.5  Conferência, bloqueios traduzidos e comparativo financeiro
2.6  Persistência, auditoria, organização e segurança (ambiente escolhido)
2.7  Snapshot candidato, hash e aprovação
2.8  PPTX financeiro mínimo (aceite final da ETAPA 2)
```

### Dependências

- **2.0** precede tudo.
- **2.1–2.2** provam o fluxo antes de import real e persistência definitiva.
- **2.3–2.5** constroem o fluxo operacional completo em memória/SQLite.
- **2.6** endurece após fluxo validado; decisão SQLite vs Postgres aqui.
- **2.7–2.8** fecham governança e entregável.

---

## 4. Fluxo funcional (ordem corrigida)

```text
entrada / importação
  → conferência dos campos (incl. escolhas do estudo)
  → calcular
  → visualizar comparativo                    ← checkpoint analista
  → gerar snapshot candidato
  → revisor visualiza conteúdo exato congelado
  → aprovação do hash
  → PPTX
```

**Invariante:** aprovação **nunca** ocorre antes de o revisor visualizar o resultado que será congelado (Patch P1).

---

## 5. Arquitetura mínima (2.1–2.5)

```text
┌──────────────────────────────────────────────┐
│  UI web (React mínimo) — homologação aqui    │
├──────────────────────────────────────────────┤
│  Orquestração (FastAPI)                      │
│  · import SISCOR síncrono                    │
│  · formulário proposta manual                │
│  · conferência / escolhas do estudo          │
├──────────────────────────────────────────────┤
│  draft_compiler (único)                      │
├──────────────────────────────────────────────┤
│  newport_motor.calcular()  [453ebb7]         │
├──────────────────────────────────────────────┤
│  StudyRepository (interface)                 │
│  · SQLite local (2.1)                        │
└──────────────────────────────────────────────┘
```

- **Sem** worker/job na primeira versão, salvo necessidade demonstrada por medição.
- **Sem** auth remota, storage cloud ou Postgres obrigatório antes da decisão de ambiente (2.6).
- **CLI** opcional para diagnóstico; não substitui a UI.

---

## 6. Arquitetura-alvo (pós-2.6)

```text
React (wizard + conferência + comparativo + revisor)
        │
        ▼
FastAPI (orquestração, auditoria, snapshot, renderer síncrono)
        │
   ┌────┴────┬─────────────────┐
   ▼         ▼                 ▼
Postgres   Storage privado    newport_motor (lib)
(repositório) (corpus, PPTX)
```

Transição: substituir implementação de `StudyRepository` e endurecer UI — **sem reescrever** o fluxo.

---

## 7. Decisões antes de cada subentrega

| Subentrega | Decisões | Quem homologa (provisório) |
|------------|----------|----------------------------|
| **2.0** | Acesso corpus; scorecard operadora; wireframes | Responsável projeto → Wesley (piloto) |
| **2.1** | Stack UI mínima; fixture fictícia de referência | Responsável projeto |
| **2.2** | Modelo `RascunhoEstudo` canônico | Responsável projeto |
| **2.3** | Variante SISCOR; regras inclusão; confirmação em lote | Responsável projeto → Wesley |
| **2.4** | Campos obrigatórios proposta; template operadora | Responsável projeto |
| **2.5** | Textos UI (tradução bloqueios); layout comparativo | Responsável projeto + analista |
| **2.6** | **Onde roda o piloto**; SQLite vs Postgres; backup | Newport (infra) |
| **2.7** | Papel revisor; autoaprovação piloto (DP-14) | Newport → Wesley |
| **2.8** | Template PPTX master ou provisório | Newport |

---

## 8. Comparação de persistência

| Dimensão | Local + SQLite | Local/container + Postgres | Hospedado + Postgres + storage |
|----------|----------------|------------------------------|--------------------------------|
| Tempo 2.1–2.5 | Mais rápido | Médio | Lento |
| Multi-usuário | Fraco | Bom | Bom |
| Auditoria | Limitada | Adequada | Centralizada |
| Corpus real / LGPD | Disco local | On-prem | Política cloud |
| Reversibilidade | Alta | Alta | Média |

**Processo:** SQLite via `StudyRepository` em 2.1–2.5; decisão formal na **2.6**.

---

## 9. Snapshot candidato — conteúdo mínimo

O snapshot candidato deve ser **autossuficiente** e conter:

1. **Entrada tipada** (`EstudoInput` serializado)
2. **`EffectivePolicy`** resolvida
3. **Resultado completo do motor** (`MotorResult`)
4. **Versão do motor** (commit ou tag do pacote)
5. **Versão do compilador/importadores**
6. **Data de referência de idade** usada
7. **Serialização canônica determinística** (ordem de chaves estável)
8. **Hash** calculado sobre esse conteúdo

Estados: `candidato | aprovado | superado` (Patch P1). PPTX **somente** de snapshot `aprovado`.

---

## 10. Síncrono vs assíncrono

| Operação | Inicial | Reconsiderar async quando |
|----------|---------|---------------------------|
| Import SISCOR | Síncrono | Tempo > ~5 s de forma recorrente |
| `calcular()` | Síncrono | N/A (motor puro, ms) |
| Snapshot | Síncrono | N/A |
| PPTX | Síncrono | Template > ~10 s ou fila multi-estudo |

---

## 11. Critério de aceite da ETAPA 2

Caso real privado de renovação simples (faixa homologada inicial 1–29 vidas; estudos maiores calculam com **H-01**):

1. Importa posição cadastral SISCOR **integralmente** (ex.: 41 vidas — sem truncamento).
2. Permite corrigir e confirmar informações (SISCOR em lote + exceções).
3. Recebe 1 proposta por entrada manual.
4. Resolve escolhas do estudo (equivalentes a B-07) na UI traduzida.
5. Calcula sem bloqueios financeiros abertos.
6. Apresenta atual, proposta, diferenças mensal e anual.
7. Gera snapshot candidato autossuficiente.
8. Revisor visualiza candidato exato e aprova hash auditavelmente.
9. Gera PPTX cujos valores coincidem com o snapshot; marca rascunho; testes semânticos.

---

## 12. Rollback por subentrega

| Subentrega | Rollback |
|------------|----------|
| 2.0 | Descartar artefatos de caracterização |
| 2.1–2.2 | Remover skeleton; motor intacto |
| 2.3 | Desligar import; manual puro |
| 2.4 | Formulário genérico |
| 2.5 | Comparativo opcional |
| 2.6 | Export SQLite; trocar impl. repository |
| 2.7 | Não aprovar; recalcular → novo candidato |
| 2.8 | Manter snapshot aprovado sem PPTX |

---

## 13. Fora da ETAPA 2

- Alterações de regra no motor (salvo hotfix versionado separado).
- Parsers PDF automatizados e IA extratora.
- Segunda operadora; seguro novo; 2+ planos/regimes mistos (ETAPA 3+).
- Worker/fila sem necessidade demonstrada.
- Auth SSO, cloud e storage remoto antes da decisão 2.6.

---

## 14. Referências

- `docs/04-HANDOFF-IMPLEMENTACAO.md`
- `docs/03-PATCH-v0.2.1.md` (P1, P9, P10, §D, §E)
- `docs/06-CARACTERIZACAO-ETAPA-2.0.md` — resultado da caracterização
- `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md`
- Motor: `453ebb7` + ETAPA 1.2.2
