# Patch v0.2.1 — Correção cirúrgica (delta)

> Delta sobre **CADERNO-DECISOES-PROVISORIAS-v0.2** (CDP) e **ESPECIFICACAO-IMPLEMENTACAO-SEGURA-v0.2** (Spec). Não substitui os dois; corrige pontos específicos.
> Objetivo: fechar as lacunas técnicas antes do código. Após esta versão, o próximo passo é **implementar o motor puro e os testes da fatia vertical** — sem mais documentação ampla.
> Versão 0.2.1 · 2026-07-20.

---

## Parte 1 — Correções (P1–P10)

Notação: **Antes** (o que estava na v0.2) → **Agora** (o que vale).

### P1 — Circularidade snapshot/aprovação
**Antes:** `Aprovacao.snapshot_id` existia e o fluxo dizia "ao aprovar, gera-se um snapshot" — a aprovação nascia antes do snapshot que referencia.
**Agora:** sequência única (ver Entregável B):
`cálculo validado → SnapshotCandidato imutável (hash) → revisor aprova aquele hash → snapshot passa a aprovado → Job gera PPTX`.
`SnapshotCalculo` ganha `estado: candidato | aprovado | superado`. `Aprovacao` só pode referenciar um snapshot **já existente** em estado `candidato`. Qualquer alteração posterior cria **novo** SnapshotCandidato e marca o anterior como `superado`, invalidando a `Aprovacao` (IS-05). **A aprovação nunca existe antes do snapshot que ela aprova.**

### P2 — Modelo financeiro completo da cotação
**Antes:** `OpcaoPlano`/`TabelaPreco` não tinham os totais impressos; B-02 não tinha o que reconciliar.
**Agora:** `OpcaoPlano` passa a conter, todos em `MoneyCents` e com proveniência por campo (IS-04):
`premio_saude_centavos`, `iof_centavos`, `total_recorrente_centavos`, `total_primeira_parcela_centavos`, `total_calculado_centavos` (derivado), `price_basis`.
`TabelaPreco` passa a conter, por faixa: `valor_centavos` **e** `quantidade_cotada`.
Custos únicos permanecem em `CustoUnico` (ex.: taxa de inscrição Porto). Cada valor extraído registra origem e evidência (página/trecho).

### P3 — Tipos monetários ≠ taxas
**Antes:** `reajuste_centavos_ou_fracao` (mistura dinheiro e taxa).
**Agora:** tipos distintos e proibição do campo antigo:
- `MoneyCents` — inteiro de centavos, para todo valor monetário.
- `RateBasisPoints` — inteiro em pontos-base (1% = 100 bps; IOF 2,38% = **238 bps**; reajuste 11,98% = **1198 bps**). Alternativa aceita: decimal exato. Nunca float.
- `PriceBasis` — enum `inclui_iof | exclui_iof | desconhecido`, obrigatório em toda tabela/total/fatura.
**Ordem de operações e arredondamento (explícita):** valor de faixa em `exclui_iof` → aplica IOF por vida → `round_half_up` para o centavo **por vida** → soma as vidas = subtotal → reconcilia contra o total impresso. A *estratégia* de arredondamento é política tipada (P4/P7): `por_vida_entao_soma` (default) | `soma_entao_aplica` | `no_total`.

### P4 — PolicySet tipado (promessa qualificada)
**Antes:** "qualquer mudança de regra sem código" + `PolicyEntry.valor_default` genérico.
**Agora:** distinção explícita:
- **Mudança de parâmetro** (limiar, default, versão de tabela, valor de tolerância) → **sem código**, só dado.
- **Novo algoritmo ou nova estrutura** (nova estratégia de arredondamento, novo *tipo* de regime de copart) → **exige código**: implementa-se o algoritmo e registra-se num **registry**; a política apenas **seleciona** um algoritmo já registrado (`algoritmo_ref`).
`PolicyEntry` passa a ser **tipada e validada por schema**: `dp_id`, `tipo_valor` (id de schema), `valor` (validado), `algoritmo_ref` (quando aplicável), `status`, `escopo`, `versao`. Fim do `valor_default` genérico.
**Fonte efetiva única (elimina duplicação):** o valor efetivo resolve-se na ordem `StudyPolicyChoice` (se houver) → `PolicyEntry` default. Entidades de domínio que "guardam" a escolha (ex.: `Cenario.baseline_escolhido`) são **cópias denormalizadas**; a fonte é `StudyPolicyChoice`. **O `SnapshotCalculo` embute todas as políticas efetivamente aplicadas** (resolvidas), garantindo reprodutibilidade sem ambiguidade.

