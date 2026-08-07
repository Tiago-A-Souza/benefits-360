# 00 — Sumário executivo

Fonte: commit `2a69d4c0bd12e4e8613cb8b085b1dac0c50cb805` — 2026-07-27

---

## O que o sistema faz

O **Sistema de Estudos Newport** monta um **comparativo financeiro** entre o plano de saúde coletivo atual de um cliente PME e propostas de operadoras/seguradoras. Entrada típica: planilha SISCOR (vidas e valores) + PDFs de cotação (ou digitação manual). Saída típica hoje: **HTML autocontido** (modos por faixa etária ou por beneficiário), depois de cálculo, snapshot com hash e aprovação local.

O núcleo financeiro é um **motor puro** (`calcular(EstudoInput, EffectivePolicy) → MotorResult`) que trabalha só com **centavos inteiros** e taxas em basis points — sem float. A aplicação (`newport_app` + React/Vite) cuida de ingestão, conferência humana, wizard, persistência SQLite e apresentação.

---

## Para quem

- **Analistas Newport** que hoje montam o estudo em planilha + PowerPoint.
- **Revisor** (papel provisório, sem autenticação corporativa) que aprova o snapshot antes do HTML.
- **Agentes/IAs** que precisam discutir arquitetura e escopo **sem abrir o repositório** — este pacote `docs/handoff-ia/`.

Não é portal do cliente final, nem plataforma multi-tenant com login.

---

## Em que estágio está

| Camada | Estado real (código + git) |
|--------|----------------------------|
| Motor financeiro + suítes A–H | **implementado** (piloto; regras sensíveis versionadas) |
| SISCOR + conferência | **implementado** (homologação com corpus privado ainda operacional) |
| Cotação PDF (Porto, SulAmérica, Amil, Omint) | **parcial** — templates reconhecidos; `extracao_financeira_homologada` **sempre false** |
| Wizard operacional (ETAPA 3.0+) | **implementado** até confirmação do comparativo e HTML |
| Snapshot / aprovação / HTML | **implementado** |
| PPTX / rede / reembolso / odonto / seguro de vida | **inexistente** no software |
| Auth / cloud / link público | **inexistente** (proibidos sem autorização) |

**Atenção:** `AGENTS.md` ainda diz “ETAPA 2.8.1”; o `git log` chega a **ETAPA 3.0** e hotfixes 3.0.x. Código e histórico git prevalecem.

Faixa comercial homologada: **1–29 vidas** (alerta H-01 acima disso). **B-08** no código = estudo **sem vidas**, não “>29”.

---

## Três coisas que alguém novo precisa saber

1. **Dinheiro nunca é float.** Tudo é `MoneyCents` (int). IOF padrão 238 bps só para `tipo_fiscal=seguradora`. `price_basis=desconhecido` bloqueia (B-02). Conferência humana (`confirmado`) é obrigatória para valores de IA/extração em alerta (B-03). Defaults de confirmação no draft/PDF começam em `false`; no motor o default do modelo é `true` — o compilador precisa carregar o estado certo.

2. **O entregável cliente histórico (PPTX com 12 partes) não foi portado.** O sistema cobre o **núcleo financeiro + classificação de copart**; rede, reembolso, odonto, seguro de vida e PPTX estão fora. HTML é o entregável real; banner “RASCUNHO INTERNO” permanece enquanto políticas forem provisórias.

3. **Governança: calcular → snapshot (hash) → revisar → aprovar (`confirmo_conteudo`) → HTML.** Aprovação sem atestado é rejeitada; HTML exige snapshot `aprovado`. Extração PDF “pronta para aplicar” **não** significa homologação financeira.

---

## Como usar este handoff

| Arquivo | Conteúdo |
|---------|----------|
| `01`–`10` | Domínio, dados, motor, SISCOR, PDF, API, apresentação, testes, lacunas, glossário |
| `CONSOLIDADO.md` | Versão única colável em chat externo |
| `docs/` canônicos 01–07 | Spec histórica; onde divergir do código, **código vence** (ver `09`) |

Leitura mínima recomendada para discussão de produto: este arquivo + `03-MOTOR-CALCULO.md` + tabela de paridade em `07` + `09`.

---

## ⚠️ NÃO VERIFICADO

1. Priorização comercial oficial Newport das 12 partes do entregável manual (fora do que o código declara como escopo).
2. Data-alvo interna para PPTX / homologação financeira PDF (não há milestone versionado no repo além de `AGENTS.md`).
