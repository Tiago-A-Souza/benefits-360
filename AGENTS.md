# AGENTS.md — Regras para agentes neste repositório

Sistema de Estudos Newport — comparativo financeiro de planos de saúde (piloto, 1–29 vidas).
Estágio atual: **implementação da primeira entrega = motor financeiro puro + testes.**

## Antes de qualquer coisa, leia (nesta ordem)
1. `docs/04-HANDOFF-IMPLEMENTACAO.md`
2. `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md`
3. `docs/03-PATCH-v0.2.1.md` — **prevalece** sobre 01/02 onde divergir.
4. `docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md`

## Faça agora (primeira entrega)
- Apenas o **motor puro** (biblioteca Python) e os **testes A–H** (ver HANDOFF §9).
- Motor = função pura: `calcular(dados_tipados, effective_policy) -> resultado + validações`. Sem I/O.
- Rode os testes contra fixtures fictícias em `tests/fixtures/` (ver o README de lá).
- Ao concluir, gere `RELATORIO-IMPLEMENTACAO.md` (HANDOFF §10).

## NÃO faça nesta entrega
- Nada de **FastAPI, React, Postgres/qualquer banco, worker/jobs, PPTX, parsers de PDF, IA/LLM**.
- Não inicialize frontend nem infraestrutura.
- **Não mova, renomeie ou exclua** os documentos existentes.

## Invariantes (valem sempre)
- Dinheiro em **`MoneyCents`** (inteiro). Taxas em **`RateBasisPoints`** ou decimal exato. **Nunca float.**
- `price_basis` (`inclui_iof|exclui_iof|desconhecido`) **por componente** financeiro.
- **Data de referência de idade é obrigatória** — sem default silencioso; sem ela, bloqueia (B-07).
- Motor **não decide política**: recebe `EffectivePolicy` já resolvida; não acessa banco/arquivo.
- Tolerâncias e estratégia de arredondamento vêm da `EffectivePolicy`, não hardcoded.
- **Nunca corrigir idade/nascimento/faixa pelo preço**; nunca sugerir "faixa candidata".
- **Nada incorreto avança:** aplique os bloqueios B-01…B-08.
- Sequência: cálculo → snapshot candidato (hash) → aprovação do hash → aprovado → PPTX. Aprovação nunca antes do snapshot. (O motor só produz dados do candidato; não aprova nem persiste.)
- `ScenarioResult` consolida; `ScenarioSectionResult` é **disjunto por regime de copart**. Um rótulo nunca mistura regimes.
- Proveniência **por campo**: documento de origem + versão do extrator + origem (`manual|parser@versão|ia@versão`).
- Regras não homologadas = **decisões provisórias (DP)**. Onde falta homologação, use **escolha bloqueante por estudo**, nunca uma regra global inventada.

## Dados e fixtures
- Somente dados **fictícios ou anonimizados** entram no Git.
- **Proibido** versionar CPF, endereço, telefone e qualquer PII. Documentos reais ficam **fora** do repositório.
- Cada fixture deve declarar o **cenário** que representa e o **resultado esperado**. Ver `tests/fixtures/README.md`.
