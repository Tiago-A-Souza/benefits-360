# AGENTS.md — Regras para agentes neste repositório

Sistema de Estudos Newport — comparativo financeiro de planos de saúde.
**Faixa inicial homologada:** 1–29 vidas (configurável; **sem teto técnico** no motor).
Estágio atual: **ETAPA 1.2.2 concluída** — motor puro + testes; próximo passo **ETAPA 2.1** (walking skeleton).

## Antes de qualquer coisa, leia (nesta ordem)
1. `docs/04-HANDOFF-IMPLEMENTACAO.md`
2. `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md`
3. `docs/03-PATCH-v0.2.1.md` — **prevalece** sobre 01/02 onde divergir.
4. `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md` — **prevalece** sobre 01/02/03/04 em **escopo de vidas**.
5. `docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md`
6. `docs/05-PLANO-ETAPA-2-VALIDACAO-OPERACIONAL.md` — direção da fatia vertical.

## Entregas concluídas
- **ETAPA 1 → 1.2.1:** motor financeiro puro (`calcular`) + suítes A–H + fixtures.
- **ETAPA 2.0:** caracterização corpus privado (`docs/06-CARACTERIZACAO-ETAPA-2.0.md`).
- **ETAPA 1.2.2:** `max_vidas_homologadas` na policy; B-08 = zero vidas; H-01 = acima da faixa homologada (alerta).

## Faça agora (quando autorizado)
- **ETAPA 2.1:** walking skeleton web (React + FastAPI + SQLite via `StudyRepository`) — ver `docs/05`.
- Não truncar vidas automaticamente; planilha SISCOR real (41 vidas) serve para importação/escala/layout, **não** como caso dourado financeiro.

## NÃO faça sem autorização
- ETAPA 2.1+ completa antes de aprovação explícita.
- Alterar regras financeiras (IOF, arredondamento, reconciliação, proveniência) sem entrega versionada separada.
- **Não mova, renomeie ou exclua** os documentos canônicos `docs/01–04`.

## Invariantes (valem sempre)
- Dinheiro em **`MoneyCents`** (inteiro). Taxas em **`RateBasisPoints`** ou decimal exato. **Nunca float.**
- `price_basis` (`inclui_iof|exclui_iof|desconhecido`) **por componente** financeiro.
- **Data de referência de idade é obrigatória** — sem default silencioso; sem ela, bloqueia (B-07).
- Motor **não decide política**: recebe `EffectivePolicy` já resolvida; `max_vidas_homologadas` vem da policy (default provisório 29).
- **Nunca corrigir idade/nascimento/faixa pelo preço**; nunca sugerir "faixa candidata".
- **Nada incorreto avança:** bloqueios B-01…B-08 + alerta H-01 (faixa homologada).
- **Nunca truncar vidas** por quantidade; H-01 alerta, não remove beneficiários.
- Sequência: cálculo → snapshot candidato (hash) → aprovação do hash → aprovado → PPTX.
- Proveniência **por campo**; minimização de dados pessoais (Patch P9).

## Dados e fixtures
- Somente dados **fictícios ou anonimizados** entram no Git.
- **Proibido** versionar CPF, endereço, telefone e qualquer PII. Documentos reais ficam **fora** do repositório.
