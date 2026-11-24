# Porto Seguro Saúde PME — mapa do vídeo do corretor

Fonte: `PORTO.mp4` (10 min 20 s, gravado em 16/10/2026, sem narração) e os quadros em `porto_quadros/`.
O número de cada quadro aparece entre colchetes. Revisei o vídeo inteiro: uma vista geral a cada 2 s,
OCR a cada 3 s e zoom nas telas de decisão.

Empresa: **L C GASTRONOMIA LTDA**, a mesma dos vídeos da SulAmérica e da Bradesco.

> O vídeo e os quadros mostram o CPF do corretor no login, e-mails e o CNPJ do cliente.
> Ficam fora do git, como `saida\`.

Este mapa separa duas coisas:
- **o processo do portal**, que vira regra do robô (Seções 2 a 6);
- **o que o corretor fez "por fora"** neste caso, que **não** vira regra (Seção 7).

## 1. O que o corretor produziu no vídeo

Ele calculou **5 cotações** e salvou **4 PDFs**:

| Cotação | Plano | Vidas | Total mensal (com taxa e IOF) | PDF salvo como |
| - | - | - | - | - |
| 3586191 | **Ouro Mais I** (Tradicional) | 4 | R$ 4.721,72 | "PORTO LC 4 VIDAS", renomeado depois para **"PORTO OURO MAXI LC 4 VIDAS"** ⚠ |
| 3586212 | Ouro Mais I | 3 | — | **nenhum** (calculou e abandonou) |
| 3586218 | **Ouro Max I** (Tradicional) | 3 | R$ 2.918,21 | "PORTO OURO MAXI LC 3 VIDAS" |
| 3586233 | **P470** (Porto Saúde) | 3 | R$ 2.179,37 | "PORTO OURO P470 LC 3 VIDAS" |
| 3586247 | **P470** | 4 | R$ 4.142,28 + taxa e IOF | "PORTO OURO P470 LC 4 VIDAS" |

⚠ O arquivo "PORTO OURO MAXI LC 4 VIDAS" contém o **Ouro Mais I**, não o Ouro Max I. O nome está
errado. Vale avisar a Newport.

Em todas: **Apartamento**, **coparticipação 30%**, plano anterior **NotreDame Intermédica**,
comissão **K001** e **sem** Cobertura Medicamentos.

## 2. Fluxo do portal, tela a tela (vira regra)

| # | Tela | O que acontece | O que o robô faz |
| - | - | - | - |
| 1 | **Login** `corretor.portoseguro.com.br` [01] | modal "Acesse o Corretor Online": **CPF + Senha** → ENTRAR. Aviso de **reCAPTCHA** | CPF e senha do cofre `NewportCotacoes/porto`. Se aparecer desafio de captcha: para e avisa, nunca tenta burlar |
| 2 | **Escolha da SUSEP** [02] | lista de códigos SUSEP (BBBBBB (P), AAAAAA (P), CCCCCC, DDDDDD, EEEEEE, …). Escolheu **AAAAAA**; o topo passa a mostrar "EDLAINE AAAAAA" | escolhe a SUSEP da engrenagem |
| 3 | **Home** `/novocol/homepage` [03] → **Saúde** [04] → **Cotar** | o cotador abre **dentro de um iframe**: `/novocol/iframe?url=https://www.saude.portoseguro.com.br/corretor/cotar?menuid=COL-049Q8…` | vai direto à página do cotador; trabalha com `frame_locator` |
| 4 | **Cotador: início** [25] | "Criar nova cotação", "Gestão de Apólice", "Acompanhar status de proposta", "Administração de Cadastros" + lista "Acompanhe o status da cotação / estudo" (filtro PME, busca por CNPJ ou nº) | **Criar nova cotação** |
| 5 | **1 de 4 — Dados iniciais** [06][07] | digita o **CNPJ** e o portal preenche pela Receita: razão social, CNAE, data de abertura, atividade econômica, CEP, logradouro, complemento, número, bairro, cidade, estado → **Próximo** | digita o CNPJ, espera o preenchimento terminar, confere a razão social. Se o CEP vier vazio ("Insira um CEP válido"), para e avisa |
| 6 | **2 de 4 — Produto e vidas** [08][09] | produto **Saúde** (a outra opção é Odonto). **Vidas: quantidade total**. **"Informe se esta empresa possui plano anterior"**: lista de operadoras (escolheu NotreDame Intermédica). **Distribuir vidas por faixa**: "00 a 18 anos (Clique aqui)" abre **uma caixa por idade, de 0 a 18 anos** (o bebê vai em "0 anos"). Depois: 19 a 23, 24 a 28, … 54 a 58, 59 a 60, e "+ Idades (Clique aqui)" para as idades maiores | preenche nesta ordem: total → plano anterior → faixas e idades. Confere que a soma bate com o total |
| 7 | **Validação de vidas** [10][27] | mensagem vermelha "Quantidade de vidas — [Faltam: N vidas]" ou "[Ultrapassou … em N vidas]" | se aparecer depois de preencher, para e mostra a mensagem |
| 8 | **Comissionamento e agenciamento** [11][12][29] | lista "Selecione uma das opções de comissão": H175, **K001 \| ag1(100%) \| ag2(100%) \| ag3(0%) \| Corretagem(5%)**, K070 (7,5%), **K130 (vem por padrão)**. O corretor troca **K130 → K001 todas as vezes**. Depois marca **"Li e estou de acordo com as regras de agenciamento"** → Próximo | escolhe a comissão da engrenagem (padrão K001) e marca a caixa. Confere o texto exato da comissão escolhida |
| 9 | **3 de 4 — Selecionar o plano** [13][14] | "Todas as vidas em um único plano" (a outra opção é "Distribuir em mais de um plano"). **Acomodação**: Apartamento / Enfermaria. **Coparticipação**: 0% / 10% / 20% / 30% (10% e 20% aparecem apagados). Grade com 3 linhas de produto: **Pro** (Regional: Ouro Pro, Diamante Pro), **Porto Saúde** (Nacional: P220, P320, P420, P470), **Tradicional** (Nacional: Bronze Brasil I, Prata Mais I, Ouro Mais I, Ouro Max I). "Preços indicativos/base", sem IOF | acomodação e coparticipação primeiro; depois clica no plano pedido pelo **nome exato**; confere "Selecionado" e o "Resumo da cotação" (plano, valor, vidas, acomodação, coparticipação) |
| 10 | **Mais vantagens** [14] | "Seguro Odonto + Vida" já vem marcado ("Sem custo adicional"). "Cobertura Medicamentos" (R$ 9,90 por vida) e "Remissão" (R$ 6,00 por vida) ficam **desmarcados** | não mexe no Odonto + Vida; confere que Medicamentos e Remissão estão desmarcados. **O ensaio para aqui**: o preço indicativo já aparece e nada foi criado |
| 11 | **Gerar orçamento** [15][16] | ⚠ **ponto sem volta**: cria o número da cotação. Abre o modal "Aumente as chances de fechar essa proposta!" → o corretor clica **"Emitir Sem Medicamentos"** | grava "gerando" antes do clique; no modal clica **Emitir Sem Medicamentos**, nunca "Adicionar à Proposta" |
| 12 | **4 de 4 — Detalhes da cotação** [17][18][19] | "A cotação nº **3586218** foi calculada com sucesso." · "Este orçamento **expira em 30 dias**." Dados do estipulante; **Valor total mensal**; Sub-total; **Taxa de inscrição**; **IOF Saúde**; vantagens incluídas; tabela por faixa (valor por beneficiário sem IOF) e informações do plano (reembolso, acomodação, coparticipação, abrangência, remissão) | grava o número logo que aparece; lê e confere os valores (Seção 4) |
| 13 | **Imprimir cotação** [20][21][22][23] | botões: Ir para página principal · Consulte o material/Kit · **Imprimir cotação** · Elaborar proposta. "Imprimir" mostra um carregando e **às vezes falha**: "**Erro ao gerar PDF** — Não foi possível gerar o PDF agora. Feche este aviso e clique novamente" (aconteceu 2 vezes em 4). Na segunda tentativa abre **uma aba nova com o PDF pronto** num link temporário (`quotation-pdf-s3-saude-prd.s3.ca-central-1.amazonaws.com/L_C_GASTRONOMIA_LTDA-<nº>.pdf?X-Amz-…`), com 15 a 16 páginas. Capa: "Indicativo de Preços Saúde - PME", data, CNPJ e razão social, corretora "K001 - AAAAAA", "Número e validade do estudo: 3586191 - 15/11/2026", data de vigência | clica em Imprimir; com "Erro ao gerar PDF": Fechar e tentar de novo, até 3 vezes com pausa. **Baixa o PDF direto do link da aba nova** (não precisa imprimir de novo). Confere que é PDF e que a capa tem o número da cotação e o CNPJ. Fecha a aba |
| 14 | **Próxima cotação** [25][26][28] | Ir para página principal → lista → ⋮ da última cotação → **"Duplicar orçamento"** (as outras opções são Visualizar, Editar e Elaborar proposta). O duplicado volta aos passos 1–3 já preenchido, **mas zera**: comissão volta para **K130**, a caixa de agenciamento fica **desmarcada** e o **plano anterior fica em branco** | duplica e **refaz e confere tudo** nos passos 1–3. Mais simples e igualmente válido: "Criar nova cotação" sempre (decisão na Seção 6) |
| 15 | **Nunca** | **Elaborar proposta**, "Adicionar à Proposta" (Medicamentos), Remissão, Editar uma cotação já calculada | — |