### P5 — DP-13 corrigida (marca de rascunho não some sozinha)
**Antes:** "a marca desaparece automaticamente quando as DPs forem homologadas".
**Agora:** homologar uma política **globalmente não altera entregáveis antigos**. A marca "RASCUNHO INTERNO" pertence ao `Entregavel`, que está preso ao `policy_set_versao` do seu snapshot. Para remover a marca, o estudo deve **conscientemente**: migrar para um PolicySet homologado → recalcular → gerar **novo** SnapshotCandidato → passar por **nova** aprovação → gerar **novo** Entregavel. Nenhum passo é automático.

### P6 — Cenário com regimes de copart diferentes entre subgrupos
**Antes:** `Cenario.rotulo_apresentacao` único; um cenário com subgrupos de regimes distintos ficaria com rótulo enganoso.
**Agora:** o cenário pode conter **várias atribuições** (`AtribuicaoPlano`) com regimes diferentes, mas a **renderização gera blocos/slides homogêneos por regime** (`sem | parcial | percentual | customizada`). O rótulo é **derivado do regime do bloco**, nunca manual. É **proibido** um único rótulo esconder composição mista: se um bloco for solicitado com regimes misturados, a geração daquele bloco é **bloqueada** (extensão de B-06) até separar. Ver caso complexo (Entregável D).

### P7 — B-02 objetivo (fim de "tolerância de centavos")
**Antes:** "tolerância de centavos" (vago).
**Agora:** reconciliação em quatro níveis, com tolerâncias configuráveis (defaults provisórios abaixo; viram escolha bloqueante por estudo se a operadora divergir — Parte 3):
- **Por vida:** |valor_com_iof_calculado − valor_esperado| ≤ **1 centavo** após arredondamento.
- **Subtotal (por opção/subgrupo):** |soma_vidas − subtotal_impresso| ≤ **2 centavos**.
- **Total impresso:** |total_calculado − total_recorrente_impresso| ≤ **5 centavos** (acúmulo de arredondamento), por operadora.
- **Primeira parcela × recorrente:** `primeira_parcela = recorrente + Σ custos_únicos`. Se fechar com custo único identificado → OK; se sobrar diferença explicável → **alerta**; se inexplicável → **bloqueante**.
Fora dessas faixas: divergência explicável e documentada = **alerta**; inexplicável = **bloqueante**. Onde ocorre o arredondamento é definido em P3.

### P8 — B-04 restrito (sem falso bloqueio)
**Antes:** toda incompatibilidade idade×valor virava suspeita bloqueante, com "faixa candidata".
**Agora:** a validação idade×valor **só roda** quando existe uma **tabela atual comparável e identificada** para o subgrupo (renovação com plano atual conhecido). Sem tabela, ou com plano/base incompatíveis, **não** se infere incompatibilidade → no máximo **alerta**. Quando roda e diverge, mostra-se **apenas a evidência encontrada** (valor da fatura × faixa esperada pela tabela atual); **nunca** uma "faixa candidata" como provável correção. Resolução: correção na fonte ou override justificado (segue bloqueante só nesse caso qualificado).

### P9 — Baseline de segurança e privacidade (reintroduzido na fatia vertical)
**Antes:** ausente na v0.2.
**Agora:** obrigatório desde o piloto (ver também Entregável A e E):
- **Escopo organizacional (`org_id`)** em todas as entidades relevantes (Cliente, Estudo, Usuario, DocumentoCotacao, Entregavel, Snapshot).
- **Acesso a dado somente pela API** (navegador nunca fala direto com o banco/storage).
- **Descarte na ingestão** dos campos SISCOR não usados: **remover CPF, endereço, CEP, telefone, nome da mãe, RG, PIS, etc.** — whitelist mantém só `{nome, parentesco, nascimento, plano, valor, status, sexo?}`. (Nome é mantido porque aparece no slide — D-P2.)
- **URLs temporárias assinadas** para PDFs e PPTX; **hash do arquivo original**; controle de acesso ao storage.
- **Retenção configurável** (default sugerido: 90 dias para dados de vidas pós-entrega).
- **Logs sem PII bruta**; registro **minimizado** do que foi enviado à IA externa (IS-08).

### P10 — Testes do Renderer (não comparar binário)
**Antes:** IS-06 falava em "travar a saída como golden" — ambíguo, sugeria igualdade binária.
**Agora:** o golden **não** é o binário do PPTX. Os testes do `Renderer` são:
1. **Semântico:** reabrir o PPTX gerado e conferir células/valores/textos contra o snapshot.
2. **Visual:** renderizar (LibreOffice → imagem) e comparar por imagem **com tolerância**.
3. **Matriz de casos:** 1, 12, 20 e 29 vidas; um e dois planos; copart `sem`, `parcial`, `percentual`.
Igualdade de bytes do PPTX é explicitamente rejeitada como critério.

