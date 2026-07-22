# AGENTS.md — Regras para agentes neste repositório

Sistema de Estudos Newport — comparativo financeiro de planos de saúde.
**Faixa inicial homologada:** 1–29 vidas (configurável; **sem teto técnico** no motor).
Estágio atual: **ETAPA 2.3.6 concluída** — importação SISCOR com conferência no navegador; **próximo passo ETAPA 2.4** (entrada manual da proposta).

## Antes de qualquer coisa, leia (nesta ordem)
1. `docs/04-HANDOFF-IMPLEMENTACAO.md`
2. `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md`
3. `docs/03-PATCH-v0.2.1.md` — **prevalece** sobre 01/02 onde divergir.
4. `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md` — **prevalece** sobre 01/02/03/04 em **escopo de vidas**.
5. `docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md`
6. `docs/05-PLANO-ETAPA-2-VALIDACAO-OPERACIONAL.md` — direção da fatia vertical.

## Entregas concluídas
- **ETAPA 1 → 1.2.2:** motor financeiro puro + suítes A–H + fixtures.
- **ETAPA 2.0:** caracterização corpus privado (`docs/06-CARACTERIZACAO-ETAPA-2.0.md`).
- **ETAPA 2.1:** walking skeleton (`newport_app` + `web/` + `RELATORIO-ETAPA-2.1.md`).
- **ETAPA 2.2 → 2.2.6:** compilador/mapper único + endurecimento financeiro (`RELATORIO-ETAPA-2.2.md`).
- **ETAPA 2.3 → 2.3.6:** importação SISCOR candidata, API, UI de conferência, separação `.data` / `.private/runtime` (`RELATORIO-ETAPA-2.3.md`).

## Faça agora (quando autorizado)
- **ETAPA 2.4:** entrada manual da proposta — ver `docs/05`.

## NÃO faça sem autorização
- ETAPA 2.4+ antes de aprovação explícita.
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
- **Modo demo** (`NEWPORT_MODO=demo`, default): banco e demos em `.data/`.
- **Modo real** (`NEWPORT_MODO=real`): estudos, importações e uploads em `.private/runtime/`; bind somente em `127.0.0.1`.

## Ambiente de testes
- Usar o venv do projeto: `.venv\Scripts\python.exe -m pytest`
- Dependências: `pip install -e ".[app,dev]"` dentro do `.venv`.
