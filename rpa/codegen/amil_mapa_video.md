# Amil (vendasmil) — Cotação PME: mapa do vídeo do corretor

Fonte: `AMIL.mp4` (3 min 32 s, gravado em 16/10/2026, sem narração) e os quadros em
`amil_quadros/`. O número de cada quadro aparece entre colchetes nas tabelas abaixo.

Empresa do vídeo: **CALANDRINI HEALTHSPAN LTDA**. É a segunda empresa do "Estudo PME Familiar". A
primeira é a L C Gastronomia, que aparece nos vídeos da SulAmérica e da Bradesco.

O vídeo tem 4 vidas: 1 na faixa até 18, 2 na faixa 34–38 e 1 na faixa 59 ou mais.

São três cotações, uma por plano: **PLATINUM R1 COPART**, **AMIL BLACK I R1 COPART** e
**AMIL S2500 R1 QP COPART**.

> O vídeo e os quadros mostram e-mails, códigos de login, CNPJ e o pedido de estudo com dados da
> família do cliente. Ficam fora do git, como `saida\`.

## 1. O que muda em relação à SulAmérica e à Bradesco

| Assunto | SulAmérica / Bradesco | Amil |
| - | - | - |
| Login | CPF/e-mail + senha | `vendas.amil.com.br/login` (vendasmil). A 1ª etapa não aparece no vídeo. Depois vem um **código de verificação de 8 dígitos enviado por e-mail** (para we***@newportconsultoria.com.br, válido por 15 min), com os botões "Verificar código", "Reenviar código" e "Voltar". O corretor copia o código do Outlook. O e-mail vem de `mail@noreply.amil.com.br`, com assunto "Código de verificação do login". A caixa dele tem códigos de 12:01, 13:24 e 13:30 do mesmo dia: **o login com código acontece várias vezes ao dia** |
| Cadastro da empresa | CNPJ e o portal confere | **Oportunidade PME**: o CNPJ é digitado e o portal preenche o resto pela Receita (razão social, fantasia, abertura, natureza jurídica, atividade, MEI e endereço completo) → **Concluir Oportunidade** gera o número **OPP-…** |
| Unidade de cotação | 1 protocolo por plano / 1 processo com cálculos | **1 oportunidade por empresa** e **1 cotação (COT-…) por plano**. Para o próximo plano: volta à oportunidade → **Criar Cotação** |
| Coparticipação | opção separada | **vem no nome do plano**. A lista só tem planos "COPART" e "COPART TP". O corretor usou os "COPART" sem TP |
| Preço | tela do plano | grade com as 10 faixas: **Qtd. vidas (+/−), Valor por vida e Subtotal**. O valor por vida **muda conforme o total de vidas** (Platinum até 18: R$ 540,32 com 0 vidas e R$ 452,13 com 4; S2500 até 18: R$ 1.002,35 com 3 vidas e R$ 838,76 com 4) |
| Ponto sem volta | emitir / Gerar processo | **"Concluir Cotação"**: o status vai de "Em Digitação" para "Concluída" e o portal gera o PDF. A oportunidade e o número COT já existem antes |
| PDF | download / pop-up de impressão | o portal gera `cotacao-COT-XXXXXXX.pdf` (cerca de 1,5 MB, 8 páginas): "Gerando PDF…" → aviso "PDF Gerado" → **Baixar PDF** |
| Recuperar PDF | difícil | fácil: a oportunidade lista "Cotações da Oportunidade" (ID, valor, vidas, status, ícone de olho). Uma cotação concluída pode ser reaberta para baixar o PDF sem criar outra |
| Validade | 45 / 40 dias | o Resumo Geral mostra **"Data de validade" de 1 dia** (criada 16/10 13:30, validade 17/10 13:30) |
| Promoções | — | Platinum e Black: **50% de desconto na 1ª e 2ª parcelas** ("Plano elegível"). S2500: sem desconto. Dental **DENTAL BRONZE PJ PROMO** com R$ 0,00 por 12 meses (depois R$ 14,50 por vida). Aditivo **AMIL RESGATE SAÚDE I** (promocional por 12 meses, R$ 0,00) |

## 2. Fluxo tela a tela

| # | Tela (endereço) | O que o corretor fez no vídeo | O que o robô faz |
| - | - | - | - |
| 1 | **Login** `vendas.amil.com.br/login` [01] | (1ª etapa fora do vídeo) → "Código de verificação enviado para we***@…, expira em 15 minutos" → digita o código de 8 dígitos → **Verificar código** | login do cofre; código: ver Seção 6 |
| 2 | **E-mail do código** [02] | Outlook: de `mail@noreply.amil.com.br`, assunto "Código de verificação do login", texto "Use a senha de uso único a seguir para completar a sua transação." + código | — |
| 3 | **Página inicial** `vendas.amil.com.br` [03][04] | menu lateral → **Criar Oportunidade PME** (há também o cartão "Criar Oportunidade PME" na página) | idem |
| 4 | **Oportunidade PME** `/oportunidades-pme/cadastro?id=…` [05] | etapas Oportunidade → Cotação → Proposta → Implantada. **Haverá Coligação?** já vem em **Não**. Detalhes da Empresa: CNPJ, Nome Fantasia, Razão Social, Data de Abertura, Natureza Jurídica, Atividade Econômica | confere "Não" na coligação |
| 5 | **CNPJ** [06][07] | digita o CNPJ → "Consultando CNPJ na Receita Federal…" e o aviso "Verificando CNAE… / Natureza Jurídica… / cobertura de planos no município…" → os campos se preenchem e ficam travados | digita, espera o fim da consulta e confere que razão social, natureza e atividade apareceram |
| 6 | **Empresa MEI? e Endereço** [08] | MEI: travado em Não ("informação bloqueada conforme dados da Receita Federal"). CEP, endereço, número, complemento, bairro, município e UF **vêm preenchidos** → **Concluir Oportunidade** | confere e conclui. Grava o número OPP |
| 7 | **Oportunidade (Resumo Geral)** `/oportunidades/<id>?origem=cadastro-pme` [09] | status "Aberto-Ativo", número **OPP-5147302** no painel → **Criar Cotação** | idem |
| 8 | **Criar Cotação — Vínculo de Vendas** `/cotacoes/<id>` [10][11] | etapas Início → Selecionar Planos → Revisar Cotação. Corretora: vem "NEWPORT CONSULTORIA E CORRETORA DE…" ("Verificando corretora…"). **Nome do Corretor**: lista (código + nome), escolheu **EDLAINE ABREU SOARES**. Supervisor: "Nenhum supervisor disponível". Gestor: BRUNA RAFAELA DA SILVA. O painel já mostra o **número da cotação COT-5185118** e "Expira em: 17/10/2026" → **Continuar** | escolhe o corretor da engrenagem. Grava o número COT |
| 9 | **Selecionar Planos** [12][13][14] | **Plano**: lista longa (ver Seção 4) → **PLATINUM R1 COPART**. Aparece o selo "50% OFF 1ª e 2ª parcela" e o botão "+ Incluir Aditivo" | escolhe o plano pedido pelo texto exato |
| 10 | **Vidas por faixa** [15] | botão + (ou digita) até 18 = 1, 34–38 = 2, 59 ou mais = 1 → "Total de Vidas: 4", "Valor Total: R$ 4.769,00" | preenche as 10 faixas; confere o total de vidas; lê o valor por vida **depois** de preencher tudo |
| 11 | **Aditivo e Dental** [16] | Aditivo **AMIL RESGATE SAÚDE I**, vidas 4 ("Promocional por 12 meses", R$ 0,00), sem clique visível. Planos Dentais: **Aderir ✓ DENTAL BRONZE PJ PROMO** (ligado ao plano médico, 4 vidas, 12 meses de desconto, R$ 14,50 por vida depois). "+ Incluir Plano Médico" não foi usado → **Continuar** | confere que o estado final é igual ao vídeo: aditivo presente e dental marcado |
| 12 | **Revisar Cotação** [17][18] | Resumo Geral: oportunidade, data de criação, **data de validade**, porte **PME I**, tabela **Compulsória**, corretora, corretor, gestor, coligada Não. Tabelas: plano médico (vidas, "Desconto 50% 1ª e 2ª parcela", valor por mês a partir da 3ª), dental, aditivos, **Total Geral**, **Total Geral após 12 Meses** | lê e confere. **O ensaio para aqui** |
| 13 | **Concluir Cotação** [19][20][21] | **Concluir Cotação** → status "Concluída" → "PDF da Cotação PME: cotacao-COT-5185118.pdf — Gerando PDF…" → avisos "PDF Gerado" e "Cotação concluída com sucesso! Agora você pode criar uma proposta." | ⚠ ponto sem volta: gravar "concluindo" antes do clique |
| 14 | **Baixar PDF** [22] | **Baixar PDF**. O Chrome abriu o arquivo no Acrobat e ele usou "Salvar como" na pasta COTAÇÕES do cliente [31]. **"Criar Proposta" nunca é clicado** | captura o download e confere o PDF |
| 15 | **Próximo plano** [23][24] | link do número OPP no painel → Oportunidade → "Cotações da Oportunidade (1)": COT-5185118, R$ 4.769,00, 4 vidas, Concluída → **Criar Cotação** → nova COT-5185125 → Vínculo (EDLAINE de novo) → … | repete os passos 8 a 14 para cada plano |
| 16 | **2º plano** [25][26][27] | **AMIL BLACK I R1 COPART** → mesmas vidas → Revisar → Concluir → Baixar PDF | idem |
| 17 | **3º plano** [28][29][30] | **AMIL S2500 R1 QP COPART** (nova COT-5185136) → idem | idem |

## 3. Valores do vídeo (para o simulador e para conferir)

Valor por vida com **4 vidas** (até 18 / 19–23 / 24–28 / 29–33 / 34–38 / 39–43 / 44–48 / 49–53 / 54–58 / 59+):

| Plano | Valores por vida | Total mensal | Total Geral (1ª e 2ª) | Após 12 meses (+ dental R$ 58,00) |
| - | - | - | - | - |
| PLATINUM R1 COPART | 452,13 / 528,99 / 645,38 / 774,45 / 813,18 / 894,50 / 1.118,13 / 1.229,94 / 1.537,43 / 2.690,51 | **4.769,00** | **2.384,50** (50%) | **4.827,00** |
| AMIL BLACK I R1 COPART | 801,42 / 937,66 / 1.143,95 / 1.372,74 / 1.441,37 / 1.585,51 / 1.981,90 / 2.180,08 / 2.725,11 / 4.768,94 | **8.453,10** | **4.226,55** (50%) | **8.511,10** |
| AMIL S2500 R1 QP COPART | 838,76 / 981,35 / 1.197,25 / 1.436,71 / 1.508,54 / 1.659,40 / 2.074,25 / 2.281,68 / 2.852,10 / 4.991,18 | **8.847,02** | **8.847,02** (sem desconto) | **8.905,02** |

Conferências:
- soma de (valor por vida × vidas) = Valor Total;
- com o selo de 50%, Total Geral = metade do total;
- após 12 meses = total + dental (R$ 14,50 × vidas).

Os valores por vida **dependem do total de vidas**. Só leia depois de preencher todas as faixas.

## 4. Planos na lista (parcial, como aparecem)

BRONZE SP COPART (TP) · BRONZE SP MAIS QC/QP COPART (TP) · PRATA QC/QP COPART (TP) · PRATA II QC/QP COPART (TP) ·
OURO QC/QP R COPART (TP) · OURO II QP R COPART (TP) · PLATINUM R1/R2 COPART (TP) · AMIL BLACK I R1/R2/R3 COPART (TP) ·
AMIL BLACK II R1/R2/R3 COPART (TP) · AMIL S380 QC/QP NAC R COPART PJ / … TP PJ_PME · AMIL S450 QC/QP NAC R COPART PJ / … TP PJ_PME ·
AMIL S750 R1/R2/R3 QP NAC COPART PJ / … TP PJ_PME · AMIL S2500 R1/R2 QP COPART (TP) · AMIL S6500 BLACK R1/R2/R3 QP COPART (TP) ·
PLANO REFERÊNCIA PJCE.

O robô escolhe pelo **texto exato**. Se o texto não estiver na lista, o robô para e mostra os nomes que viu. O pedido de estudo
do e-mail fala em "Platinum R1" e "Amil One S2500 R1"; o corretor também cotou o "Black I R1".

## 5. Regras propostas para o robô

1. **1 pedido (empresa) = 1 oportunidade (OPP)**, e **cada plano = 1 cotação (COT)** dentro dela. Grave o OPP logo depois de "Concluir Oportunidade" e o COT logo que ele aparecer no Vínculo.
2. **Anti-reemissão:**
   - oportunidade: CNPJ;
   - cotação: OPP + plano + vidas.

   Grave "concluindo" antes de **Concluir Cotação**. Se cair depois do clique, **não crie outra cotação**: abra a COT pela lista "Cotações da Oportunidade" e baixe o PDF. Se não conseguir, deixe em "Conferir no portal".
3. **Retomada:**
   - se a OPP já existe, reabra-a (link do número OPP ou Andamentos) e crie só as cotações que faltam;
   - se uma COT ficou "Em Digitação", continue de onde parou ou crie outra (calibrar).
4. **Ensaio:** vai até **Revisar Cotação**, lê os valores e para **sem "Concluir Cotação"**.

   Atenção: na Amil o ensaio **já cria a oportunidade** e uma cotação "Em Digitação", que expira em 1 dia. Não há como ver o preço sem isso.
5. **Nunca clicar** em **"Criar Proposta"**, "Enviar por E-mail", "+ Incluir Plano Médico" (salvo pedido), nem em nada das etapas Proposta e Implantada.
6. **PDF:** pelo botão "Baixar PDF" (evento de download).
   - Confira que é um PDF válido e que contém o número COT e o nome do plano.
   - Arquivo morto: `AMIL_<cnpj>_<COT>.pdf`.
   - Pasta do cliente: ver Seção 7.
7. **Coisas na frente dos cliques:** avisos (toasts) no canto superior direito e o "Carregando…" entre telas.

## 6. Login com código por e-mail (decisão pendente)

O vídeo mostra que **todo login pede um código de 8 dígitos enviado ao e-mail do usuário**, e que isso acontece várias vezes ao dia. Há dois caminhos:

- **A. Código na nossa tela (já existe na SulAmérica):** o robô faz o login, o portal manda o código e a nossa tela mostra "Digite o código que chegou no seu e-mail". O corretor copia do Outlook e digita na nossa tela. Funciona já, mas exige que o corretor abra o e-mail.
- **B. O robô lê o código sozinho:** acesso de leitura à caixa do Microsoft 365 do usuário (Microsoft Graph). O robô lê só e-mails de `mail@noreply.amil.com.br` com assunto "Código de verificação do login" recebidos depois do clique, e o token fica no cofre do Windows. Depende de a TI da Newport autorizar o aplicativo no Microsoft 365.

Recomendação: construir **A** agora. Também guardar a sessão no perfil do navegador, para pedir código o menos possível, e medir quanto tempo a sessão dura. **B** só com autorização da Newport.

## 7. Engrenagem do robô Amil (padrão = o que o vídeo mostra)

| Tela | Campo | Padrão |
| - | - | - |
| Login | usuário e senha (cofre `NewportCotacoes/amil`). Campos exatos: calibrar na 1ª etapa | — |
| Login | código por e-mail | pedir na nossa tela (Seção 6) |
| Oportunidade | Haverá coligação? | Não |
| Vínculo | Nome do corretor (texto como aparece na lista) | EDLAINE ABREU SOARES (como no vídeo) |
| Vínculo | Supervisor | nenhum |
| Planos | planos que já vêm marcados | nenhum (escolhidos na Nova cotação, texto exato da lista) |
| Dental | aderir ao DENTAL BRONZE PJ PROMO | Sim (como no vídeo) |
| Aditivo | AMIL RESGATE SAÚDE I | manter (como no vídeo) |
| PDF | nome na pasta do cliente | `AMIL {apelido do plano} {nome curto da empresa}.pdf`, como o corretor ("AMIL PLATINUM CALANDRINI", "AMIL BLACK CALANDRINI", "AMIL S2500 CALANDRINI"). Apelido por plano na engrenagem (PLATINUM R1 COPART → PLATINUM; AMIL BLACK I R1 COPART → BLACK; AMIL S2500 R1 QP COPART → S2500). O nome curto da empresa vem do campo "nome para achar depois" da Nova cotação; vazio = sem nome |

## 8. Regra geral

Onde houver escolha, o robô faz **exatamente o que o corretor faz no vídeo**.

Pontos que o vídeo não mostra e que são calibrados no primeiro ensaio:
- a 1ª etapa do login;
- se o aditivo e o dental vêm marcados pelo portal ou foram clicados (o robô confere o estado final: aditivo presente e dental "Aderir" marcado);
- o que o portal faz se já existir uma oportunidade para o mesmo CNPJ.
