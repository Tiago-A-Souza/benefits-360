# Especificação de Implementação Segura v0.2 — Sistema de Estudos Newport

> Artefato irmão do **Caderno de Decisões Provisórias (CDP)**. Lê as regras pendentes como política versionada (ver CDP §1).
> Estratégia: *implementação tolerante a decisões pendentes*. Precisão é o princípio máximo: **nada incorreto avança**.
> Escopo: fatia vertical do comparativo **financeiro**, 1–29 vidas. Versão 0.2 · 2026-07-20.
> **Este documento não contém código.** Entrega: modelo de domínio, invariantes, políticas, fluxo de estados, bloqueios, auditoria e critérios de aceite.

---

## Parte 1 — Invariantes de segurança (IS)

Diferente das DPs (provisórias), os **invariantes** são firmes desde já — são os mecanismos que tornam as decisões pendentes toleráveis.

- **IS-01 — Dinheiro em inteiro.** Todo valor monetário é armazenado em **centavos inteiros** (ou decimal exato serializado como string). Nunca ponto flutuante. Vale para mensalidade, IOF, reajuste, totais, diferenças.
- **IS-02 — Estado vivo relacional; JSON só como snapshot.** O estado editável, concorrente e auditável vive no **banco relacional**. O JSON é um **snapshot imutável** de uma versão aprovada, que alimenta o PPTX e a auditoria. O JSON nunca é o store de trabalho.
- **IS-03 — Motor puro.** O cálculo é uma **biblioteca Python independente**, sem FastAPI, banco, arquivo ou PowerPoint. Assinatura conceitual: `calcular(dados_tipados, policy_set) -> resultado + validações`. Isso permite testá-lo com o corpus histórico sem subir infraestrutura.
- **IS-04 — Proveniência por campo.** Cada valor extraído carrega origem (`parser | ia | manual`), página/trecho de evidência, valor anterior, usuário e timestamp. Não existe proveniência "por proposta inteira".
- **IS-05 — Aprovação invalidável.** Qualquer alteração manual em dado que afeta cálculo **invalida automaticamente** a aprovação anterior e devolve o estudo à conferência.
- **IS-06 — Reuso avaliado, não presumido.** O gerador PPTX atual é tratado como **adapter reutilizável atrás de uma interface `Renderer`**, validado por **testes de caracterização** (rodar sobre snapshots conhecidos e travar a saída como golden) antes de qualquer refatoração. Se falhar nos testes, é reescrito; não se assume que funciona.
- **IS-07 — Entrada manual é o fallback principal.** Se um parser falha ou fica em alerta, o piso seguro é a **entrada manual estruturada** (documento ao lado de um formulário). A IA apenas **sugere** valores; o humano confirma. Reconciliações decidem se pode avançar.
- **IS-08 — Minimização no envio à IA.** Antes de mandar qualquer conteúdo a um serviço externo de IA, dados pessoais são minimizados/redigidos e registra-se **o que** foi processado externamente.

---

## Parte 2 — Modelo de domínio (relacional)

**Entidade central:** `Estudo`. Tudo se conecta a ela. Money = `*_centavos` (IS-01).

### Domínio Identidade
- **Usuario** (`id`, `email`, `papel: analista|revisor`, `ativo`).

### Domínio Cadastro
- **Cliente** (`id`, `nome`, `cnpj`).
- **Estudo** (`id`, `cliente_id`, `formato: novo|renovacao`, `estado`, `data_referencia_idade` [DP-01], `policy_set_versao` [pin], `criado_por`, `criado_em`).
- **Vida** (`id`, `estudo_id`, `nome`, `parentesco`, `nascimento`, `faixa` [derivada no cálculo], `valor_fatura_centavos`, `fatura_inclui_iof` [DP-02], `incluida:bool` [DP-09], `motivo_inclusao_exclusao`, `subgrupo_atual_id`, `flags[]`).

