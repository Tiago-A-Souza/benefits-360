# Handoff de Implementação — Sistema de Estudos Newport

> Documento de passagem de bastão do Cowork (concepção) para o Cursor (implementação).
> **Nenhum código foi escrito na concepção.** Este handoff autoriza e delimita a primeira entrega.
> UTF-8 · Versão 1.0 · 2026-07-20.

---

## 1. Objetivo do piloto

Permitir que **qualquer pessoa da Newport** monte um **comparativo financeiro** de plano de saúde (empresas de **1 a 29 vidas**) a partir das cotações das seguradoras e da base de vidas do cliente, com precisão **auditável e reproduzível**. O que hoje depende de poucos especialistas passa a ser um fluxo guiado e verificável.

**Esta primeira entrega é apenas o núcleo:** o **motor financeiro puro** e seus **testes**. Interface, banco, extração e geração de PPTX vêm depois, sobre um motor já confiável.

## 2. Escopo e fora de escopo

**No escopo (do produto, faseado):** comparativo financeiro; formatos novo, renovação e renovação com 2+ planos; regimes de coparticipação sem / parcial / percentual / customizada; operadoras Amil, Bradesco, SulAmérica, Porto; ingestão SISCOR; 1–29 vidas; entregável PPTX marcado como rascunho enquanto houver decisão provisória.

**Fora de escopo (agora):** comparativos de rede, reembolso, regras contratuais, seguro de vida e odonto; parsers automatizados; IA de extração; adapter Flui; front-end; banco; worker; infraestrutura. Ver também §8.

## 3. Ordem de leitura dos documentos

1. **`docs/04-HANDOFF-IMPLEMENTACAO.md`** (este) — o que fazer e o que não fazer agora.
2. **`docs/02-ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2.md`** — modelo de domínio, invariantes, estados, bloqueios, auditoria.
3. **`docs/03-PATCH-v0.2.1.md`** — correções cirúrgicas. **Onde o patch diverge de 01/02, o patch prevalece.**
4. **`docs/01-CADERNO-DECISOES-PROVISORIAS-v0.2.md`** — as 14 decisões provisórias (DP) e o mecanismo de política versionada.
5. **`AGENTS.md`** (raiz) — as regras acima em forma operacional curta.

Contexto histórico opcional (não obrigatório): `ESPECIFICACAO-TECNICA-Sistema-Estudos-Newport.md` na raiz (visão v0.1).

## 4. Invariantes inegociáveis

Valem sempre; o motor deve garanti-los por construção.

- **IS-01 — Dinheiro em `MoneyCents`** (inteiro de centavos). Taxas em `RateBasisPoints` (inteiro; 1% = 100 bps) ou decimal exato. **Nunca float.**
- **IS-02 — Estado vivo relacional; JSON só como snapshot imutável.** (Aplicável ao sistema; o motor não persiste — ver §6.)
- **IS-03 — Motor puro.** Biblioteca Python sem FastAPI, banco, arquivo ou PPTX. `calcular(dados_tipados, effective_policy) -> resultado + validações`.
- **IS-04 — Proveniência por campo** (origem, evidência, valor anterior, usuário, versão do extrator).
- **IS-05 — Aprovação invalidável:** alteração em dado que afeta cálculo invalida a aprovação anterior.
- **IS-06 — Renderer reutilizável, validado por testes semânticos/visuais** (fora desta entrega).
- **IS-07 — Entrada manual estruturada é o fallback principal;** IA apenas sugere (fora desta entrega).
- **IS-08 — Minimização no envio à IA** (fora desta entrega).
- **Nada incorreto avança:** todo resultado passa pelos bloqueios B-01…B-08 (ver 02/03).
- **Nunca corrigir idade/nascimento/faixa pelo preço** (DP-08); sem "faixa candidata".
- **Sequência não-circular:** cálculo → SnapshotCandidato (hash) → aprovação do hash → aprovado → PPTX. A aprovação nunca precede o snapshot que aprova (Patch P1). *O motor produz os dados do candidato; não cria aprovação nem persiste.*

## 5. Decisões provisórias