## 3. Valores do vídeo (para o simulador e para conferir)

Valores por beneficiário, sem IOF:

| Cotação | Plano | Vidas | Por faixa | Sub-total | Taxa de inscrição | IOF | Total mensal |
| - | - | - | - | - | - | - | - |
| 3586191 | Ouro Mais I | 4 (0 anos, 2× 34–38, 59–60) | 0 anos 864,89 · 59–60 2.385,57 | 4.591,96 | 20,00 | 109,76 | **4.721,72** |
| 3586218 | Ouro Max I | 3 (0 anos, 2× 34–38) | 612,67 · 1.111,35 | 2.835,36 | 15,00 | 67,84 | **2.918,21** |
| 3586233 | P470 | 3 | 456,59 · 828,56 | 2.113,71 | 15,00 | 50,66 | **2.179,37** |
| 3586247 | P470 | 4 | 429,93 · 780,19 · 2.151,97 | 4.142,28 | — | — | — |

Preços da grade (indicativos, sem taxa e IOF):
- **4 vidas:** P220 2.184,68 · P320 2.496,57 · P420 3.386,12 · P470 4.142,29 · Bronze Brasil I 2.671,06 · Prata Mais I 3.368,73 · Ouro Mais I 4.591,96 · Ouro Max I 5.556,53 · Ouro Pro 2.865,57 · Diamante Pro 4.328,20.
- **3 vidas:** P220 1.114,79 · P320 1.273,94 · P420 1.727,86 · P470 2.113,71 · Bronze Brasil I 1.362,98 · Prata Mais I 1.718,98 · Ouro Mais I 2.343,16 · Ouro Max I 2.835,36 · Ouro Pro 1.462,23 · Diamante Pro 2.208,58.