### Domínio Situação atual (só renovação)
- **SubgrupoAtual** (`id`, `estudo_id`, `operadora`, `tipo_fiscal: seguradora|operadora`, `plano_nome`, `regime_copart_id` [DP-06], `acomodacao`, `modalidade` [DP-12], `reajuste_centavos_ou_fracao` [DP-04]).
  *Resolve o C.08: cada subgrupo tem sua própria operadora e tipo fiscal — 2 planos de operadoras diferentes é natural.*

### Domínio Cotações (normalização em 3 níveis)
- **DocumentoCotacao** (`id`, `estudo_id`, `operadora`, `arquivo_ref`, `hash`, `template_fingerprint`, `parser_versao`, `data_emissao`, `validade_oficial` [DP-05], `data_vigencia_pretendida`, `estado_extracao`).
- **Proposta** (`id`, `documento_id`, `operadora`, `numero`, `abrangencia`, `contratacao`, `obs`) — o conjunto comercial extraído de um documento.
- **OpcaoPlano** (`id`, `proposta_id`, `plano_nome`, `acomodacao`, `regime_copart_id` [DP-06], `tabela_inclui_iof` [DP-02]) — um plano/tabela que **pode entrar** num cenário.
- **TabelaPreco** (`id`, `opcao_plano_id`, `faixa`, `valor_centavos`) — 10 faixas por opção.
- **CustoUnico** (`id`, `opcao_plano_id`, `descricao`, `valor_centavos`) — ex.: taxa de inscrição Porto (fora do mensal, DP correlata à regra RN-3.4.4).
- **RegimeCopart** (`id`, `tipo: sem|parcial|percentual|customizada`, `escopo_procedimentos[]`, `percentual`, `limitadores`, `origem`) [DP-06].

### Domínio Estudo/Cenário (cenário = atribuição de planos)
- **Cenario** (`id`, `estudo_id`, `rotulo_apresentacao: com_copart|copart_parcial|sem_copart`, `baseline_escolhido: vigente|reajustado` [DP-03]).
- **AtribuicaoPlano** (`id`, `cenario_id`, `alvo_tipo: subgrupo|vida`, `alvo_id`, `opcao_plano_id`) [DP-10] — qual opção cada subgrupo/vida recebe naquele cenário. *Referencia opção por ID; não duplica a proposta.*

### Domínio Cálculo/Entrega
- **SnapshotCalculo** (`id`, `estudo_id`, `versao`, `json_imutavel`, `hash`, `criado_em`) — snapshot congelado (IS-02).
- **Aprovacao** (`id`, `estudo_id`, `snapshot_id`, `revisor_id`, `estado: pendente|aprovada|invalidada`, `criado_em`, `invalidada_em`, `motivo_invalidacao`) [DP-14, IS-05].
- **Entregavel** (`id`, `estudo_id`, `snapshot_id`, `tipo: pptx`, `arquivo_ref`, `marca_rascunho:bool`, `dps_provisorias[]`) [DP-13].

### Domínio Política (o mecanismo do CDP §1)
- **PolicySet** (`id`, `versao`, `status_global`).
- **PolicyEntry** (`id`, `policy_set_id`, `dp_id`, `valor_default`, `status: provisoria|homologada`, `escopo: global|por_estudo`, `evidencia`).
- **StudyPolicyChoice** (`id`, `estudo_id`, `dp_id`, `valor_escolhido`, `usuario_id`, `justificativa`, `criado_em`).

### Domínio Auditoria
- **ProvenienciaCampo** (`id`, `alvo_tipo`, `alvo_id`, `campo`, `origem`, `evidencia_pagina`, `evidencia_trecho`, `valor_anterior`, `usuario_id`, `criado_em`) [IS-04].
- **Validacao** (`id`, `estudo_id`, `codigo`, `severidade: info|alerta|bloqueante`, `estado: aberta|resolvida|override`, `mensagem`, `alvo_ref`, `resolvido_por`, `justificativa`).
- **Job** (`id`, `tipo: extracao|render_pptx`, `estado: pendente|rodando|concluido|falha`, `tentativas`, `payload`, `erro`, `criado_em`, `atualizado_em`) — worker por tabela (Parte 6).
- **AuditLog** (`id`, `entidade`, `entidade_id`, `acao`, `usuario_id`, `antes`, `depois`, `criado_em`).

