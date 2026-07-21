# Caderno de Decisões Provisórias — Sistema de Estudos Newport

> Artefato irmão da **Especificação de Implementação Segura v0.2**. Estratégia: *implementação tolerante a decisões pendentes*.
> Nenhuma regra abaixo é definitiva. Todas são **provisórias** até homologação de Wesley/Newport, mas o sistema já opera com elas de forma segura, reversível e auditável.
> Versão 0.2 · 2026-07-20

---

## 0. Como ler este caderno

Cada decisão pendente vira uma **Decisão Provisória (DP-NN)** com nove campos fixos:

1. **ID e status** — sempre `provisória` até homologação.
2. **Evidência disponível** — o que sustenta o comportamento hoje.
3. **Comportamento recomendado** — o que o sistema faz por padrão.
4. **Confirmação/escolha por estudo** — como o usuário confirma ou troca a regra naquele estudo.
5. **Armazenamento e versionamento** — onde a regra vive.
6. **Validação de bloqueio** — o que impede um resultado incorreto de avançar.
7. **Evolução sem migração** — como mudar depois sem reescrever o motor.
8. **Trilha de auditoria** — o que fica registrado.
9. **Critério de promoção** — quando vira `homologada`.

## 1. Mecanismo central (responde 5, 6 e 7 de forma global)

Este é o coração da estratégia. Sem ele, cada DP viraria um `if` espalhado no código — exatamente o que queremos evitar.

**Regra como dado, não como código.** Todas as DPs vivem em um **`PolicySet` versionado** (tabela relacional), não embutidas no motor. O motor de cálculo é uma **função pura** de `calcular(dados_do_estudo, policy_set)`. Ele nunca decide uma política; apenas aplica a que recebe.

- **`PolicySet`** — um conjunto de regras com uma **versão** (ex.: `v2026.07`) e um status global. Cada regra é uma **`PolicyEntry`** (`dp_id`, `valor_default`, `status: provisória|homologada`, `escopo: global|por_estudo`, `evidencia`, `versao`).
- **`StudyPolicyChoice`** — quando o usuário confirma ou troca uma regra num estudo, grava-se aqui a escolha (`estudo_id`, `dp_id`, `valor_escolhido`, `usuario_id`, `justificativa`, `criado_em`). Isso **não altera** o PolicySet global.
- **Cada Estudo fixa (`pin`) a versão do PolicySet** que usou. Reabrir um estudo antigo reproduz o cálculo com as regras da época.

**Consequências diretas:**
- **Armazenamento/versionamento (campo 5):** toda DP é uma linha em `PolicyEntry`, versionada; escolhas por estudo em `StudyPolicyChoice`.
- **Evolução sem migração (campo 7):** mudar uma regra = nova `PolicyEntry`/nova versão de PolicySet. Nenhuma tabela muda de forma; nenhum código do motor muda. Estudos antigos continuam válidos porque fixaram a versão anterior; estudos novos usam a nova. Recalcular é reexecutar a função pura.
- **Promoção a homologada (campo 9):** flip de `status` na `PolicyEntry` + congelamento de uma versão do PolicySet, registrado no Apêndice D da spec. Sem reescrita.

**Regra de ouro:** enquanto houver qualquer DP `provisória` relevante a um estudo, o entregável desse estudo sai marcado **"RASCUNHO INTERNO — sujeito a validação"** (ver DP-13).

---

## 2. Decisões Provisórias

### DP-01 — Data de referência para idade/faixa
1. **Status:** provisória.
2. **Evidência:** no piloto, operadoras cotaram em datas diferentes (SulAmérica 30/06, Amil 09/06); a skill usava "a data da cotação". Não há regra homologada sobre qual data governa a faixa quando elas divergem.
3. **Comportamento recomendado:** cada estudo tem uma **`data_referencia_idade` selecionável**. Default sugerido = data da cotação mais recente entre as propostas do cenário. Cada documento guarda também sua própria data (emissão/validade/vigência).
4. **Confirmação/escolha por estudo:** campo obrigatório no passo de configuração; o sistema propõe o default e o usuário confirma ou troca.
5. **Armazenamento:** `Estudo.data_referencia_idade` (escolha) + `DocumentoCotacao.data_*` (por documento) + DP-01 no PolicySet.
6. **Validação de bloqueio:** o cálculo de faixa **não roda** sem uma `data_referencia_idade` definida (bloqueio B-07).
7. **Evolução:** se a Newport homologar "sempre a data da cotação mais antiga" ou "data da proposta escolhida", muda-se o default no PolicySet; escolhas por estudo continuam soberanas.
8. **Auditoria:** registra data escolhida, se foi default ou override, usuário e timestamp.
9. **Promoção:** quando Wesley definir a regra oficial de qual data governa a faixa.

