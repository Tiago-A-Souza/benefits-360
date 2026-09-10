# Sistema de Estudos Newport — Registro Técnico de Alterações

**Período:** 7 a 16 de agosto de 2026
**Método:** validação com dados reais de quatro clientes, comparando o
resultado do sistema contra estudos já entregues.

---

## Índice

1. [Resumo](#1-resumo)
2. [Motor de cálculo](#2-motor-de-cálculo)
3. [Extração de planilha SISCOR](#3-extração-de-planilha-siscor)
4. [Extração de cotações em PDF](#4-extração-de-cotações-em-pdf)
5. [Declaração de parâmetros financeiros](#5-declaração-de-parâmetros-financeiros)
6. [Formatos de estudo](#6-formatos-de-estudo)
7. [Comunicação de erros](#7-comunicação-de-erros)
8. [Apresentação](#8-apresentação)
9. [Governança](#9-governança)
10. [Verificações estruturais](#10-verificações-estruturais)
11. [Validação contra estudos reais](#11-validação-contra-estudos-reais)
12. [Em aberto](#12-em-aberto)
13. [Gráficos da etapa 1](#13-gráficos-da-etapa-1)
14. [Colunas Tit. e Dep. sob demanda](#14-colunas-tit-e-dep-sob-demanda)

---

## 1. Resumo

Vinte e dois defeitos corrigidos. Seis produziam valores financeiros
incorretos sem qualquer sinalização. A suíte automatizada passou de 326 para
mais de 470 testes.

Duas categorias de estudo que não funcionavam passaram a funcionar: renovação
com múltiplos planos vigentes e seguro novo.

Três estudos reais foram reproduzidos ao centavo a partir dos arquivos brutos.

**O motor de cálculo não foi alterado.** Todas as correções ocorreram nas
camadas de extração, declaração de parâmetros, montagem de cenários e
apresentação. O núcleo financeiro estava correto desde o início — o que
falhava era o que chegava até ele e o que saía dele.

---

## 2. Motor de cálculo

### O que é

Uma única função pura, `calcular(estudo, policy) → resultado`, idêntica para
todas as operadoras e todos os estudos. Não conhece Amil, Porto ou SulAmérica.

Sequência:

```
idade na data de referência   →  faixa etária ANS (índices 0 a 9)
faixa                         →  valor na tabela do plano
tipo fiscal seguradora        →  aplica IOF de 2,38%
formato renovação             →  aplica reajuste, vida a vida
soma                          →  vida → subgrupo → seção → cenário
```

### Regras aritméticas

**Dinheiro é sempre inteiro em centavos.** Nunca ponto flutuante. Taxas em
basis points inteiros (IOF = 238 bps).

**Arredondamento half-up simétrico**, incluindo negativos:
`(numerador + denominador ÷ 2) ÷ denominador`.

**Estratégia homologada: `por_vida_entao_soma`.** O reajuste e o IOF são
aplicados a cada vida individualmente, e só depois somados. Aplicar sobre o
total produz resultado diferente.

> Exemplo real — Anistia, 36 vidas, reajuste de 10%:
> por vida então soma = **R$ 28.862,01**; sobre o total = R$ 28.862,04.
> Três centavos de diferença. O primeiro é o correto.

### Faixas etárias

Dez faixas, com limite de idade completa: ≤18, ≤23, ≤28, ≤33, ≤38, ≤43, ≤48,
≤53, ≤58, e 59+.

A idade é apurada na **data de referência** definida na configuração do
estudo, por idade completa — critério da ANS.

> **Divergência identificada com a planilha manual:** o método manual calcula
> idade por subtração de anos (`ano atual − ano de nascimento`), o que
> antecipa o envelhecimento de quem ainda não fez aniversário.
>
> Medido na base da Anistia: **3 das 41 vidas** caem em faixa diferente por
> esse motivo. No estudo ATEF, o titular aparece como 55 anos na planilha e 54
> no sistema — o sistema está correto.

### Estado

**Não foi alterado.** Validado contra três estudos reais e coberto pelas
suítes A a H.

---

## 3. Extração de planilha SISCOR

### 3.1 Base de comparação descartava beneficiários

**Antes:** o subtotal era montado por faixa etária. Se as vidas de uma faixa
tinham valores de fatura diferentes — situação comum, por adesões em datas
distintas — a faixa inteira era excluída do total.

**Impacto medido (Anistia):** faixas 19-23 e 34-38 tinham valores mistos.
**14 de 36 vidas fora da base** — R$ 9.183,23, ou 35% do valor. A tela exibia
«36 beneficiários» ao lado de um total que representava 22.

**Correção:** criada função única de agregação (`agregacao_faixa.py`),
compartilhada entre resumo e apresentação.

> **Invariante estabelecido:** o total é sempre a soma de todos os valores
> conhecidos. A homogeneidade dos valores dentro de uma faixa decide apenas se
> é possível exibir um valor unitário representativo — nunca se a faixa entra
> no total.

O documento passou a exibir, nessas faixas, a observação «Valores individuais
diferentes — total observado exibido».

### 3.2 Contador de dependentes fixo em zero

**Antes:** «41 vidas · 27 titulares · 0 dependentes». A soma não fechava. O
contador comparava o parentesco com o literal `"dependente"`, que não existe —
os valores possíveis são titular, cônjuge, filho e companheiro.

**Correção:** dependente passou a ser toda vida cujo parentesco não é titular,
com terceira categoria para parentesco ausente.

> **Invariante:** `titulares + dependentes + sem_parentesco = total de vidas`.

### 3.3 Total «observado» exibia valor calculado

**Antes:** o rótulo dizia «Total mensal observado na base», mas o número
trazia o reajuste aplicado — e calculado fora do motor, por multiplicação
sobre o total, com divergência de três centavos.

**Correção:** dois valores rotulados sem ambiguidade — vigente e reajustado —
com o reajustado vindo do mesmo caminho de cálculo do motor.

> **Invariante:** todo valor financeiro exibido vem do motor ou é a soma
> direta de valores importados. A camada de exibição não aplica taxas,
> reajustes nem arredondamentos próprios.

### 3.4 Mensagem de erro sem diagnóstico

**Antes:** planilha com layout incorreto produzia apenas «A planilha não
possui todas as colunas obrigatórias do layout piloto». O parser conhecia as
colunas faltantes e descartava a informação.

**Correção:** a mensagem passou a listar as colunas ausentes, o nome da aba
lida, e a identificar quando o arquivo não é uma posição cadastral.

### 3.5 Não havia como excluir beneficiário pela interface

**Antes:** a API suportava exclusão com motivo, mas a tela não oferecia a
ação. Operadores recorriam ao formulário de edição, com risco de apagar dados.

**Correção:** ação de exclusão com motivo obrigatório, linha marcada
visivelmente e reversível, contadores atualizados.

---

## 4. Extração de cotações em PDF

### 4.1 Amil — valores acima de mil reais truncados

**Causa:** a expressão de leitura exigia o ponto separador de milhar:

```
padrão antigo:  [\d]{1,3}(?:\.\d{3})*,\d{2}
```

Quando a Amil escreve `R$1073,96` sem o ponto, o padrão casava apenas com
`073,96`.

**Impacto medido:**

| Arquivo | Faixa | Extraído | Correto |
|---|---|---|---|
| `AMIL_BRONZE_SP_MAIS_TP` | 59+ | R$ 73,96 | **R$ 1.073,96** |
| `AMIL_PRATA_TP` | 59+ | R$ 683,47 | **R$ 1.683,47** |
| `AMIL_BLACK_R1` | 7 das 10 faixas | corrompidas | — |

No estudo IVTEC, com uma vida na faixa 59+: **R$ 1.000,00 por mês** a menos,
R$ 12.000 no ano. O estudo apresentaria economia inexistente.

**Correção:** padrão que aceita milhar com ou sem separador.

### 4.2 Amil — linhas de subtotal oferecidas como plano

**Antes:** cada arquivo produzia o dobro de opções. Metade eram linhas de
subtotal com valores esparsos, apresentadas como planos selecionáveis. Um
analista poderia montar um estudo inteiro sobre nada.

**Correção:** descarte com alerta `PDF-AMIL-003`. A contagem por arquivo caiu
pela metade em todo o corpus — sem perda de plano real.

### 4.3 Amil — nome do plano capturado de texto institucional

**Antes:** sete de oito planos do estudo Lunvox recebiam o nome «mais»,
capturado de frases da capa: «a 11ª marca mais valiosa», «as empresas mais
queridas». Os planos ficavam indistinguíveis na matriz de atribuição.

**Correção:** o nome passou a ser lido na vizinhança da tabela tarifária,
reconhecendo o padrão Amil (`PRATA QC COPART`, `OURO QP R COPART`).

> **Invariante:** o nome do plano é lido da mesma página e do mesmo contexto
> da tabela tarifária. Se não puder ser determinado com segurança, usa-se
> rótulo neutro numerado com alerta — nunca fragmento de frase.

### 4.4 Porto — série «P» descartada

**Antes:** de 18 planos por tabela, o parser extraía 11. Os sete descartados
eram os de nome alfanumérico: `P220 Q`, `P320 Q`, `P420 Q`, `P470 Q`,
`P520 Q`, `P220 E`, `P320 E`. Catorze planos por documento, considerando as
duas tabelas.

**Gravidade:** o `P220 Q COPAR` é o plano que a Newport apresentou ao cliente
ATEF. O sistema não conseguia extrair o plano do próprio estudo entregue.

**Correção:** reconhecimento de nomes alfanuméricos e verificação de
completude entre linhas detectadas e opções montadas.

### 4.5 SulAmérica — tabela ilegível

**Antes:** duas famílias de layout devolviam zero planos, com alerta
`PDF-SUL-001`. A causa era a anotação de quantidade que a SulAmérica
intercala entre os valores:

```
R$ 283,94
1 vida          ← interrompia a leitura
R$ 354,92
R$ 440,09
...
```

O parser esperava dez valores contíguos e desistia ao encontrar texto.

**Correção:** as anotações passaram a ser ignoradas na montagem da sequência
e **aproveitadas como dado** — «1 vida» na faixa 19-23 preenche a quantidade
cotada daquela faixa.

### 4.6 Upload em lote abortava no primeiro erro

**Antes:** o laço de envio percorria os arquivos dentro de um único bloco de
tratamento. Se o segundo PDF falhasse, o recarregamento da lista nunca
ocorria — os arquivos que subiram com sucesso não apareciam na tela.

**Correção:** tratamento por arquivo, recarregamento garantido, e resumo
individual por documento.

### 4.7 Extração sem resultado era beco sem saída

**Antes:** quando o parser não extraía nenhum plano, a tela oferecia apenas
«Ver PDF», «Voltar» e «Remover». A entrada manual existia em outro painel,
inacessível dali.

**Correção:** bloco de recuperação com preenchimento manual, herdando
operadora, número de cotação e vínculo ao documento de origem.

---

## 5. Declaração de parâmetros financeiros

Dois campos determinam o valor final e não pertencem ao cálculo — são
declarações sobre o dado.

### 5.1 Tipo fiscal assumia «seguradora» por omissão

**Antes:** quando o parser não conseguia extrair o tipo fiscal, o sistema
gravava «seguradora» — e seguradora implica IOF de 2,38%.

**Impacto:** toda cotação de operadora (Amil, Hapvida, Unimed, NotreDame) saía
inflada. No IVTEC: R$ 3.830,97 em vez de R$ 3.741,89.

O erro é assimétrico: sempre para cima, sempre desfavorecendo a proposta na
comparação.

**Correção:** o valor por omissão foi removido. Campo ausente permanece
ausente e exige declaração explícita.

> **Invariante:** nenhum campo que altere o valor calculado recebe valor por
> omissão. Quando o dado não pode ser extraído com segurança, é o operador
> quem declara.

### 5.2 Assimetria entre os dois campos

Antes da correção, `price_basis` desconhecido **bloqueava** o cálculo (B-02),
enquanto `tipo_fiscal` desconhecido **adotava um palpite** que alterava o
valor. Dois campos com o mesmo peso financeiro, tratados de formas opostas.

Agora ambos exigem declaração.

### 5.3 Referência das declarações

| Operadora | Tipo fiscal | IOF |
|---|---|---|
| Amil, Hapvida, Unimed, NotreDame | operadora | não incide |
| Porto Seguro, SulAmérica, Bradesco | seguradora | 2,38% |

A base de preço depende do documento. A Porto declara no rodapé da tabela:
«Valores em Reais e sem IOF».

---

## 6. Formatos de estudo

### 6.1 Renovação com múltiplos planos vigentes

**Antes:** a interface criava um cenário por proposta, com uma única
atribuição. O motor exige que cada cenário cubra **todos** os subgrupos com
vidas. Com dois ou mais planos vigentes, o bloqueio B-06 era inevitável —
nenhuma configuração resolvia.

Afetava Anistia (2 planos) e Lunvox (3 planos).

**Correção:** matriz de atribuição cenário × subgrupo. Cada coluna do
comparativo é um cenário que atribui uma proposta a cada subgrupo, com
preenchimento inicial automático e edição por célula para combinações mistas.

> **Invariante:** todo cenário cobre integralmente os alvos exigidos pelo
> formato do estudo. Se a aplicação considera um rascunho sincronizado, o
> motor não pode devolver bloqueio estrutural.

### 6.2 Seguro novo

**Antes:** o motor suportava o formato, mas a jornada não existia.

| Etapa | Problema |
|---|---|
| Criação | todo estudo nascia como renovação |
| Base | valor de fatura zerado gerava exceção nas 12 linhas |
| Configuração | exigia reajuste, baseline e precedência |
| Atribuição | gravava alvo por subgrupo; o motor exige por vida |
| Apresentação | tabela vazia; propostas exibiam o mesmo total |

**Correção:** escolha de formato na criação; isenção de valor de fatura;
etapa de configuração reduzida à data de referência; atribuição automática
por vida; apresentação sem coluna de plano atual, comparando as propostas
entre si.

### 6.3 Acomodação divergente entre plano atual e proposta

**Identificado no Lunvox:** três subgrupos, sendo um de enfermaria e dois de
apartamento. O preenchimento automático aplicava o mesmo plano a todos,
oferecendo enfermaria a quem tinha apartamento — rebaixamento de cobertura
apresentado como economia, sem aviso.

**Correção:** alerta de divergência de acomodação na matriz, no comparativo e
no documento gerado. Não bloqueia, porque upgrade proposital é caso legítimo —
mas torna a escolha consciente.

---

## 7. Comunicação de erros

O padrão dominante entre os defeitos encontrados: **o sistema tinha a
informação correta e não a comunicava.**

### 7.1 Bloqueios do motor invisíveis

**Antes:** a tela do comparativo exibia «Esperados 3 resultados calculados,
mas o motor retornou 0». O resultado do motor contém a lista completa de
bloqueios, com código, mensagem e alvo — e a informação era descartada.

**Correção:** lista de bloqueios com código, mensagem do motor, alvo resolvido
por nome e indicação da etapa a revisar.

### 7.2 Erros de compilação também invisíveis

Quando a falha ocorre antes do motor, não há bloqueios de motor a exibir e a
mensagem genérica reaparecia. Os erros de compilação passaram a ser exibidos
no mesmo formato, agrupados por origem.

### 7.3 Bloqueios repetidos e ilegíveis

**Antes:** o mesmo problema em três cenários gerava três itens idênticos, e a
mensagem citava identificadores internos:

```
Reajuste não definido para subgrupo d6821b0a-d707-435d-bcae-a6e4c125cb23
```

**Correção:** agrupamento por `(código, alvo)` com indicação de quantidade, e
substituição do identificador pelo nome do plano.

### 7.4 Deduplicação colapsava problemas distintos

**Antes:** pendências eram deduplicadas apenas por código. Dois subgrupos com
o mesmo problema exibiam um item só — o operador corrigia, recalculava, e o
segundo aparecia.

**Correção:** deduplicação por `(código, alvo)`.

### 7.5 Cotação importada sem plano selecionado

**Antes:** o operador podia importar quatro cotações, selecionar planos de uma
e avançar. As outras três ficavam fora do comparativo sem qualquer aviso.

**Correção:** indicador por documento, ação explícita de descarte com motivo,
e aviso ao avançar com documento não resolvido.

### 7.6 Diagnóstico operacional

Criado registro estruturado de falhas em formato JSONL, com endpoint de
consulta e exportação por botão. Instrumentado na importação SISCOR, na
extração de PDF, no cálculo e na aprovação.

Objetivo: permitir que problemas sejam relatados sem depender de o operador
saber descrevê-los. Não registra dados pessoais.

---

## 8. Apresentação

### 8.1 Identificadores internos no documento

**Antes:** o bloco de totais gerais exibia
«Proposta c1c42feb-e994-47e6-aa45-a6e7ae2b536b» enquanto as tabelas, no mesmo
documento, mostravam o nome correto.

**Correção:** rótulos resolvidos por nome, com numeração neutra quando o nome
não estiver disponível.

### 8.2 Propostas distintas com rótulo idêntico

Duas cotações SulAmérica do mesmo produto apareciam com o mesmo texto,
indistinguíveis. Rótulos passaram a ser qualificados pelo que os diferencia —
regime de coparticipação, acomodação.

### 8.3 Faixas etárias vazias

Estudo de três vidas exibia as dez faixas, sete apenas com travessões. As
faixas sem vidas passaram a ser omitidas.

### 8.4 Data em formato ISO

«Validade: 2026-08-14» passou a `14/08/2026`.

### 8.5 Divergência entre comparativo e apresentação

**Identificado no IVTEC:** o HTML exibia os valores corretos e a tela do
comparativo aparecia vazia. As duas camadas liam a estrutura de formas
diferentes — a correção de seguro novo entrara em uma e não na outra.

> **Invariante:** qualquer valor exibido no documento final está visível na
> tela de comparativo antes da confirmação. Nada é aprovado sem ter sido
> mostrado.

### 8.6 Matriz atribuía o total consolidado ao primeiro plano vigente

**Antes:** com dois planos vigentes, a matriz comparativa exibia uma única
coluna de contrato atual. O nome vinha do primeiro subgrupo; o valor vinha do
total consolidado do cenário. Na Anistia, a tela mostrava «AMIL S750 - Apto.»
carregando R$ 48.479,31 — o total dos dois contratos. O S750 responde por
R$ 29.386,76. O AMIL ONE S2500, R$ 19.092,55 e 39% da base, não aparecia em
nenhuma das três visões.

A aritmética estava correta: R$ 48.479,31 é o consolidado, e todas as
diferenças e percentuais fechavam contra ele. O defeito era de atribuição — um
número verdadeiro publicado sob um nome falso.

**Causa:** `adapters/motor_out.py`, `_montar_plano_atual`. A identidade vinha de
`rascunho.subgrupos_atuais[0]`; o valor, de
`propostas[0].numerico.atual_mensal_centavos`, que é
`ScenarioResult.total_atual_baseline_centavos`. O modelo `PlanoAtualComparativo`
representava um plano só, e a dependência de `propostas[0]` fazia o valor
exibido variar com a ordem das propostas.

`presentation/builder.py` já percorria todos os subgrupos desde a correção 6.1.
O adaptador nunca foi alcançado.

**Correção:** `planos_atuais: list[PlanoAtualComparativo]`, um por subgrupo, com
os subtotais que o motor já produzia por subgrupo
(`ResultadoSubgrupo.subtotal_atual_vigente_centavos`,
`subtotal_atual_reajustado_centavos`, `subtotal_proposta_centavos`) e que o
adaptador descartava. Agregação por `subgrupo_id` somando todas as seções do
cenário, porque atribuições mistas distribuem subgrupos entre regimes. O campo
`plano_atual` singular foi removido sem apelido de compatibilidade, para que
consumidor não migrado falhe de forma visível.

Nenhuma alteração no motor.

> **Invariante:** o valor exibido ao lado do nome de um plano é o valor daquele
> plano. Consolidado é rotulado como consolidado, nunca com o nome de um dos
> planos que o compõem.

### 8.7 Correções desta seção aplicadas em uma camada só

Ao validar 8.6 descobriu-se que **duas correções já registradas como concluídas
existiam apenas no `builder.py`**:

| Item | No documento | Na matriz |
|---|---|---|
| 8.2 rótulo qualificado | «Executivo R1 Apartamento (Nacional) (sem copart)» e «(copart 30%)» | duas colunas com o cabeçalho idêntico «EXECUTIVO R1 APARTAMENTO (NACIONAL)» |
| 8.4 data em formato brasileiro | 02/07/2026 | 2026-07-02 |

**Correção:** a qualificação de rótulo foi extraída para `presentation/rotulos.py`
e passou a ser chamada pelas duas camadas — implementação única, não uma cópia
em cada lado. As datas da matriz passaram a usar o mesmo `formatar_data_br` do
documento.

### 8.8 Índice interno de faixa exibido ao usuário

**Antes:** a visão por beneficiário da matriz exibia «BENEFICIÁRIO · FAIXA 4».
Era o índice interno da faixa somado de um. O documento exibia «29 a 33».

**Correção:** `faixa_rotulo` resolvido por `ROTULOS_FAIXA`, a mesma tabela que o
documento usa.

### 8.9 Observação de valores heterogêneos ausente na matriz

**Antes:** o documento marcava as faixas com valores individuais distintos
(«Valores individuais diferentes — total observado exibido»); a tabela de faixas
da matriz exibia apenas o total do grupo, sem sinalizar quais faixas eram
heterogêneas, sem unitária nas homogêneas e sem linha de totais.

Sem a observação, o leitor não distingue um total que é `unitária × quantidade`
de um que é soma de valores distintos — e pode dividir o total pela quantidade
para obter um preço que não corresponde a ninguém. Na Anistia, as quatro vidas
da faixa 19-23 pagam 458,95 · 536,98 · 536,98 · 536,98.

**Correção:** a tabela de faixas da matriz passou a exibir a observação nas
mesmas faixas que o documento, a unitária onde a faixa é homogênea, e rodapé de
totais por plano. Onde não há unitária, exibe apenas o total — não calcula
média.

---

> **Padrão de fundo desta seção.** Três correções (8.2, 8.4 e o equivalente de
> 6.1) foram aplicadas ao `builder.py` e nenhuma ao `motor_out.py`. Não foram
> três descuidos independentes: o adaptador nunca recebeu a varredura da camada
> de apresentação. Toda correção que toque conteúdo ou formatação exibida
> precisa de teste de paridade entre as duas camadas, construindo os dois
> payloads a partir do mesmo rascunho — os caminhos são distintos, porque o
> `builder` re-soma vida a vida a partir do snapshot e o adaptador lê os
> subtotais do `MotorResult`.

### 8.10 Unificação das etapas 5 e 6 — fase 2

A etapa 6 saiu da navegação. A matriz da etapa 5 passou a ser a tela de
comparativo, aprovação e exportação. O wizard tem cinco etapas.

**Renderizador único de faixas.** `ComparativoExperiencia.jsx` tinha um segundo
caminho para a tabela de faixas, sob a condição
`seguroNovo || !plano?.faixas?.length`, que somava as vidas no próprio cliente e
não exibia observação de heterogeneidade, unitária nem totais. Não era exclusivo
de seguro novo: qualquer renovação com `faixas` vazio caía nele. O adaptador
passou a fornecer `faixas_estudo` para seguro novo, usando `agregar_valores_faixa`
— a mesma função do documento — e o caminho alternativo foi removido.

**Versão do formato de snapshot.** `SNAPSHOT_VERSAO` existia declarada e não era
gravada. Passou a `2.8.0`, persistida no snapshot e no `payload_nucleo`. Snapshot
sem a versão gravada é conferido com o conjunto canônico anterior — verificado
que nenhum dos snapshots existentes passou a divergir.

**Seleção de propostas no hash.** `propostas_apresentacao` estava no payload e
fora de `CAMPOS_PAYLOAD_CANONICO`. Como na fase 2 a seleção define as colunas do
documento, ela entrou no conjunto canônico sob a versão 2.8.0, e alterar a
seleção passou a superar o snapshot. Sem isso seria possível confirmar cinco
propostas, aprovar, trocar para três e exportar sob um hash que ainda conferia.

**Snapshot em formato anterior.** `comparativo_do_snapshot` devolvia
`ComparativoResponse` com `planos_atuais` vazio ao ler payload gerado antes de
`37cf41f`, sem erro — o mesmo padrão silencioso de 8.6. Passou a recusar com
`SnapshotFormatoIncompativelError` e mensagem legível. Reconstruir pelo motor foi
descartado: reabriria um documento aprovado com apresentação que ninguém aprovou.

**Exportação a partir do congelado.** `ler_comparativo_congelado` é o leitor
único, com a guarda de formato. O documento passou a nascer do `comparativo`
congelado no snapshot aprovado, sem recálculo. O mesmo componente renderiza ao
vivo e congelado. Terceiro modo `resumo` acrescentado aos dois existentes.
`_montar_faixas` no adaptador foi removido — produzia número que ninguém lia.

**Governança na etapa 5.** O snapshot nasce no clique de «Confirmar comparativo»,
sem clique adicional, e a confirmação só é gravada se o congelamento der certo.
A aprovação virou seção da própria etapa 5, com nome do revisor, atestado e
autoaprovação justificada. Aprovar um snapshot novo passou a superar a aprovação
anterior do mesmo estudo — antes duas podiam coexistir sem critério, e a etapa 5
não tem seletor. O reparo de aprovações duplicadas legadas foi para a migração
`2.8.3`, com auditoria, e saiu do GET que o executava como efeito colateral.

### 8.11 Resumo executivo perdia o valor por plano de propostas de outro regime

**Antes:** no modo `resumo`, a coluna de uma proposta em regime diferente do
primeiro exibia travessão no lugar do valor por plano vigente, e o consolidado
correto logo abaixo. No estudo Anistia com seis propostas, a Executivo R1
(coparticipação 30%) aparecia sem os R$ 44.819,89 do S750 e os R$ 13.041,45 do
ONE S2500, que somam exatamente o R$ 57.861,34 exibido.

**Causa:** o modo `resumo`, criado na fase 2, paginava as propostas de três em
três atravessando regimes, enquanto a busca do valor por subgrupo permanecia
escopada à seção de regime. Os modos `faixas` e `beneficiario` já seccionavam por
regime e não tinham o defeito.

**Correção:** o resumo passou a seccionar por regime, como os outros dois modos.
Isso também comunica ao leitor que coparticipação 30% não se compara linha a
linha com sem coparticipação. A matriz ganhou paginação na impressão equivalente
à do documento — com seis propostas a última coluna era cortada, o que foi o
motivo de o defeito ter passado despercebido na validação.

### 8.12 Caixa de origem dos valores atuais — ajuste 2 da ata

A caixa oferecia «Valores importados do SISCOR» e «Tabela oficial do plano». Não
existe editor de `tabela_atual` na interface; 33 das 35 renovações no banco têm a
tabela vazia, e nenhum estudo tem as duas fontes coexistindo. Quatro estudos
escolheram «tabela oficial» e receberam o valor de fatura, porque
`_base_atual_vida` cai no ramo da fatura quando não há tabela — a interface pedia
uma decisão, registrava a resposta e o sistema fazia outra coisa sem avisar.

A caixa saiu da etapa 2. O campo `precedencia_atual_vida` permanece em
`EscolhasEstudo` e em `EffectivePolicy`: removê-lo do modelo faria snapshot
antigo reabrir sem ele, em silêncio, e `effective_policy` não tem guarda de
formato. O valor passou a ser gravado de forma explícita quando a fonte é única,
sem sobrescrever estudos que já tinham escolha confirmada. Quando as duas fontes
coexistirem, a caixa volta e o `APP-ESC-003` bloqueia até a decisão — o sistema
não escolhe sozinho.

No mesmo ajuste, o campo «valor informado já inclui IOF» saiu da etapa 2 e o
`BASES_IOF` da cotação manual ficou com duas opções. `DESCONHECIDO` e
`NAO_APLICA` permanecem no modelo: `finance.py:30` levanta erro quando
`price_basis` desconhecido chega ao cálculo, e isso é a proteção correta — a
extração determina a base em 1823 de 1823 opções de PDF, e o desconhecido é o
estado real de uma cotação manual não preenchida.

---

> **Cobertura.** A suíte foi de 495 para 571 testes, com os mesmos 13 pulados por
> indisponibilidade do corpus de PDF privado. Lacunas conhecidas: não há teste de
> tela, e as correções 8.8 e 8.9 passaram em toda a suíte com o JSX ainda
> exibindo o comportamento antigo. Validação visual em `localhost:5173` é
> obrigatória para qualquer alteração de renderização.

---

## 9. Governança

### 9.1 Exigência de confirmação humana estava desativada

Uma sessão anterior de desenvolvimento havia removido a validação que exige
confirmação humana de valores extraídos de PDF:

```
antes:  confirmado = bool(campo e campo.confirmado)
depois: confirmado = aceito            # aceito = "o campo tem valor"
```

Efeito comprovado: um valor com estado «revisar» e `confirmado = falso`
produzia registro marcado como confirmado no estudo.

Havia ainda um teste automatizado consagrando esse comportamento — o que
faria qualquer tentativa futura de restaurar a proteção parecer um erro.

**Correção:** a exigência foi restaurada. A confirmação passa a ocorrer pela
**seleção consciente do plano** pelo analista, ato que já existia no fluxo.
Nenhuma etapa adicional foi introduzida; o fluxo não travou.

O teste que protegia o defeito foi reescrito com o contrato invertido.

### 9.2 Organização do repositório

Havia 741 linhas de alteração não registrada, acumuladas de sessões
anteriores, cuja origem ninguém sabia explicar.

Foram auditadas e organizadas em sete commits temáticos, com documento de
auditoria descrevendo cada mudança, sua classificação e o risco de reverter.

Estabelecido protocolo: commit antes de iniciar tarefa, execução da suíte
antes de commitar, e verificação de estado limpo ao final.

---

## 10. Verificações estruturais

Além das correções pontuais, foram instaladas verificações que detectam esta
classe de erro **sem depender de alguém conhecer a resposta correta**.

### 10.1 Monotonicidade tarifária

Tabela de faixa etária cresce com a idade — regra da ANS, não de operadora.
Valor menor que o da faixa anterior gera alerta.

Implementada no pipeline, valendo para **todos os parsers**, inclusive de
operadoras que o sistema ainda não conhece.

> Esta verificação teria detectado sozinha o truncamento da Amil: a sequência
> `757,37` seguida de `73,96` é impossível numa tabela válida.

### 10.2 Completude de extração

Comparação entre linhas tarifárias detectadas na página e opções efetivamente
montadas. Divergência gera alerta informando quantos planos foram ignorados,
em vez de omissão silenciosa.

### 10.3 Reconciliação contra o documento

Os PDFs trazem os próprios totais:

```
Porto      →  «P320 Q COPAR · R$ 1.500,82 · 3 vidas»
SulAmérica →  «Prêmio R$ 2.215,76 + IOF R$ 52,74 = Total R$ 2.268,50»
```

O sistema soma a tabela por faixa e compara com o total impresso pela
operadora. É autoverificação que não depende de gabarito externo.

> Validado na prática: no estudo Anistia, o sistema calculou o Porto
> P320 Q COPAR em **R$ 1.500,82** — exatamente o valor que a Porto imprime no
> resumo financeiro da cotação. Sistema e seguradora chegaram ao mesmo número
> por caminhos independentes.

---

## 11. Validação contra estudos reais

### ATEF — renovação simples

3 vidas · 1 plano vigente · Porto e SulAmérica

| Item | Estudo entregue | Sistema |
|---|---|---|
| Total atual reajustado (11,98%) | R$ 2.387 | **R$ 2.387,45** |
| Porto P220 Q COPAR | R$ 1.365 | **R$ 1.365,09** |
| Economia anual | R$ 12.268 | **R$ 12.268,32** |
| Titular · faixa 54-58 | R$ 616 | **R$ 615,85** |
| Cônjuge · faixa 49-53 | R$ 498 | **R$ 498,43** |
| Dependente · faixa 19-23 | R$ 251 | **R$ 250,81** |

### Anistia Internacional — renovação multi-plano

41 vidas · 2 planos vigentes · 3 propostas Porto

| Item | Valor |
|---|---|
| Vigente total | R$ 43.285,14 |
| Reajustado (10%) | **R$ 47.613,62** |
| AMIL S750 (36 vidas) | R$ 26.238,22 → **R$ 28.862,01** |
| AMIL ONE S2500 (5 vidas) | R$ 17.046,92 → **R$ 18.751,61** |
| BRONZE BRASIL I Q | **R$ 26.873,14** · −R$ 248.885,76/ano |
| PRATA MAIS I Q | **R$ 29.707,78** · −R$ 214.870,08/ano |
| OURO MAIS I Q | **R$ 42.222,37** · −R$ 64.695,00/ano |

**Segunda execução independente — reajuste 12%.** O mesmo estudo foi
reprocessado com outro percentual de reajuste, o que revalida a base e o motor
sem reaproveitar nenhum número da primeira conferência.

| Item | Valor |
|---|---|
| AMIL S750 (36 vidas) | R$ 26.238,22 → **R$ 29.386,76** |
| AMIL ONE S2500 (5 vidas) | R$ 17.046,92 → **R$ 19.092,55** |
| Consolidado | R$ 43.285,14 → **R$ 48.479,31** |

R$ 29.386,76, não 29.386,81; R$ 48.479,31, não 48.479,36. A diferença de
centavos é a assinatura do `por_vida_entao_soma` e confirma que a estratégia
homologada é respeitada em mais de um percentual.

Os valores das propostas por plano vigente são independentes do reajuste e
conferem com o estudo entregue: PRATA MAIS I Q em R$ 23.607,17 no S750 e
R$ 6.100,61 no ONE S2500; OURO MAIS I Q COPAR 30 em R$ 27.512,49 e R$ 7.109,88.
Estes seis valores estão travados em teste.

Vinte e quatro valores conferidos, mais dez relações de coerência interna do
documento.

### IVTEC — seguro novo

12 vidas · sem plano vigente · 2 propostas Amil

| Item | Estudo entregue | Sistema |
|---|---|---|
| Amil Bronze SP + TP | R$ 3.741,89 | **R$ 3.741,89** |
| Amil Prata TP | R$ 5.652,04 | **R$ 5.652,04** |
| Diferença entre propostas | — | R$ 1.910,15 |

### Cobertura da validação

| Dimensão | Coberto |
|---|---|
| Escala | 3 a 47 vidas |
| Formato | renovação e seguro novo |
| Planos vigentes | nenhum, um, dois, três |
| Tipo fiscal | operadora e seguradora |
| Coparticipação | sem, parcial, percentual |
| Operadoras | Amil, Porto, SulAmérica, HapVida |

---

## 12. Em aberto

### Consentimento do plano atual (etapa 2)

O checkbox «Revisei e confirmo as informações do plano atual» saiu: a
atestação do operador acontece na aprovação do snapshot, na etapa 5, e o
checkbox era uma segunda declaração para a mesma coisa.

O campo `escolhas.baseline_escolhido.confirmado` (e
`escolhas.precedencia_atual_vida.confirmado` quando a precedência é exigida)
**permanece no modelo** — removê-lo faria snapshot antigo reabrir sem ele,
em silêncio. O «Próxima etapa» grava esses campos de forma explícita ao
avançar da etapa 2. O consentimento passou a ser derivado do avanço.

### Regras comerciais — confirmações pendentes com o Wesley

A aba «Regras contratuais» do documento lê `docs/regras_comerciais_base.csv`.
Duas pontas ficam abertas, sem efeito no casamento atual:

1. **«Unimed os Bandeirantes»** — a pesquisa não localizou operadora com esse
   nome exato. Pode ser imprecisão da planilha. A chave e os aliases
   (`Unimed dos Bandeirantes`, `Unimed Bandeirantes`) ficam como estão até
   confirmação. Não casar com Seguros Unimed nem com Unimed regional.

2. **Linha de produto Hapvida / NotreDame** (e-mail do Wesley): Smart é
   Hapvida; Advance, Premium e Infinity são NotreDame. **Não usamos isso para
   casar operadora.** Serve só se a cotação vier sem operadora identificada —
   e ninguém decidiu usar. Hapvida e NotreDame continuam entradas distintas
   (valores iguais por confirmação do Wesley; Fábio, 26/08, a Hapvida
   reseparando a NotreDame).

O casamento é igualdade após `normalizar_cabecalho`
(`siscor_importer/normalize.py:29`). Nunca «contém», em especial nunca
«contém Unimed». Operadora não reconhecida simplesmente não vira coluna.

### Correções mapeadas

| Item | Efeito |
|---|---|
| Registrar o parser Bradesco em `FAMILIAS` (existe, não está ativo) | conclui IVTEC e Lunvox |
| Deduplicar planos idênticos vindos de documentos distintos | elimina colunas repetidas |
| Regime de coparticipação da Amil fixado como «parcial» | rótulo correto no documento |
| Acomodação ausente não gera aviso | **resolvido** — Frente 2: `APP-ACO-002` informa incompleto |
| Revisar tipo fiscal gravado em estudos anteriores à correção | dado legado |
| Etapa 1 exige plano e seguradora mesmo em seguro novo | lista de vidas simples |
| Duas implementações do formatador de reais | divergência futura entre as camadas |
| Paginação da matriz para impressão | última coluna cortada com 5 propostas |
| Cabeçalho da coluna de contrato atual repete o rótulo | «CONTRATO ATUAL / CONTRATO ATUAL / vários planos» |
| `_th_proposta(..., [], ...)` no modo beneficiário | terceira superfície do 8.2 — ver abaixo |

### Adaptador zera campos que existem no rascunho

Mesmo padrão dos subtotais por subgrupo (§8.6): o dado está no rascunho e o
adaptador de apresentação descarta.

`presentation/builder.py`, `_mapear_plano`, gravava `modalidade=None` mesmo
com `SubgrupoAtualRascunho.modalidade` preenchido (Anistia: `compulsorio` nos
dois subgrupos). O HTML saía «—» nos dois blocos. A adesão compulsória não
chegava ao renderer. `PlanoAtualComparativo` também não tem o campo — o
`motor_out` nunca o copia.

**Corrigido nesta alteração:** `_mapear_plano` lê `sg.modalidade` e o
documento exibe «Compulsório» / «Adesão» no bloco do contrato atual. A
proposta **não** herda a modalidade do vigente; continua «—» até a cotação
trazer o campo.

**Ainda na mesma situação — não corrigir agora:**

| Campo no rascunho | Onde some |
|---|---|
| `SubgrupoAtualRascunho.tipo_fiscal` | não existe em `PlanoAtualApresentacao` |
| `SubgrupoAtualRascunho.fatura_price_basis` | idem |
| `SubgrupoAtualRascunho.subtotal_atual_impresso` | idem; conferência usa outro caminho |
| `OpcaoPropostaRascunho.modalidade` quando a cotação não preenche | «—» no bloco de propostas (ausência real do dado, não descarte do vigente) |

### Cabeçalho SISCOR com caracteres invisíveis (NBSP)

Planilha real da Anistia (e outras origens Excel/SISCOR) pode trazer **espaço
não separável (U+00A0)** e outros invisíveis nos cabeçalhos de mais de uma
palavra — visualmente idênticos a espaço comum (`CPF\xa0TITULAR`,
`TIPO\xa0DE\xa0VIDA`, `DATA\xa0DE\xa0NASCIMENTO`, `NOME\xa0DA\xa0MAE`).
Um `== "CPF TITULAR"` sem normalizar **não encontra** a coluna; `SEXO` (uma
palavra) casava e mascarava o defeito.

**Defesa:** `normalizar_cabecalho` colapsa NBSP/tab/quebra/BOM/ZWSP, remove
acentos e aplica caixa alta — não alias pontual. Fixture
`planilha_anistia_41_cabecalho_nbsp` + testes em `test_frente_base_colunas_siscor`
e `test_siscor_import`. **Não versionar** a planilha real.

Isto **voltará a acontecer** com planilha de outra origem — qualquer leitura de
cabeçalho deve passar pela normalização.

### Resolvidos (histórico — não apagar)

| Item | Commit / nota |
|---|---|
| Segundo renderizador de faixas no frontend (`seguroNovo \|\| !plano?.faixas?.length`) | `5483fe3` — ver §8.10; teste `test_jsx_tabela_faixas_sem_agregacao_no_cliente` |
| `round()` bancário em `_calcular_diff_bps` | `_calcular_diff_bps` delega a `bps_variacao` (half-up); `test_bps_variacao_half_up_nao_bankers` — `c96f861` |

### Pendência — dois tipos de acomodação convivendo

Com a dedução por letra no nome do produto **mantida** nos parsers Porto e Amil,
o sistema passa a ter duas origens: a **informada** (etapa 2 / conferência do
PDF) e a **deduzida na extração** (campo `acomodacao` preenchido pelo parser a
partir de Q/E/QC/QP no nome). Na tela ficam idênticas quando ambas existem.
Remover a dedução volta à mesa quando os golden dos parsers forem construídos.

**Golden (Frente 3):** a inferência Q/E/QC/QP está congelada nos JSON em
`tests/fixtures/cotacao_pdf/golden/amil/` e `…/golden/porto/`, com ressalva
explícita em cada arquivo (`_ressalva_deducacao_acomodacao`). Os testes em
`tests/test_frente3_golden_parsers.py` protegem o comportamento atual — não são
endosso; quebra deliberada ao remover a dedução exige atualizar o golden.

### Resolvido na FASE 3 — acomodação do cabeçalho em cenário misto

Com coluna = cenário, o cabeçalho usava a acomodação da primeira atribuição
(`opcao_referencia_cenario`). `_acomodacao_cenario` espelha `_regime_tipo_cenario`:
valor único quando todas as atribuições concordam, «misto» quando divergem.
Inverter a ordem das atribuições não muda acomodação, rótulo nem valor
(`test_05c_acomodacao_do_cenario_e_invariante_a_ordem`).

### Resolvido na FASE 4 — `coluna_id` = cenário

`chave_de_coluna` passou a devolver `cenario_id`. A identidade da coluna no
documento é o cenário, não a opção de referência. Os três estudos que
colidiam (`est-6ec6d7945a`, `est-629bfca67e`, `est-e1862b46be`) voltam a
mostrar as duas colunas. `APP-COL-001` permanece como rede: só dispara se a
chave voltar a colapsar.

`coluna_id` **não entra** no payload do comparativo — `cenario_id` já estava
lá. `SNAPSHOT_VERSAO` permanece `2.8.0`. Snapshot existente relê com o hash
gravado. Snapshot novo do mesmo conteúdo (sem o alerta) tem o mesmo hash,
exceto nos três estudos em que o `APP-COL-001` saiu das pendências.

`selecao_apresentacao` continua gravando `opcao_ids`. Os 49 estudos abrem
por fallback: um `opcao_id` resolve para todas as colunas cuja opção de
referência é aquela. Sem migração do JSON.

O resumo executivo segue o mockup `docs/coluna-por-cenario.html`: cabeçalho
misto «Cenário N» + composição, uniforme só com o nome do plano; cada célula
de plano vigente traz o plano atribuído (`.pl-cel`); consolidado = soma dos
grupos daquele cenário. Acomodação e coparticipação agregadas, «misto»
quando divergem.

### Beneficiário: cabeçalho sem `PropostaApresentacao` (8.2)

`html_renderer.py:698` chama `_th_proposta(op_id, [], rotulos)` no modo
beneficiário. Com a lista vazia, o cabeçalho não recebe o
`PropostaApresentacao` e perde a operadora. O nome vem do mapa de rótulos,
então o valor não erra — mas duas propostas com o mesmo nome base não são
desambiguadas nessa visão. É a terceira superfície do item 8.2. Correção:
passar `secao.propostas` em vez de lista vazia.

### Segundo renderizador de faixas etárias no frontend — RESOLVIDO

Histórico mantido: `ComparativoExperiencia.jsx` tinha caminho alternativo sob
`seguroNovo || !plano?.faixas?.length`. Removido em `5483fe3` (§8.10). O bloco
abaixo descrevia o defeito; não está mais aberto.

~~`ComparativoExperiencia.jsx` tem um caminho alternativo…~~ → ver tabela
«Resolvidos» acima.

### Lacunas conhecidas na cobertura de teste

| Lacuna | Consequência |
|---|---|
| Harness de mutações (Fases A–B) roda **1 célula** (`renovacao_2_2_3`), não 3 | cada mutação é validada numa configuração só; não cobre seguro novo, 1/3 planos nem mistos — corte `b844316` por teto de 3 min na suíte |
| `assert_paridade_rotulos_faixa` não é chamado no teste do gabarito Anistia | o único teste com dado real não confere rótulo de faixa |
| Nada assegura que `ROTULOS_FAIXA` contenha as faixas da ANS | a asserção compara o campo com a tabela, não a tabela com a realidade |
| `sum(vigente das faixas) == plano.vigente_centavos` não é assertado | o rodapé exibe vigente e reajustado; o teste trava só o reajustado |
| Nenhum teste de tela (Vitest) | correção que fique no payload e não suba ao JSX passa despercebida |
| `test_listagem_47_estudos_abaixo_de_300ms` no demo real | sob contenção da suíte (138 s → 163 s) a mediana pode cruzar 300 ms e o teste **skipa**; o gate de performance perde eficácia por carga da própria suíte, não por regressão do produto — o sintético em `tmp_path` continua sendo o assert rígido |

### Lacunas dos goldens sintéticos (Frente 3 — não coberto por fixture)

| Lacuna | Consequência |
|---|---|
| PDF escaneado Amil 8p / OCR Omint | só corpus privado ou testes OCR existentes |
| Coordenadas finas e drift de layout real | golden PyMuPDF não reproduz posicionamento comercial |
| Bradesco via pipeline (`FAMILIAS`) | parser testado com stub de tabelas; família ainda não registrada |
| SulAmérica: `secao is None` em página intermediária | páginas sem tabela são ignoradas sem alerta — comportamento documentado, não bloqueia happy path |
| Amil: páginas sem cabeçalho de faixa | ignoradas em silêncio até falta total (`PDF-AMIL-001`) |
| Paridade centavo-a-centavo com PDFs comerciais reais | os 13 testes `private_corpus` continuam necessários |

~~`assert obs_matriz == obs_html` com ambos vazios~~ — corrigido: ramo explícito
exige faixas sem observação ou igualdade não-vazia; coletas fase1/fase2 passam
a falhar se `n_falha > 0`.


### Escopo não construído

**Formato misto** — estudo que combina renovação de um grupo com inclusão de
vidas novas em outro. Caso do cliente EVOPE: 9 sócios em renovação (em dois
planos Bradesco distintos) e 22 colaboradores novos. O modelo admite um
formato por estudo. Requer decisão de produto antes de estimativa.

**Partes do estudo fora do software** — rede credenciada, reembolso,
procedimentos reembolsáveis, odontológico, seguro de vida, carências e
condições contratuais seguem sendo montados manualmente. Nunca estiveram no
escopo. A saída do sistema é HTML, não PowerPoint.

**Governança não exercitada** — as três travas da etapa de aprovação existem
no código mas não foram testadas nesta validação: gerar documento sem
aprovar, aprovar sem atestar revisão, e usar snapshot invalidado.

---

## 13. Gráficos da etapa 1

Pedido de Leonardo Brunetti na reunião de 01/09: uma rosca separando feminino
de masculino e barras verticais por faixa etária, ambas **opcionais** — com 9 a
12 vidas o gráfico é pobre; com 40 a 50 mostra concentração.

### Fonte única

A tabela `faixa × sexo × titular/dependente` da etapa 1 é produzida por
`montar_tabela_faixas_cotacao`
(`src/newport_app/siscor_importer/faixas_cotacao.py:79`) e entregue à tela em
`conferencia.tabela_faixas_cotacao`. **Os gráficos consomem esse mesmo objeto**:
`derivarGraficos` (`web/src/fluxo/graficosFaixas.js:96`) apenas relê as células
que a tabela exibe.

| Gráfico | Célula lida | Coluna correspondente na tabela |
|---|---|---|
| Rosca — feminino | `tit_f + dep_f` | Tit. F + Dep. F |
| Rosca — masculino | `tit_m + dep_m` | Tit. M + Dep. M |
| Rosca — não informado | `nao_informado` | Não informado |
| Barras — cada faixa | `total` | Total da linha |

Não existe segunda contagem nem segunda regra de faixa: o índice e o rótulo da
faixa vêm de `ln.faixa` / `ln.rotulo`, que a própria função da tabela derivou de
`newport_motor.faixa.faixa_em`. `tests/test_graficos_etapa1.py` recusa
`nascimento`, `Date(`, `idade`, `faixa_em` e `getFullYear` no módulo do gráfico,
e regenera as fixtures JSON pela função Python comparando-as byte a byte com o
que o teste JavaScript consome — nenhuma contagem paralela nasce sem quebrar a
suíte.

### Quando aparece

Sem coluna `SEXO` na origem (formato reduzido de 8 colunas) ou sem vida alguma,
`derivarGraficos` devolve `{ disponivel: false }`: **nenhum gráfico e nenhum
botão**. A etapa 1 fica idêntica ao que era.

### Sexo parcialmente preenchido

As vidas sem sexo **não são distribuídas** entre feminino e masculino nem
descartadas: viram uma terceira fatia «Não informado», coerente com a coluna de
mesmo nome que a tabela já mostrava. Nas barras elas continuam no `total` da
faixa. A alternativa — omiti-las da rosca — mudaria o total do gráfico em
relação ao da tabela; a outra — ratear — inventaria dado.

### Alternância

Botão ao lado de «Copiar tabela». Os gráficos **substituem** a tabela no mesmo
espaço; «Copiar tabela» desaparece enquanto não há tabela na tela e volta com
ela. Estado local de tela (`useState`) — não vira preferência, não entra no
rascunho, não toca o snapshot nem o hash.

### Implementação e acabamento

Sem biblioteca. A rosca é SVG (arcos por `stroke-dasharray` sobre um círculo de
raio 70 e espessura 34); as barras são CSS puro em grid. Tokens de `styles.css`,
numerais tabulares em todo valor, nenhum número escondido atrás de hover.

**Barras sem trilho.** A primeira versão punha um retângulo claro de altura total
atrás de cada barra. Ele competia com o dado e sugeria que cada faixa tivesse um
máximo próprio — leitura falsa. A distribuição agora é lida contra o espaço
vazio, com uma linha de base de 1px (`--line-strong`) que ancora sem devolver a
caixa; as pistas encostam (`gap: 0`, respiro por padding interno) para a linha
sair contínua. Na versão estreita a mesma linha vira vertical, à esquerda.

**Intensidade proporcional.** A concentração precisa saltar antes da leitura do
número. Cada barra tem sua cor derivada da própria fração, do azul claro ao
`--blue-2` cheio, dentro da família de tokens:

```css
background: color-mix(in oklab,
  var(--blue-2) calc(var(--intensidade) * 100%), var(--blue-100));
```

A curva está em `intensidadeBarra` (`web/src/fluxo/graficosFaixas.js:89`) e é a
**raiz** da fração, não a fração. A primeira versão usava o mapa linear
`28% + fração × 72%`, e uma faixa dominante o estragava: numa base com 1, 3, 4 e
10 vidas, as cores medidas em tela foram `#95b7ed`, `#79a2e5`, `#6b98e0` e
`#0f56c4` — 1, 3 e 4 praticamente indistinguíveis, e só o pico se destacando.
Com a raiz, os mesmos valores rendem `#84aae8`, `#5f8fdd`, `#5284d8` e
`#0f56c4`; o degrau de luminância entre 4 e 10 cai de 69 para 49 pontos e o
degrau entre 1 e 3 sobe de 22 para 28. A ordem das faixas não muda em nenhum
caso — a raiz é monotônica.

Os rótulos e os valores ficam fora da barra — acima e abaixo —, então nenhuma
intensidade os prejudica. O piso de altura subiu de 3px para 7px para que a
faixa de uma vida não suma ao lado de uma de duzentas; a cor clara dessa barra
impede que o piso superdimensione o valor.

| Caso-limite | Tratamento |
|---|---|
| Fatia de 0% | fora do desenho; aparece na legenda com o valor e `0%` |
| Fatia de 100% | círculo cheio, sem `stroke-dasharray` — sem emenda visível |
| Percentual que não soma 100 | maior resto (`percentuaisInteiros`); 3 iguais → 34/33/33 |
| Uma vida só | rosca cheia e uma coluna; as outras nove faixas com zero |
| Base grande | barra com piso de 7px e cor clara, escala pela maior faixa |
| Rótulo que colide | rótulo curto no eixo (`0–18`) e, abaixo de 700px, barras horizontais |
| Contêiner estreito | ≤900px coluna única; ≤700px barras horizontais |
| Impressão | sai o que está na tela; `break-inside: avoid` e cor exata |

Cor não é o único diferenciador: hachura diagonal sobre as fatias não femininas,
mais rótulo e valor visíveis na legenda. Cada gráfico tem `role="img"` com
descrição textual completa associada por `aria-labelledby`.

`web/scripts/previa-graficos.mjs` renderiza os nove casos em oito larguras
(360–1280px) para revisão de acabamento →
`.data/previa-graficos-etapa1.html`.

### O que não mudou

Motor, snapshot, hash, governança, TSV do «Copiar tabela», demais etapas e o
gabarito da Anistia — todos intactos e verificados na suíte.

---

## 14. Colunas Tit. e Dep. sob demanda

Pedido de Leonardo Brunetti na reunião de 01/09: na visão de faixas etárias do
documento exportado, titular e dependente ficam atrás de um botão — a
granularidade por faixa «não faz muito sentido» por padrão.

### Técnica

O documento exportado continua **sem script**. O controle é o mesmo padrão das
abas: um `input type="checkbox"` visualmente oculto (`#col-titdep`) imediatamente
seguido do `label`, e a visibilidade das colunas resolvida por seletor irmão:

```css
.tabela-faixas th.col-titdep, .tabela-faixas td.col-titdep { display: none; }
#col-titdep:checked ~ * .tabela-faixas th.col-titdep,
#col-titdep:checked ~ * .tabela-faixas td.col-titdep { display: table-cell; }
```

Um único checkbox governa **todas** as tabelas da seção — as duas da Anistia
abrem e fecham juntas. O rodapé deixou o `colspan="4"` e passou a ter uma célula
por coluna, para `display:none` em Tit./Dep. não desalinhá-lo.

### Rótulos

«Ver titulares e dependentes» / «Ocultar titulares e dependentes». Dizem o que o
clique faz, nos dois estados, com as palavras por extenso — Tit. e Dep. na tabela
são abreviação; no controle, não. O checkbox nativo anuncia o estado ao leitor
de tela; o texto visível muda com `:checked`.

### Impressão

Sai o estado da tela. O controle some (`display:none` no `@media print`); as
colunas seguem o `:checked`. Nenhuma regra de impressão força aberto ou fechado.

### O que não mudou

Matriz da etapa 5, resumo executivo, grupo familiar, totais, motor, snapshot,
hash e gabarito da Anistia. Renderer `html@2.11.0`.

---

## Nota final

Vale registrar o padrão dominante entre os vinte e dois defeitos: em quase
todos, **o sistema tinha a informação correta e não a comunicava** —
calculava parcialmente, assumia valor por omissão, ou exibia mensagem
genérica onde havia diagnóstico preciso disponível.

As correções mais valiosas desta validação não foram de aritmética. O motor
de cálculo não foi tocado. O que mudou foi o sistema tornar visível o que já
sabia — e recusar-se a decidir sozinho aquilo que altera o dinheiro.

**Adendo — fase 1 da unificação das etapas 5 e 6.** Seis correções adicionais,
todas de apresentação, todas do mesmo padrão: o sistema tinha o valor correto e
o exibia sob o rótulo errado, ou não o exibia. O motor continua intocado. A
diferença é que desta vez a origem foi identificada — a camada de adaptação
nunca havia recebido as correções aplicadas à camada de documento — e a defesa
construída foi estrutural: implementação única para rótulo e formatação, teste
de paridade obrigatório entre as duas camadas, e gabarito travado em centavos
inteiros.
