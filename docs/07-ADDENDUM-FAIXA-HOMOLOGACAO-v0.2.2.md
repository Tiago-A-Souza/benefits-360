# Addendum v0.2.2 — Faixa homologada de vidas

> Complementa `docs/02`, `docs/03` e `docs/04` **sem alterá-los**.  
> Onde este addendum tratar escopo de vidas, **prevalece** sobre menções a “1–29 vidas” como limite técnico.  
> UTF-8 · 2026-07-22 · Implementado na ETAPA 1.2.2.

---

## 1. Problema

A v0.2 tratava **1–29 vidas** simultaneamente como:

- escopo comercial inicial de homologação Newport; e
- **bloqueio técnico permanente** no motor (`B-08` bloqueante para `count > 29`).

Isso impedia calcular estudos reais com mais beneficiários (ex.: planilha SISCOR com 41 vidas) e incentivava truncamento operacional — comportamento rejeitado pelo produto.

---

## 2. Decisão

| Conceito | Definição |
|----------|-----------|
| **Faixa homologada operacional** | Intervalo **1–29 vidas** como **primeiro escopo comercial** de homologação Newport — **não** capacidade técnica máxima do sistema. |
| **Capacidade técnica** | **Sem teto** no motor nesta versão. Eventuais limites de infraestrutura serão definidos na **camada de aplicação**, com base em medições. |
| **Limite comercial por operadora** | Metadado de template/proposta (camada app) — fora do motor. |

---

## 3. Comportamento no motor (ETAPA 1.2.2)

### `EffectivePolicy.max_vidas_homologadas`

- Tipo: `int | None`
- Default provisório: **`29`**
- `None` → não emitir advertência por quantidade
- Valor embutido em `politicas_efetivas` / snapshot

### Validações

| Código | Condição | Severidade | Impede cálculo? |
|--------|----------|------------|-----------------|
| **B-08** | `vidas_incluidas == 0` | Bloqueante | **Sim** |
| **H-01** | `count > max_vidas_homologadas` (quando definido) | **Alerta** | **Não** |

**B-08 deixa de significar “mais de 29 vidas”.**

### Regras invariantes

- **Nunca** truncar ou excluir vidas automaticamente por quantidade.
- Acima da faixa homologada: cálculo permitido; UI informa revisão adicional; **aprovação futura** exige confirmação do revisor (camada app — B-01 estendido).
- Material para cliente **pode** ser gerado após revisão e homologação formal — H-01 não é veto permanente.

---

## 4. Impacto nos documentos anteriores

| Documento | Texto anterior (resumo) | Leitura corrigida |
|-----------|-------------------------|-------------------|
| Patch §C B-08 | Vidas > 29 bloqueante | B-08 = zero vidas; >29 → **H-01 alerta** |
| HANDOFF §2 | “1–29 vidas” no escopo | Faixa **inicial homologada**, não teto técnico |
| DP-09 / inclusão | B-08 via contagem | B-08 só para zero vidas; H-01 para faixa |

Homologação formal deste addendum por Wesley permanece pendente (W-11).

---

## 5. Análise separada — `quantidade_cotada`

**Fora do escopo da 1.2.2.** O motor **não verifica** se as quantidades por faixa informadas na cotação correspondem às vidas atribuídas ao plano. Tratar em etapa futura (compilador/reconciliação/UI), sem alterar regras financeiras nesta entrega.

---

## 6. Referência de implementação

- Commit ETAPA 1.2.2
- Suíte `tests/test_suite_122_escopo_vidas.py`
- Campo `EffectivePolicy.max_vidas_homologadas`
