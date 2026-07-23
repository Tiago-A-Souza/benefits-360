# AGENTS.md — Regras para agentes neste repositório

Sistema de Estudos Newport — comparativo financeiro de planos de saúde.
**Faixa inicial homologada:** 1–29 vidas (configurável; **sem teto técnico** no motor).
Estágio atual: **ETAPA 2.5.6 concluída** — conferência operacional de cotações PDF; **próximo passo: persistência histórica + snapshot/aprovação + PPTX**.

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
- **ETAPA 2.4 → 2.5.5:** wizard guiado, proposta manual, ingestão PDF (Porto, SulAmérica, Amil, Bradesco, Omint).
- **ETAPA 2.5.6:** conferência PDF completa no navegador, aplicação sem defaults silenciosos, reconciliação automática após correção, regressão sintética por operadora.

## Estado real dos parsers PDF (homologação privada)
| Operadora | Template | Extração | Observação |
|-----------|----------|----------|------------|
| **Porto** | `porto-orcamento-v1` | 10 faixas, prêmio/IOF/total | Reconciliação diverge quando qtd por faixa ≠ subtotal |
| **SulAmérica** | `sulamerica-pme-v1` | 10 faixas, totais | Reconciliação OK no corpus privado |
| **Amil** | `amil-visual-v1` | até 4 opções, 10 faixas/op | Prêmio/IOF globais ausentes — conferir manualmente |
| **Bradesco** | `bradesco-cp-v1` | 2 perfis, 10 faixas | Totais pág. 2 globais; reconciliação exige revisão |
| **Omint** | `omint-ocr-v1` | `ocr_pendente` | Sem Tesseract: esqueleto + entrada manual |

Regressão versionada: `tests/test_cotacao_pdf_regressao.py` + `tests/fixtures/cotacao_pdf/regressao_esperada.json`. Corpus real: `.private/homologacao_cotacao_pdf.py` (fora do Git).

## Faça agora (quando autorizado)
- **Persistência histórica + snapshot/aprovação + PPTX** — após aprovação explícita.

## NÃO faça sem autorização
- Persistência histórica relacional, snapshot, aprovação formal, PPTX, autenticação ou seguro novo.
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
- **PDF:** nenhum valor extraído nasce confirmado; tipo fiscal e coparticipação **nunca** recebem default na aplicação.

## Dados e fixtures
- Somente dados **fictícios ou anonimizados** entram no Git.
- **Proibido** versionar CPF, endereço, telefone e qualquer PII. Documentos reais ficam **fora** do repositório.
- **Modo demo** (`NEWPORT_MODO=demo`, default): banco e demos em `.data/`.
- **Modo real** (`NEWPORT_MODO=real`): estudos, importações e uploads em `.private/runtime/`; bind somente em `127.0.0.1`.

## Ambiente de testes
- Usar o venv do projeto: `.venv\Scripts\python.exe -m pytest`
- Dependências: `pip install -e ".[app,dev]"` dentro do `.venv`.
- Regressão PDF: `.venv\Scripts\python.exe -m pytest tests/test_cotacao_pdf_regressao.py -q`
- Homologação privada: `.venv\Scripts\python.exe .private\homologacao_cotacao_pdf.py`