### DP-02 — IOF na fatura e na proposta
1. **Status:** provisória (relacionada à decisão A1).
2. **Evidência:** IOF de seguros = 2,38%; seguradoras (Bradesco, SulAmérica, Porto) entram com IOF, operadoras (Amil, Hapvida) sem. Mas **não está confirmado** se a fatura atual do cliente já vem com IOF embutido, e propostas trazem o total com/sem IOF de formas diferentes.
3. **Comportamento recomendado:** registrar **explicitamente** dois booleanos por origem — `fatura_inclui_iof` e, por opção de plano, `tabela_inclui_iof`. O `tipo_fiscal` da operadora define o IOF **esperado**. O sistema **reconcilia**: `soma_por_vida × (1+iof)` deve bater com o total impresso (tolerância de centavos). Se não reconciliar, não assume — **pede confirmação** de qual base está correta.
4. **Confirmação/escolha por estudo:** quando a reconciliação falha, o checkpoint exibe a divergência e exige que o usuário declare se a fatura/tabela já inclui IOF.
5. **Armazenamento:** flags em `Vida`/`OpcaoPlano`/`TabelaPreco` + DP-02 no PolicySet (regra de qual tipo_fiscal aplica IOF).
6. **Validação de bloqueio:** divergência de IOF não reconciliada e não confirmada = **bloqueante** (B-02).
7. **Evolução:** a regra "tipo_fiscal → IOF" é uma entrada de política; ajustável por operadora sem tocar o motor.
8. **Auditoria:** registra flags declaradas, resultado da reconciliação, confirmação manual (usuário, valor, timestamp).
9. **Promoção:** quando Newport confirmar o comportamento fiscal por operadora e se a fatura padrão inclui IOF.

### DP-03 — Baseline de comparação (vigente vs reajustado)
1. **Status:** provisória.
2. **Evidência:** os comparativos atuais mostram a diferença contra o valor **reajustado**; mas há casos em que faz sentido comparar contra o **vigente** (antes do reajuste). Não há regra única homologada.
3. **Comportamento recomendado:** o sistema **calcula os dois** (vigente e reajustado) e o usuário **escolhe qual é apresentado** no entregável. Default sugerido = reajustado (padrão histórico Newport).
4. **Confirmação/escolha por estudo:** seletor no checkpoint ("baseline apresentado: vigente / reajustado"); ambos ficam calculados e visíveis, só a apresentação muda.
5. **Armazenamento:** ambos os cálculos no `SnapshotCalculo`; a escolha em `Cenario.baseline_escolhido` + DP-03 no PolicySet.
6. **Validação de bloqueio:** exige uma escolha de baseline antes de gerar o cenário (B-07). O reajuste usado (DP-04) precisa estar definido.
7. **Evolução:** trocar o default é uma linha de política; a escolha por estudo permanece.
8. **Auditoria:** registra qual baseline foi apresentado e por quem.
9. **Promoção:** quando Newport definir o baseline padrão de apresentação (e as exceções).

### DP-04 — Reajuste da operadora atual
1. **Status:** provisória (decisão C17).
2. **Evidência:** reajuste PME é tabelado por operadora/período (Maio→Abril) em `REFERENCIA/reajustes/reajustes-pme.csv`. Valores mudam a cada período e podem estar desatualizados.
3. **Comportamento recomendado:** buscar o reajuste pela **operadora atual + período vigente**; exibir como valor provisório para **confirmação**. Se a operadora não estiver na base, ou o grupo tiver 30+ vidas (sinistralidade), **perguntar**.
4. **Confirmação/escolha por estudo:** o valor tabelado aparece pré-preenchido e editável no checkpoint, com a fonte citada.
5. **Armazenamento:** valor efetivo em `SubgrupoAtual.reajuste`; tabela de referência versionada; DP-04 no PolicySet aponta a versão da tabela.
6. **Validação de bloqueio:** renovação **não calcula reajustado** sem um reajuste definido (B-07).
7. **Evolução:** atualizar a tabela de reajustes é publicar nova versão do arquivo de referência; estudos fixam a versão usada.
8. **Auditoria:** registra valor aplicado, fonte (tabela+versão ou manual), quem confirmou.
9. **Promoção:** a regra "reajuste = da operadora atual, tabelado" já é adotada; promove-se quando a Newport validar a manutenção periódica da tabela.