As 14 DPs (detalhe em `docs/01`) são **regras ainda não homologadas por Wesley/Newport**. Regra de operação: **nenhuma vira regra global inventada**; cada uma tem um default provisório e, quando exige escolha, é **escolha explícita e bloqueante por estudo** (B-07). O motor **recebe** essas escolhas já resolvidas em `EffectivePolicy` (§6); nunca as decide internamente.

Resumo: DP-01 data de idade · DP-02 IOF/price_basis · DP-03 baseline vigente/reajustado · DP-04 reajuste tabelado · DP-05 validade oficial vs prazo Newport · DP-06 regimes de copart · DP-07 precedência copart da proposta · DP-08 não-correção por preço · DP-09 inclusão de vidas · DP-10 associação subgrupo↔plano manual · DP-11 arredondamento · DP-12 modalidade · DP-13 marca de rascunho · DP-14 revisor/aprovação. Promoção a "homologada" só via migração consciente de PolicySet (Patch P5).

## 6. Ajustes residuais a respeitar na implementação

Todos já refletidos em 02/03; reiterados aqui como requisitos duros do motor:

1. **`price_basis` por componente financeiro** — cada componente (tabela por faixa, prêmio, IOF, total recorrente, primeira parcela, fatura atual) carrega seu próprio `PriceBasis` (`inclui_iof | exclui_iof | desconhecido`). Não existe um único basis para a proposta inteira.
2. **Totais impressos opcionais + origem por campo** — prêmio, IOF, total recorrente e primeira parcela são **opcionais** (podem faltar num PDF/entrada manual). Cada valor tem `origem ∈ {extraído, calculado, manual}`. A reconciliação se adapta aos totais presentes; ausência não pode causar exceção, só reduz o que dá para reconciliar.
3. **Data de referência obrigatória, sem default silencioso** — a data que governa idade/faixa é entrada **obrigatória** do estudo. O motor **recusa calcular** (bloqueio B-07) se ela não vier. A UI pode *sugerir* um valor, mas o valor entregue ao motor é sempre explícito.
4. **Tolerâncias provisórias recebidas por `EffectivePolicy`** — as tolerâncias de reconciliação (por vida, subtotal, total; e a estratégia de arredondamento) **não são hardcoded** no motor. Chegam dentro de `EffectivePolicy`. Trocar tolerância = trocar política, não código.
5. **`ScenarioResult` consolidado e `ScenarioSectionResult` disjunto** — o resultado de um cenário é um `ScenarioResult` que **consolida** o cenário e contém uma lista de `ScenarioSectionResult` **disjuntos por regime de coparticipação** (sem sobreposição de vidas/subgrupos). Um rótulo nunca mistura regimes (Patch P6).
6. **Motor recebe `EffectivePolicy` já resolvida, sem acessar banco** — a resolução `StudyPolicyChoice → PolicyEntry default` acontece **fora** do motor. O motor é função pura de `(dados_tipados, EffectivePolicy)`; não lê arquivo nem banco; mesmo input ⇒ mesmo output. O snapshot embute as `politicas_efetivas` usadas.
7. **Proveniência ligada ao documento e à versão do extrator** — cada valor extraído referencia o **documento de origem** e a **versão do extrator** (`manual`, ou `parser@versão`, ou `ia@versão`), além de página/trecho de evidência. Permite auditar qual extrator gerou cada número.

## 7. Primeira entrega autorizada

**Somente o motor financeiro puro e seus testes.** Concretamente:

- Tipos de valor (`MoneyCents`, `RateBasisPoints`, `PriceBasis`) e o modelo de domínio **tipado** (entidades de 02, ajustadas por 03) como estruturas em memória.
- O cálculo: idade/faixa, atual (com/sem IOF por tipo fiscal), reajustado, proposta, diferenças mês/ano, por vida/subgrupo/cenário; `ScenarioResult` + `ScenarioSectionResult`.
- As políticas como `EffectivePolicy` de entrada (resolvida fora) + o registry de algoritmos selecionáveis (arredondamento, regime de copart).
- As validações e os bloqueios B-01…B-08 no nível do motor (os que dependem de dado, não de infra).
- A suíte de testes A–H (§9) rodando contra fixtures fictícias (ver `tests/fixtures/README.md`).

## 8. Componentes proibidos nesta primeira entrega

