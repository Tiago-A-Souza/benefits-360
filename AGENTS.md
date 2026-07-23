# AGENTS.md — Regras para agentes neste repositório

Sistema de Estudos Newport — comparativo financeiro de planos de saúde.
**Faixa inicial homologada:** 1–29 vidas (configurável; **sem teto técnico** no motor).
Estágio atual: **ETAPA 2.8.1 concluída** — persistência histórica longitudinal, snapshot/aprovação e apresentação HTML autocontida.

## Antes de qualquer coisa, leia (nesta ordem)
1. `docs/04-HANDOFF-IMPLEMENTACAO.md`
2. `docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md`
3. `docs/03-PATCH-v0.2.1.md` — **prevalece** sobre 01/02 onde divergir.
4. `docs/07-ADDENDUM-FAIXA-HOMOLOGACAO-v0.2.2.md` — **prevalece** sobre 01/02/03/04 em **escopo de vidas**.
5. `docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md`
6. `docs/05-PLANO-ETAPA-2-VALIDACAO-OPERACIONAL.md` — direção da fatia vertical.

## Entregas concluídas
- **ETAPA 1 → 1.2.2:** motor financeiro puro + suítes A–H + fixtures.
- **ETAPA 2.0–2.5.6:** walking skeleton, compilador, SISCOR, PDF, conferência operacional.
- **ETAPA 2.6:** persistência histórica SQLite relacional + migração segura com backup.
- **ETAPA 2.7:** snapshot candidato (hash SHA-256 determinístico) + aprovação local provisória.
- **ETAPA 2.8:** `PresentationViewModel` → renderer HTML autocontido (modos faixas e beneficiário).
- **ETAPA 2.8.1:** correções consolidadas — centavos no ViewModel, múltiplas propostas via motor, histórico longitudinal (clientes/ciclos/beneficiários), UI histórica.

## Próximo passo (quando autorizado)
- **Renderer PPTX/PDF** alimentado pelo mesmo `PresentationViewModel` (não implementado).
- Autenticação corporativa, link público, seguro novo.

## NÃO faça sem autorização
- PowerPoint/PDF de produção, autenticação, cloud, link público ou seguro novo.
- Alterar regras financeiras do motor (IOF, arredondamento, reconciliação) sem entrega versionada separada.
- **Não mova, renomeie ou exclua** os documentos canônicos `docs/01–04`.

## Invariantes (valem sempre)
- Dinheiro em **`MoneyCents`** (inteiro). Taxas em **`RateBasisPoints`** ou decimal exato. **Nunca float.**
- `PresentationViewModel` transporta **centavos**; formatação `R$` **somente no renderer HTML**.
- Hash de snapshot = conteúdo **canônico determinístico** (sem timestamps).
- Aprovação local: campo explícito `auto_aprovacao`; justificativa obrigatória se true.
- Beneficiários **nunca** vinculados silenciosamente — sugestão exige confirmação na UI.
- Registrar plano contratado = **ação explícita**; nunca automática após aprovação.
- Rascunho JSON = transitório; histórico aprovado persiste nas tabelas relacionais.
- Sequência: cálculo → snapshot candidato (hash) → revisão → aprovação → apresentação HTML.
- HTML do cliente **sem** hashes, IDs técnicos ou metadados de auditoria.
- Motor **intocável** — recálculo por proposta na apresentação usa motor existente, sem alterar regras.

## Dados e fixtures
- Somente dados **fictícios ou anonimizados** entram no Git.
- **Proibido** versionar CPF, endereço, telefone e qualquer PII.
- **Modo demo** (`NEWPORT_MODO=demo`, default): banco e demos em `.data/`.
- **Modo real** (`NEWPORT_MODO=real`): estudos, importações, uploads e entregáveis em `.private/runtime/`.

## Ambiente de testes
- Usar o venv: `.venv\Scripts\python.exe -m pytest`
- Testes 2.8.1: `tests/test_etapa_281.py`
- Exemplos HTML: `python scripts/gerar_exemplos_html.py` → `.private/runtime/entregaveis/exemplos-2.8/`