### DP-05 — Validade oficial vs prazo operacional Newport
1. **Status:** provisória (substitui a decisão A3, que trocava uma pela outra).
2. **Evidência:** cada PDF traz uma validade oficial; a Newport aplicava uma "regra conservadora" (~30 dias; Amil ~10) que **sobrescrevia** a data do PDF — o que pode gerar informação comercialmente incorreta.
3. **Comportamento recomendado:** **dois campos separados, nunca um sobre o outro** — `validade_oficial` (extraída do PDF, imutável) e `prazo_operacional_newport` (regra interna). O entregável pode exibir os dois; o oficial nunca é adulterado.
4. **Confirmação/escolha por estudo:** o sistema preenche a validade oficial pela extração e o prazo operacional pela política; o usuário confirma ambos.
5. **Armazenamento:** `DocumentoCotacao.validade_oficial` + `prazo_operacional_newport` derivado da DP-05 no PolicySet.
6. **Validação de bloqueio:** validade oficial ausente/ilegível = alerta (não bloqueante); nunca substituir por regra interna sem registrar.
7. **Evolução:** o prazo operacional é uma política ajustável por operadora; a validade oficial vem sempre do documento.
8. **Auditoria:** registra ambos os valores e a origem de cada um.
9. **Promoção:** quando Newport formalizar o prazo operacional por operadora e a forma de exibição.

### DP-06 — Categorias de coparticipação
1. **Status:** provisória.
2. **Evidência:** a imagem do comparativo tem três colunas — **Sem Coparticipação, Coparticipação Parcial, Com Coparticipação** — e a nota "Importante" diz *"Coparticipação Parcial: aplica coparticipação apenas em terapias"*. Copart não é booleano.
3. **Comportamento recomendado:** copart estruturada como **regime** com tipo `{ sem | parcial | percentual | customizada }` + escopo (ex.: parcial→`["terapias"]`) + parâmetros (percentual, limitadores). Extração propõe o regime a partir do texto; usuário confirma.
4. **Confirmação/escolha por estudo:** no checkpoint, cada opção de plano tem um seletor de regime de copart; parcial exige marcar os procedimentos abrangidos.
5. **Armazenamento:** entidade `RegimeCopart` referenciada por `OpcaoPlano`/`SubgrupoAtual`; catálogo de regimes na DP-06 do PolicySet.
6. **Validação de bloqueio:** regime de copart indefinido numa opção usada em cenário = bloqueia aquele cenário (B-06 correlato).
7. **Evolução:** novos tipos de regime entram no catálogo de política; o motor trata regime como dado.
8. **Auditoria:** registra o regime atribuído, se veio de extração ou manual.
9. **Promoção:** quando Newport validar as categorias e o mapeamento por operadora/plano.

### DP-07 — Precedência da copart/reembolso da proposta sobre a base de referência
1. **Status:** provisória (decisão A4).
2. **Evidência:** caso real SulAmérica: valores de copart na proposta ~9,7% acima da base de referência. Quando a proposta traz o dado, ele deve prevalecer.
3. **Comportamento recomendado:** quando a proposta traz copart/reembolso, ela **prevalece**; a base de referência é fallback. Divergência >2% entre proposta e base = **sinalizar** para atualizar a base.
4. **Confirmação/escolha por estudo:** o checkpoint mostra proposta × base e qual foi usada; o usuário confirma.
5. **Armazenamento:** valores efetivos na `OpcaoPlano`; origem (proposta/base) marcada; DP-07 no PolicySet.
6. **Validação de bloqueio:** não bloqueante por si; divergência >2% vira alerta obrigatório de conferência.
7. **Evolução:** regra de precedência é política; o limiar de 2% é parâmetro ajustável.
8. **Auditoria:** registra fonte usada, divergência medida, encaminhamento de atualização da base.
9. **Promoção:** quando Newport validar a regra de precedência e o limiar.

### DP-08 — Nunca corrigir idade/nascimento/faixa pelo preço
1. **Status:** provisória, mas **inegociável no comportamento** (só o texto de exibição é ajustável).
2. **Evidência:** no piloto, o valor de uma vida sugeria data de nascimento provavelmente errada (2005 vs ~1996). O preço pode divergir por muitos motivos (plano diferente, tabela anterior, condição comercial, região, cobrança proporcional, erro de origem).
3. **Comportamento recomendado:** **detectar** a incompatibilidade idade×valor e **sinalizar como suspeita a investigar**. Jamais alterar idade/nascimento/faixa automaticamente. Resolução só por **correção na fonte** ou **override justificado**.
4. **Confirmação/escolha por estudo:** a vida sinalizada aparece com a suspeita e uma faixa candidata *apenas informativa*; o usuário corrige a fonte ou registra override com justificativa.
5. **Armazenamento:** flag em `Vida.flags`; override em `ProvenienciaCampo` (com justificativa).
6. **Validação de bloqueio:** vida com flag idade×valor **não resolvida** = **bloqueante** (B-04).
7. **Evolução:** o texto/limiar da suspeita é política; a proibição de auto-correção é invariante.
8. **Auditoria:** registra a suspeita, a decisão (correção na fonte ou override), justificativa, usuário, valor anterior.
9. **Promoção:** o comportamento não precisa de homologação para operar; homologa-se apenas o texto e o limiar de detecção.