---

## Parte 2 — Entregáveis

### A. Modelo relacional v0.2.1 (só entidades afetadas)

Tipos: `MoneyCents` (int), `RateBasisPoints` (int) | Decimal exato, `PriceBasis` (`inclui_iof|exclui_iof|desconhecido`).

- **Org** *(nova)* — `id`, `nome`. → `org_id` em Cliente, Usuario, Estudo, DocumentoCotacao, SnapshotCalculo, Entregavel.
- **Vida** — `valor_fatura_centavos: MoneyCents`; remove `fatura_inclui_iof:bool` → basis fica em `SubgrupoAtual.fatura_price_basis`. Ingestão só grava campos da whitelist (P9).
- **SubgrupoAtual** — `reajuste_bps: RateBasisPoints` (substitui `reajuste_centavos_ou_fracao`); `fatura_price_basis: PriceBasis`.
- **OpcaoPlano** *(ampliada)* — `+ premio_saude_centavos`, `+ iof_centavos`, `+ total_recorrente_centavos`, `+ total_primeira_parcela_centavos`, `+ total_calculado_centavos`, `+ price_basis`.
- **TabelaPreco** — `valor_centavos: MoneyCents`, `+ quantidade_cotada: int`.
- **CustoUnico** — `valor_centavos: MoneyCents` (sem alteração de forma).
- **SnapshotCalculo** *(ampliada)* — `+ estado: candidato|aprovado|superado`, `+ politicas_efetivas` (JSON resolvido, embutido), `+ parametros` (iof_bps, tolerâncias, estratégia de arredondamento usadas).
- **Aprovacao** — `snapshot_id` referencia snapshot em estado `candidato`; `estado: pendente|aprovada|invalidada`. FK obrigatória a um snapshot já existente.
- **Entregavel** — `marca_rascunho:bool` derivada do `policy_set_versao` do snapshot (P5); `gerado_de: snapshot_id (aprovado)`; `+ dps_provisorias[]`.
- **PolicyEntry** *(retipada)* — `dp_id`, `tipo_valor` (schema), `valor` (validado), `algoritmo_ref?`, `status`, `escopo`, `versao`. Remove `valor_default` genérico.
- **RegimeCopart** — inalterada (`tipo: sem|parcial|percentual|customizada`, escopo, percentual, limitadores).

### B. Sequência definitiva de estados

```
calculo_e_validacao
  ├─ há bloqueio aberto?  → permanece; não gera snapshot
  └─ sem bloqueio         → cria SnapshotCandidato (imutável, hash, politicas_efetivas)  [estado=candidato]
        → em_conferencia
        → revisor aprova o HASH do candidato
              → Aprovacao(aprovada, snapshot=esse candidato)
              → snapshot [estado=aprovado]
        → Job(render_pptx) sobre o snapshot APROVADO → Entregavel
        → entregue

Alteração manual em qualquer dado que afeta cálculo (a partir de em_conferencia/aprovado):
   → Aprovacao vigente → invalidada
   → snapshot vigente  → superado
   → volta a calculo_e_validacao → (recalcula) → novo SnapshotCandidato
```
Invariante: **não existe Aprovacao sem um SnapshotCandidato pré-existente**; **não se gera PPTX sem snapshot `aprovado`** (B-01).

### C. Matriz de bloqueios

| ID | Condição objetiva | Evidência necessária | Resolução |
|---|---|---|---|
| **B-01** | Geração de snapshot final/PPTX sem `Aprovacao.aprovada` (ou autoaprovação sem flag registrada) | Registro de aprovação com revisor + hash | Revisor aprova o hash do candidato (DP-14) |
| **B-02** | Reconciliação fora das tolerâncias de P7 (vida ≤1c / subtotal ≤2c / total ≤5c / parcela = recorrente+custos) e não explicada | Totais impressos (premio, iof, recorrente, 1ª parcela), qtd por faixa, custos únicos | Corrigir extração, declarar `price_basis`, ou registrar override; senão bloqueia |
| **B-03** | Campo com origem `ia` **ou** documento em `extraido_com_alerta`/`falha_extracao` sem confirmação | Proveniência do campo + confirmação manual | Confirmar/editar via entrada manual (IS-07) |
| **B-04** | Idade×valor divergente **quando há tabela atual comparável identificada** | Tabela atual do subgrupo + valor de fatura | Corrigir na fonte ou override justificado; sem tabela comparável = só alerta (P8) |
| **B-05** | Faixa incompleta / campo obrigatório de opção usado num cenário ausente | Tabela por faixa completa (10 faixas) | Completar dados da opção |
| **B-06** | Subgrupo/vida sem `AtribuicaoPlano` no cenário **ou** bloco de render com regimes de copart misturados sob um rótulo | Matriz de atribuição + regime por opção | Atribuir plano a cada subgrupo; separar blocos por regime (P6) |
| **B-07** | DP que exige escolha do estudo sem valor definido (data idade DP-01, baseline DP-03, reajuste DP-04, estratégia de tolerância/arredondamento) | `StudyPolicyChoice` correspondente | Usuário define a escolha no estudo |
| **B-08** | Vidas incluídas > 29 | Contagem de `Vida.incluida = true` | Fora do piloto; reduzir escopo ou tratar fora do sistema |