---

## Parte 3 — Fluxo de estados

### 3.1 Estado do Estudo
```
rascunho
  → vidas_em_revisao        (base SISCOR importada)
  → cotacoes_em_extracao    (documentos recebidos)
  → calculo_e_validacao     (motor puro roda)
  → em_conferencia          (checkpoint humano)
  → aprovado                (revisor aprova snapshot)
  → entregue                (PPTX gerado e baixado)
  → arquivado
```
**Retrocessos (IS-05):** qualquer alteração manual que afete cálculo a partir de `em_conferencia`/`aprovado` devolve para `calculo_e_validacao`, invalida a `Aprovacao` vigente e re-dispara validações.

### 3.2 Estado da extração (por DocumentoCotacao) — substitui score numérico por estados verificáveis
```
recebido → em_extracao →
    extraido_ok            (todos os campos + reconciliação OK)
  | extraido_com_alerta    (faltou campo / divergência não-bloqueante)
  | falha_extracao         (parser não reconheceu o template)
→ conferido                (humano confirmou)
```
`extraido_com_alerta` e `falha_extracao` **exigem** passagem pela entrada manual assistida (IS-07) antes de `conferido`.

### 3.3 Estado da Aprovação
```
pendente → aprovada → (invalidada por alteração posterior, IS-05)
```

### 3.4 Estado do Job
```
pendente → rodando → concluido | falha(+tentativas)
```

---

## Parte 4 — Bloqueios (o que impede um resultado incorreto)

Cada bloqueio é uma `Validacao` de severidade `bloqueante`. **Nenhum estudo passa de `em_conferencia` para `aprovado`, e nenhum snapshot/PPTX é gerado, com bloqueio aberto.**

- **B-01 — Sem aprovação, sem entrega.** Snapshot final e PPTX exigem `Aprovacao.aprovada` por usuário Revisor (ou autoaprovação registrada, DP-14).
- **B-02 — Divergência monetária.** `soma_por_vida (±IOF) ≠ total impresso` além da tolerância, não resolvida → bloqueante (DP-02, DP-11).
- **B-03 — Valor não confirmado.** Campo com origem `ia` ou documento em `extraido_com_alerta`/`falha_extracao` sem confirmação manual → bloqueante (IS-04, IS-07).
- **B-04 — Suspeita idade×valor.** Vida com flag de incompatibilidade não resolvida (correção na fonte ou override justificado) → bloqueante (DP-08).
- **B-05 — Dados obrigatórios ausentes.** Faixa incompleta, valor de faixa faltando, campo obrigatório de opção usado num cenário → bloqueante.
- **B-06 — Cenário sem atribuição.** Subgrupo/vida sem `AtribuicaoPlano` no cenário → bloqueia a geração daquele cenário (DP-10).
- **B-07 — Política sem escolha.** DP que exige escolha do estudo (data de idade DP-01, baseline DP-03, reajuste DP-04) sem valor definido → bloqueia o cálculo.
- **B-08 — Fora do piloto.** Vidas incluídas > 29 → bloqueante (fora do escopo do piloto).

**Alertas (não bloqueantes, mas de conferência obrigatória):** divergência copart proposta×base >2% (DP-07); adesão sem confirmação societária (DP-12); validade oficial ausente (DP-05).

---

## Parte 5 — Esquema de auditoria

Três trilhas complementares respondem "quem, quando, com base em quê, e o que mudou":