### DP-09 — Inclusão de vidas (ativas sugeridas, revisável)
1. **Status:** provisória.
2. **Evidência:** a planilha SISCOR tem coluna `STATUS SEGURADO` (Ativo/…); o estudo em geral considera vidas ativas, mas há exceções (inclusões/exclusões previstas).
3. **Comportamento recomendado:** por padrão **sugerir** as vidas com `STATUS = Ativo`; inclusão e exclusão são **revisáveis** vida a vida.
4. **Confirmação/escolha por estudo:** tela de revisão de vidas com checkbox por vida; total recalcula ao incluir/excluir.
5. **Armazenamento:** `Vida.incluida` (bool) + motivo; DP-09 no PolicySet define o critério de sugestão default.
6. **Validação de bloqueio:** contagem final de vidas incluídas alimenta o cap de 29 (B-08); estudo sem nenhuma vida incluída = bloqueia.
7. **Evolução:** critério de sugestão (ex.: incluir dependentes de titular inativo) é política ajustável.
8. **Auditoria:** registra cada inclusão/exclusão manual, motivo, usuário.
9. **Promoção:** quando Newport definir o critério oficial de elegibilidade por status.

### DP-10 — Associação subgrupo atual ↔ opção de plano proposta
1. **Status:** provisória.
2. **Evidência:** cliente com 2 planos atuais (AMIL S750 e AMIL ONE S2500); a correspondência entre plano atual e plano proposto por cada operadora não é trivial nem única.
3. **Comportamento recomendado:** no piloto, a associação é **manual**. O usuário escolhe, por cenário, qual `OpcaoPlano` cada subgrupo/vida recebe. Nenhum auto-match.
4. **Confirmação/escolha por estudo:** matriz de atribuição no checkpoint (subgrupo × operadora → opção de plano).
5. **Armazenamento:** entidade `AtribuicaoPlano` (cenário, subgrupo/vida, opção) + DP-10 no PolicySet (flag "auto-match desabilitado no piloto").
6. **Validação de bloqueio:** subgrupo sem atribuição num cenário = **bloqueia** a geração daquele cenário (B-06).
7. **Evolução:** um auto-match sugerido pode ser adicionado depois como *sugestão* sem mudar o modelo (a associação continua explícita).
8. **Auditoria:** registra cada atribuição, quem fez.
9. **Promoção:** quando houver regra homologada de correspondência de planos (aí o auto-match vira sugestão confirmável).

### DP-11 — Arredondamento monetário por operadora
1. **Status:** provisória.
2. **Evidência:** o motor da skill multiplica valor×1,0238 e reconcilia com tolerância de centavos; cada operadora pode arredondar diferente na origem.
3. **Comportamento recomendado:** default = arredondamento para centavo (half-up) por vida; **reconciliar** a soma contra o total impresso na proposta. Divergência além da tolerância → conferência.
4. **Confirmação/escolha por estudo:** normalmente automático; só aparece quando a reconciliação falha.
5. **Armazenamento:** regra de arredondamento por operadora na DP-11 do PolicySet; valores sempre em **centavos inteiros**.
6. **Validação de bloqueio:** divergência soma×total além da tolerância e não resolvida = **bloqueante** (B-02).
7. **Evolução:** ajustar arredondamento por operadora é mudar a política; o motor usa inteiros e recebe a regra.
8. **Auditoria:** registra tolerância aplicada e resultado da reconciliação.
9. **Promoção:** quando Newport confirmar o arredondamento por operadora (idealmente conferido contra faturas reais).