### D. Dois casos de aceite da fatia vertical

**Caso simples — renovação, 1 plano atual, 1 proposta.**
1. Importa SISCOR (só whitelist gravada; CPF/endereço descartados). 2. Vidas ativas sugeridas; analista confirma inclusões. 3. Define `data_referencia_idade`, baseline e reajuste (senão B-07). 4. Digita 1 proposta na entrada manual (cada valor com proveniência); totais impressos preenchidos. 5. Motor calcula atual/reajustado/proposta/diferenças em centavos. 6. Reconciliação P7 passa dentro das tolerâncias; nenhuma vida em B-04 (há tabela atual). 7. Revisor confere e aprova o hash. 8. SnapshotCandidato→aprovado; políticas efetivas embutidas. 9. PPTX gerado, totais idênticos ao snapshot, marca "RASCUNHO INTERNO".
**Aceite:** percorre 1→9, PPTX reconciliado e auditável, com um único regime de copart e rótulo coerente.

**Caso complexo — renovação, 2 planos atuais, atribuição manual, regimes potencialmente diferentes.**
Igual ao simples, com: 2 `SubgrupoAtual` (operadoras/tipos fiscais possivelmente distintos — C.08 resolvido); cada vida referencia seu subgrupo; no cenário, o analista faz a **atribuição manual** (B-06) de opção por subgrupo; se os subgrupos ficarem com regimes de copart diferentes, a renderização gera **blocos/slides separados por regime** (P6), cada um com rótulo derivado; nenhum rótulo mistura regimes.
**Aceite:** percorre 1→9 com 2 planos, atribuição explícita, e saída segmentada por regime — sem rótulo enganoso.

### E. Backlog de implementação (ordem de dependência)

1. **Motor puro + testes** — tipos (`MoneyCents`/`RateBasisPoints`/`PriceBasis`), modelo tipado, cálculo, políticas tipadas + registry de algoritmos, validações/bloqueios. Testado contra o corpus histórico, sem infra.
2. **Persistência** — Postgres, entidades v0.2.1, repositórios, `org_id`/tenant, tabela `Job`.
3. **Entrada manual estruturada** — o fallback principal (IS-07); alimenta o motor sem depender de parser.
4. **Adapter SISCOR** — ingestão + whitelist/descarte de PII (P9) + cálculo de idade/faixa.
5. **Checkpoint + aprovação + snapshot** — sequência B, proveniência, invalidação (IS-05), auditoria.
6. **Renderer** — adapter PPTX atrás de interface + testes semânticos/visuais (P10).
7. **(Depois)** Parsers automatizados, um a um, com entrada manual sempre como fallback; IA apenas sugestão.

---

## Parte 3 — Escolhas bloqueantes por estudo (onde depende do Wesley)

Onde não há regra homologada, **não se inventa regra global**: vira escolha explícita e **bloqueante por estudo** (B-07), com default provisório citado:

- **Data que governa a faixa** (DP-01) — default: cotação mais recente.
- **Baseline apresentado** (DP-03) — default: reajustado.
- **Reajuste** (DP-04) — default: tabela PME por operadora/período.
- **`price_basis` da fatura e da tabela** (DP-02) — default: pelo `tipo_fiscal`; se a reconciliação P7 falhar, o usuário **declara** o basis (bloqueante até declarar).
- **Estratégia e tolerâncias de reconciliação/arredondamento** (P3/P7) — default: `por_vida_entao_soma`, tolerâncias 1c/2c/5c; por operadora, configurável; divergência inexplicável = bloqueante.
- **Regime de copart por opção** (DP-06) — sem default silencioso; exige confirmação quando não extraído com segurança.

Cada escolha grava `StudyPolicyChoice` (usuário, valor, justificativa) e entra nas `politicas_efetivas` do snapshot. Promoção a global só após homologação (CDP §1).

---

### Fim do patch
Com a v0.2.1, os artefatos estão prontos para orientar a implementação. Próximo passo: **motor financeiro puro + testes da fatia vertical** (Backlog E, item 1) — sem nova documentação ampla.