Conferências:
- soma (valor por beneficiário × vidas) = sub-total, com tolerância de centavos;
- **taxa de inscrição = R$ 5,00 por vida**;
- **IOF = 2,38% × (sub-total + taxa de inscrição)**, conferido nas três cotações acima;
- total mensal = sub-total + taxa + IOF;
- o valor por vida **muda com o total de vidas** (P470, faixa 0–18: 456,59 com 3 vidas e 429,93 com 4). Ler os valores só depois de preencher tudo.

## 4. Regras propostas para o robô

1. **1 plano pedido = 1 cotação = 1 PDF.** Não existe processo ou oportunidade que agrupe as cotações.
2. **Anti-reemissão:** CNPJ + total de vidas + idades e faixas + plano anterior + comissão + acomodação + coparticipação + plano + extras.
   - Grave "gerando" antes de **Gerar orçamento**.
   - Se cair depois do clique, **não gere outra**: procure na lista "Acompanhe o status" pelo CNPJ (status "Calculada"), abra por **Visualizar** e baixe o PDF. Se não achar com certeza, "Conferir no portal".
3. **Ensaio:** vai até o passo 3 com o plano selecionado e o resumo lido, e para **sem "Gerar orçamento"**. Nada é criado no portal.
4. **PDF:**
   - Use o link da aba que o "Imprimir cotação" abre: baixe o arquivo original.
   - "Erro ao gerar PDF" é normal no portal: feche o aviso e tente de novo (até 3 vezes).
   - Se não conseguir, a cotação já existe: fica "Conferir no portal". Não gere outra.
5. **Iframe:** o cotador fica dentro de um iframe. Os avisos ("Erro ao gerar PDF", modal de Medicamentos) e o carregando aparecem dentro dele.
6. **Coisas na frente dos cliques:** banner "Está com dúvidas sobre como utilizar o novo sistema de cotação?" (fechar), botão de chat no canto inferior direito, overlays de carregando.
7. **Vidas 0–18:** cada vida até 18 anos precisa da idade exata (caixas de 0 a 18 anos). Acima de 60 anos, por "+ Idades", a calibrar.
8. **Login com reCAPTCHA:** o risco desta operadora é o reCAPTCHA bloquear o robô. Na calibragem use "Mostrar a janela do portal". Se aparecer desafio, o robô para e pede ao corretor na nossa tela. Mantenha a sessão no perfil do navegador para logar o menos possível.