1. **ProvenienciaCampo (IS-04)** — por valor: origem, página/trecho de evidência, valor anterior, usuário, timestamp. Toda correção crítica no checkpoint grava aqui, com **justificativa**.
2. **Validacao** — cada checagem (info/alerta/bloqueante) com estado e, quando resolvida por override, o `resolvido_por` + justificativa.
3. **AuditLog** — transições de estado, aprovações, invalidações (IS-05), escolhas de política (`StudyPolicyChoice`), e envios a IA externa (IS-08, com o conteúdo redigido registrado).

**Regra de correção crítica:** editar um valor que afeta cálculo exige `{justificativa, evidência, usuário, data, valor anterior}`, dispara re-validação e **invalida a aprovação anterior** (IS-05). Sem isso, a edição é rejeitada.

Cada `SnapshotCalculo` é imutável e endereçável por `hash` — dado um PPTX, sempre se reconstrói exatamente com que dados e qual `policy_set_versao` foi gerado.

---

## Parte 6 — Arquitetura (monólito modular enxuto)

Um repositório, uma aplicação, poucos processos. Todo acesso a dado passa pela API (sem o navegador falando direto com tabelas — evita dois caminhos de autorização).

**Módulos (fronteiras lógicas, não microserviços):**
- `dominio/` — **motor puro** (modelo tipado, cálculo, políticas, validações). Sem I/O (IS-03).
- `ingestao/` — adapters: `siscor` (layout fixo) e, futuro, `flui`. Normalizam para o modelo.
- `extracao/` — parsers por operadora + entrada manual estruturada (fallback principal) + IA (sugestão). Emite estados verificáveis (§3.2).
- `render/` — adapter `Renderer` sobre o gerador PPTX atual, coberto por testes de caracterização (IS-06).
- `persistencia/` — repositórios sobre Postgres; único ponto de acesso a dados.
- `jobs/` — **worker por tabela de jobs no Postgres** (§6.1).
- `api/` — FastAPI: orquestra, aplica permissões (papéis DP-14), expõe o fluxo.
- `web/` — UI React (wizard + checkpoint). Fala só com a `api/`.

**Serviços de apoio:** um Postgres (estado + jobs), um storage (PDFs/PPTX). Provedor gerenciado é aceitável **desde que o acesso a dados passe pela API**, não direto do navegador.

### 6.1 Worker assíncrono (sem Redis/Celery)
Extração de PDF e geração de PPTX (LibreOffice/pdftoppm) **não rodam dentro da requisição web**. Vão para a tabela `Job`:
- API insere `Job(pendente)` e devolve na hora um id de acompanhamento.
- Um processo worker faz *polling* com `SELECT ... FOR UPDATE SKIP LOCKED`, executa, atualiza estado, guarda `tentativas`/`erro`, respeita `timeout` e é **idempotente** (reprocessar o mesmo job não duplica efeito).
- A UI acompanha por *status*.
- Redis/Celery só entram se houver necessidade demonstrada (volume/concorrência) — não no piloto.

---

## Parte 7 — Fatia vertical e critérios de aceite

Fluxo a provar ponta a ponta antes de investir nos quatro parsers:

**SISCOR → revisão das vidas → entrada manual ou um parser → cálculo → validações → checkpoint → snapshot → PPTX.**

Cada etapa com critério **observável** (como saber que está pronta):