### DP-12 — Modalidade de contratação
1. **Status:** provisória.
2. **Evidência:** padrão renovação PME = compulsório; adesão muda tabela (Bradesco/SulAmérica) quando há sócio fora da cotação.
3. **Comportamento recomendado:** default **compulsório**; se marcado adesão, disparar **checagem de composição societária** (aviso) e sinalizar impacto de tabela.
4. **Confirmação/escolha por estudo:** seletor de modalidade na configuração; adesão exibe o aviso societário.
5. **Armazenamento:** `SubgrupoAtual.modalidade`/`OpcaoPlano.modalidade`; DP-12 no PolicySet (default).
6. **Validação de bloqueio:** não bloqueante; adesão sem confirmação do aviso = alerta.
7. **Evolução:** default e regras por operadora são política.
8. **Auditoria:** registra modalidade escolhida e reconhecimento do aviso.
9. **Promoção:** quando Newport formalizar as regras de adesão×tabela por operadora.

### DP-13 — Marcação de entregável não homologado
1. **Status:** provisória (invariante de segurança enquanto houver DP aberta).
2. **Evidência:** decisão do Léo — enquanto regras não estão homologadas, entregáveis são rascunho interno.
3. **Comportamento recomendado:** todo PPTX gerado com qualquer DP `provisória` relevante recebe marca **"RASCUNHO INTERNO — sujeito a validação"**. Some quando as DPs aplicáveis estiverem homologadas.
4. **Confirmação/escolha por estudo:** automático; o sistema mostra ao usuário quais DPs mantêm a marca.
5. **Armazenamento:** `Entregavel.marca_rascunho` (bool) + lista de DPs provisórias que a acionaram.
6. **Validação de bloqueio:** não bloqueia a geração; bloqueia a classificação como "homologado".
7. **Evolução:** a marca é função do status das DPs no PolicySet; nada a reescrever.
8. **Auditoria:** registra quais DPs estavam provisórias na geração.
9. **Promoção:** a marca desaparece automaticamente quando todas as DPs aplicáveis ao estudo forem homologadas.

### DP-14 — Papel de revisor (temporário) e autoaprovação
1. **Status:** provisória.
2. **Evidência:** precisão é o princípio máximo; o checkpoint precisa de um aprovador distinto do analista, mas ainda não há estrutura de papéis definida pela Newport.
3. **Comportamento recomendado:** dois papéis no piloto — **Analista** (cria, extrai, corrige, submete) e **Revisor** (aprova o snapshot). Revisor pode ser temporário. Autoaprovação só se explicitamente habilitada e **registrada como decisão**.
4. **Confirmação/escolha por estudo:** a aprovação exige um usuário com papel Revisor; autoaprovação exige flag consciente com justificativa.
5. **Armazenamento:** `Usuario.papel`; `Aprovacao` guarda revisor; DP-14 no PolicySet (autoaprovação on/off).
6. **Validação de bloqueio:** snapshot/entregável final **não sai sem aprovação** (B-01); autoaprovação sem flag registrada = bloqueio.
7. **Evolução:** um RBAC mais rico entra depois sem mudar o modelo (papel já é atributo).
8. **Auditoria:** registra quem aprovou, quando, e se foi autoaprovação (com justificativa).
9. **Promoção:** quando Newport definir a política oficial de aprovação/segregação de funções.

---

## 3. Resumo de promoção

| DP | Tema | O que homologar | Dono |
|---|---|---|---|
| DP-01 | Data de idade/faixa | Qual data governa a faixa quando propostas divergem | Wesley |
| DP-02 | IOF | Comportamento fiscal por operadora + fatura inclui IOF? | Wesley/financeiro |
| DP-03 | Baseline | Baseline padrão de apresentação e exceções | Wesley |
| DP-04 | Reajuste | Manutenção periódica da tabela de reajustes | Newport |
| DP-05 | Validade | Prazo operacional por operadora e exibição | Wesley |
| DP-06 | Copart | Categorias e mapeamento por plano | Wesley |
| DP-07 | Precedência copart | Regra e limiar de divergência | Wesley |
| DP-08 | Idade×preço | Só texto/limiar (comportamento já seguro) | Léo |
| DP-09 | Inclusão de vidas | Critério oficial de elegibilidade | Wesley |
| DP-10 | Subgrupo↔plano | Regra de correspondência (para virar sugestão) | Wesley |
| DP-11 | Arredondamento | Arredondamento por operadora vs faturas reais | Wesley/financeiro |
| DP-12 | Modalidade | Regras de adesão×tabela por operadora | Wesley |
| DP-13 | Rascunho | Automático — sem homologação de conteúdo | — |
| DP-14 | Aprovação | Política de papéis/autoaprovação | Newport |

**Nada aqui trava o início da implementação.** O sistema roda com os defaults, marca o entregável como rascunho interno, bloqueia o que for perigoso, e registra tudo — pronto para promover cada regra quando Wesley validar.