## 5. Engrenagem do robô Porto (padrão = o que o vídeo mostra)

| Tela | Campo | Padrão |
| - | - | - |
| Login | CPF e senha (cofre `NewportCotacoes/porto`) | — |
| Login | Código SUSEP | AAAAAA |
| Vidas | Produto | Saúde |
| Comissão | Opção de comissão (texto exato da lista) | **K001** \| ag1(100%) \| ag2(100%) \| ag3(0%) \| Corretagem(5%) |
| Comissão | Aceitar regras de agenciamento | Sim |
| Plano | Distribuição | Todas as vidas em um único plano |
| Plano | Acomodação | Apartamento |
| Plano | Coparticipação: Com (30%) / Sem (0%) / Com e sem | **Com, 30%** (como no vídeo) |
| Vantagens | Cobertura Medicamentos / Remissão | Não / Não ("Emitir Sem Medicamentos") |
| Planos | planos que já vêm marcados | nenhum (escolhidos na Nova cotação, nome exato da grade) |
| PDF | nome na pasta do cliente | `PORTO {plano} {nome curto da empresa}.pdf`. Opcional: `{vidas} VIDAS` no fim, como o corretor fez |

O **plano anterior** não é padrão: vem da Nova cotação (campo "Operadora atual"), com um de-para de
nomes para a lista da Porto (ex.: NOTREDAME → "NotreDame Intermédica"). Se não tiver plano anterior,
calibrar a opção da lista ("Não Possui Plano Anterior" aparece nela).

## 6. Decisão pendente: duplicar ou criar nova

O corretor faz a 2ª cotação em diante com **"Duplicar orçamento"**. Mas o duplicado zera a comissão,
a caixa de agenciamento e o plano anterior, e mantém as vidas antigas, o que causou o erro de vidas
no vídeo. As opções são:
- **Duplicar** (como no vídeo): o robô refaz e confere todos os campos de qualquer forma;
- **Criar nova cotação** sempre: o mesmo número de telas, sem resíduo da cotação anterior.

Recomendação: **Criar nova cotação**. O resultado no portal é igual (uma cotação nova e independente)
e o risco de levar um campo errado da anterior desaparece.

## 7. O que o corretor fez "por fora" — NÃO vira regra

| No vídeo | Por que não é regra | No robô |
| - | - | - |
| Abriu o **Outlook** para ler o "Pedido de Estudo PME Familiar — L C Gastronomia / Calandrini" e tirar os dados (de 0:36 a 1:06) [05] | é a origem dos dados deste cliente | os dados vêm da Nova cotação ou da planilha |
| Cotou **3 vidas e 4 vidas** para a mesma empresa (a 4ª vida tem 59–60 anos) | é o estudo deste cliente (dois cenários), não um padrão da Porto | cada cenário é um pedido. Se a Newport faz isso sempre, vira um recurso futuro: "cenários de vidas" |
| Escolha dos planos (Ouro Mais I, Ouro Max I, P470) | escolha comercial para este cliente | os planos vêm da Nova cotação |
| Calculou a **3586212** (Ouro Mais I, 3 vidas) e **abandonou** sem PDF [30] | tentativa ou mudança de ideia | o robô só gera o que foi pedido |
| Os **nomes dos arquivos**: salvou "PORTO LC 4 VIDAS", depois **renomeou** pela janela de salvar para "PORTO OURO MAXI LC 4 VIDAS" (nome errado, o plano é Ouro Mais I) e corrigiu o erro de digitação "PORTO OURO PLC 3 VIDAS" [24] | edição manual e inconsistente | nome pelo modelo da engrenagem; o robô nunca renomeia arquivos que já estão na pasta |
| **Reimprimiu o PDF** pelo Adobe Acrobat ("Imprimir → Salvar como PDF") | o portal já entrega o PDF pronto | baixa o arquivo original |
| Aviso do Acrobat para "Fazer login com Google" (Wesley) | é do navegador dele | — |
| Ordem em que digitou as vidas (gerou o erro "Ultrapassou … em 1 vida" no duplicado) [27] | erro de digitação | total primeiro, depois as faixas |
| Caminho pela página Saúde / Links úteis | só navegação | vai direto ao cotador |