| # | Etapa | Critério de aceite |
|---|---|---|
| 1 | Importar SISCOR | O analista sobe a "Posição Cadastral" e vê as vidas com nome, parentesco, nascimento, plano e valor; os subgrupos (planos distintos) aparecem separados; valores em centavos inteiros. |
| 2 | Revisão das vidas | Vidas `Ativo` vêm marcadas para inclusão; o analista inclui/exclui vida a vida e o total recalcula; toda exclusão registra motivo (DP-09). |
| 3 | Data de idade e políticas do estudo | O analista define `data_referencia_idade` (DP-01), baseline (DP-03) e confirma o reajuste (DP-04); sem isso, o cálculo fica bloqueado (B-07). |
| 4 | Entrada de proposta (1 operadora) | O analista digita uma proposta na entrada manual estruturada **ou** roda um parser; em ambos, cada valor recebe proveniência (IS-04) e a tabela por faixa fica completa. |
| 5 | Cálculo | O motor puro calcula, por vida/subgrupo/cenário: atual (com/sem IOF conforme DP-02), reajustado, proposta, diferença mês e ano — tudo em centavos; os dois baselines ficam disponíveis (DP-03). |
| 6 | Validações | A reconciliação soma×total roda; divergência não resolvida bloqueia (B-02); vida com suspeita idade×valor bloqueia até resolução (B-04); nenhum valor `ia`/alerta não confirmado passa (B-03). |
| 7 | Checkpoint | O revisor vê a tabela consolidada + todas as flags; edita valores (cada edição exige justificativa, gera proveniência e **invalida aprovação anterior**, IS-05); aprova explicitamente. |
| 8 | Snapshot | Ao aprovar, gera-se um `SnapshotCalculo` imutável com `hash` e `policy_set_versao` fixada; reabrir reproduz o cálculo idêntico. |
| 9 | PPTX | Um `Job(render_pptx)` gera o comparativo financeiro no template master; totais **idênticos** ao snapshot; sai marcado "RASCUNHO INTERNO" enquanto houver DP provisória (DP-13). |

**Definição de pronto da fatia vertical:** um estudo real de renovação (ex.: o caso AMIL de 2 planos, limitado a ≤29 vidas) percorre 1→9 com uma operadora, gera PPTX com totais reconciliados e marca de rascunho, e todo o caminho fica auditável (proveniência + validações + aprovação). Só então adicionam-se os parsers restantes, um a um, com a entrada manual sempre como fallback.

---

## Parte 8 — O que fica explicitamente para depois (com razão)
- Parsers Unimed, Omint, Hapvida (adicionados um a um após a fatia vertical).
- Adapter Flui (formato inexistente hoje).
- Comparativos de rede, reembolso, regras, seguro de vida, odonto (portados do motor da skill como referência, não como arquitetura).
- Auto-match de subgrupo↔plano (DP-10 vira sugestão só após regra homologada).
- RBAC rico, multiusuário avançado, dashboards.
- Redis/Celery (só sob necessidade demonstrada).

---

## Apêndice — Rastreabilidade DP ↔ mecanismo de segurança

| DP | Onde é escolhida | Armazenada em | Bloqueio associado |
|---|---|---|---|
| DP-01 data idade | passo 3 | `Estudo.data_referencia_idade` | B-07 |
| DP-02 IOF | checkpoint | flags em Vida/OpcaoPlano/TabelaPreco | B-02 |
| DP-03 baseline | checkpoint | `Cenario.baseline_escolhido` | B-07 |
| DP-04 reajuste | passo 3 | `SubgrupoAtual.reajuste` | B-07 |
| DP-05 validade | automático + conferência | `DocumentoCotacao.validade_oficial` | alerta |
| DP-06 copart | checkpoint | `RegimeCopart` | B-05/B-06 |
| DP-07 precedência copart | checkpoint | `OpcaoPlano` (origem) | alerta >2% |
| DP-08 idade×preço | revisão de vidas | `Vida.flags` + `ProvenienciaCampo` | B-04 |
| DP-09 inclusão vidas | revisão de vidas | `Vida.incluida` | B-08 (via contagem) |
| DP-10 subgrupo↔plano | checkpoint | `AtribuicaoPlano` | B-06 |
| DP-11 arredondamento | automático | PolicySet + centavos | B-02 |
| DP-12 modalidade | configuração | `SubgrupoAtual.modalidade` | alerta |
| DP-13 rascunho | automático | `Entregavel.marca_rascunho` | — |
| DP-14 aprovação | checkpoint | `Usuario.papel` / `Aprovacao` | B-01 |