Não introduzir, nem como esqueleto: **FastAPI, React, Postgres (ou qualquer banco), worker/tabela de jobs, geração de PPTX, parsers automatizados de PDF, IA/LLM.** Também não inicializar frontend nem infraestrutura. Esses itens entram nas etapas seguintes do backlog (Patch, Entregável E), depois do motor puro validado.

## 9. Testes A–H

> Nota de transparência: o último parecer não numerou os testes como "A–H"; consolidei os requisitos de teste dele em **oito suítes A–H para o motor puro**. Os testes de renderização visual do PPTX (parecer P10) ficam para quando o Renderer entrar — **fora desta entrega**.

- **A. Tipos e aritmética** — `MoneyCents`/`RateBasisPoints` sem float; `round_half_up` por centavo determinístico; ordem de operações (aplica taxa por vida → arredonda por vida → soma). Casos de borda de arredondamento.
- **B. Reconciliação (B-02)** — valida tolerâncias por vida/subtotal/total vindas de `EffectivePolicy`; `primeira_parcela = recorrente + Σ custos_únicos`; classifica alerta vs bloqueante; **funciona com totais impressos ausentes** (opcionais) sem quebrar.
- **C. IOF e `price_basis` por componente** — seguradora com IOF, operadora sem; basis por componente; quando `desconhecido` e não reconcilia → exige declaração (bloqueio), **sem assumir**.
- **D. Atual e reajuste (renovação)** — atual com/sem IOF conforme tipo fiscal; `reajustado = atual × (1 + reajuste_bps)`; **ambos** os baselines (vigente e reajustado) calculados; diferença mês e ano.
- **E. Idade/faixa (DP-01, DP-08)** — faixa na **data de referência obrigatória** (sem data ⇒ bloqueia, sem default silencioso); detecção idade×valor **só** quando há tabela atual comparável identificada; **nunca** auto-corrige nem sugere faixa candidata (só evidência).
- **F. Cenários e seções por regime (P6)** — `ScenarioResult` consolidado com `ScenarioSectionResult` **disjuntos** por regime; atribuição manual por subgrupo; **bloqueio B-06** quando subgrupo sem atribuição ou quando um bloco misturaria regimes.
- **G. Pureza e `EffectivePolicy`** — motor não acessa banco/arquivo; mesmo input ⇒ mesmo output; tolerâncias/estratégias vêm da política; o resultado embute as `politicas_efetivas` aplicadas.
- **H. Formas, escala e proveniência** — casos de **1, 12, 20 e 29 vidas**; **um e dois planos**; copart **sem / parcial / percentual**; **B-08** (>29 bloqueia); cada valor com **proveniência** (documento + versão do extrator + origem).

Onde um comportamento não puder ser fixado sem Wesley, o teste exercita a **escolha bloqueante por estudo** (a ausência de escolha deve bloquear), não um valor global inventado.

## 10. Critério de conclusão e formato do relatório

**Concluído quando:**
- O motor puro implementa o modelo tipado + cálculo + políticas (via `EffectivePolicy`) + bloqueios B-01…B-08 aplicáveis a dado.
- As **oito suítes A–H passam** contra as fixtures fictícias.
- Nenhum componente proibido (§8) foi introduzido.
- Determinismo verificado (mesmo input ⇒ mesmo output) e proveniência presente em cada valor.

**Relatório de implementação** (`RELATORIO-IMPLEMENTACAO.md`, Markdown UTF-8, na raiz), contendo:
1. Módulos entregues e a fronteira pública do motor (assinaturas conceituais, sem depender de infra).
2. Resultado das suítes A–H (passou/falhou + contagem) e as fixtures usadas.
3. Cobertura dos bloqueios B-01…B-08 no nível do motor (qual teste cobre cada um).
4. Lista dos pontos que viraram **escolha bloqueante por estudo** (aguardando homologação de Wesley), com o default provisório usado.
5. Questões abertas e riscos, sem inventar regra global.

Após a conclusão e o relatório, o próximo passo do backlog é **persistência → entrada manual → SISCOR → checkpoint/snapshot → Renderer** (Patch, Entregável E). Parsers automatizados e IA só depois da fatia manual funcionando.
