# Bradesco — Cotação SPG (Saúde PME): mapa do vídeo do corretor

Fonte: `BRADESCO.mp4` (2 min 49 s, gravado em 16/10/2026, sem áudio) e os quadros em
`bradesco_quadros/` (o número de cada quadro aparece entre colchetes nas tabelas abaixo).
O cenário é o mesmo do vídeo da SulAmérica: a mesma empresa, com 3 vidas (1 na faixa 00–18,
"Menor de 1 ano", e 2 na faixa 34–38).

> O vídeo e os quadros mostram CPF, e-mails e celular do corretor e o CNPJ do cliente.
> Ficam fora do git, como `saida\`.

## 1. O que muda em relação à SulAmérica

| Assunto | SulAmérica | Bradesco |
| - | - | - |
| Login | CPF + e-mail + senha numa tela | 2 etapas: **CPF/CNPJ → Continuar → senha** (`login.bradescoseguros.com.br/nidp/...`). No vídeo o campo recebeu o **CNPJ da corretora (Newport)** e a etapa da senha passou sozinha (sessão ou senha salva no Chrome dele). A senha não aparece: calibrar |
| Onde fica o cotador | módulo "Cotação PME" | Portal de Negócios → **SAÚDE → Painel Saúde → COTAÇÕES → Cotação SPG** |
| Telas | cotador novo, uma rota por tela | começa num **cotador novo** (passo a passo) e termina em **páginas antigas** (`EEEM-EmissaoExpressa`), com rolagem própria, provavelmente dentro de iframe |
| O que gera o número oficial | "Continuar" no resumo → protocolo **por plano** | **"Gerar processo"** cria **um Número do Processo por empresa** (válido 40 dias). Cada plano ou versão é um **cálculo** dentro do mesmo processo, feito por **"Alterar Cotação" → Calcular** |
| Segundo plano | Copiar cotação | **Alterar Cotação** (formulário antigo) → troca plano, acomodação ou coparticipação → Calcular. **O processo é o mesmo** |
| PDF | botão de download | **"Imprimir"** abre uma **janela pop-up (`about:blank`)** com o cálculo; o corretor imprime como PDF (Salvar como PDF) |
| Coparticipação | filtro com/sem | cotador novo: **Sim / Não** na aba do grupo. Alterar Cotação: **lista com percentual** (o vídeo usa **30%**) |
| Dental | Cuidado 360° | o Resultado já vem com **Padrão Doc 1 marcado**; no vídeo o corretor **troca para "Sem plano dental"** antes de "Iniciar cotação". Com isso, a página do cálculo mostra Saúde \| Saúde Conjugado \| Dental Conjugado e os blocos "Totais Saúde" e "Totais Conjugado" (o conjugado aparece só como comparação). Com um dental marcado, o portal mostra outro layout (linha "Plano Dental", colunas Saúde \| Dental, um bloco "Totais") |
| Idades exatas | faixas pedidas pelo portal | **00 a 18** e **59 ou mais** pedem a idade de cada pessoa (lista "Menor de 1 ano", 1, 2, ...) |
| Grupos | — | as vidas entram em **grupos por categoria funcional** (o vídeo usa 1 grupo, "Sócios e Diretores") |
| IOF | 2,38% | **2,38%** também (5.671,64 → 134,99; 2.448,93 → 58,28) |
| Validade | 45 dias (no exemplo) | **40 dias** a partir da data do processo (texto do portal) |

## 2. Fluxo tela a tela

| # | Tela (endereço) | O que o corretor fez no vídeo | O que o robô faz |
| - | - | - | - |
| 1 | **Portal de Negócios — login** `bradescoseguros.com.br/pnegocios2/wps/portal/portaldenegociosnovo/...` [01] | campo **CPF/CNPJ** → Continuar | preenche com o login guardado no cofre |
| 2 | **Senha** `login.bradescoseguros.com.br/nidp/app/login?id=secure_name_pasword_form_pneg...` | passou sozinho (não aparece) | senha do cofre; calibrar no primeiro ensaio; se aparecer código, a nossa tela pede, como na SulAmérica |
| 3 | **Área logada** `.../myportal/portalnegocios/arealogada/home` [02] | menu **SAÚDE** | topo mostra "NEWPORT CONSULTORIA E CORRETORA DE" |
| 4 | **Painel Saúde** `.../arealogada/saude/...` [03] | submenu **COTAÇÕES → Cotação SPG** (há também o atalho "Cotação SPG" em Acesso rápido) | idem |
| 5 | **Cotador de planos SPG** `.../arealogada/saude/cotacoes/cotacao-spg` [04] | "Selecione um produto": **Saúde e conjugado** (outra opção: Dental). Também há "Abrir simulações salvas" e "Acompanhar processos" | Saúde e conjugado |
| 6 | **"Qual o CNPJ ou CAEPF da empresa contratante?"** [05] | CNPJ → **Consultar** → aparece a razão social → **Avançar** | digita, consulta, confere a razão social e avança |
| 7 | **"Indique os grupos que vão aderir ao seguro"** [06][07] | Grupo 1, categoria **Sócios e Diretores** (opções: Funcionários, Estagiários, Administradores, Sócios Diretores e Funcionários). Quantidades por faixa: 00 a 18, 19 a 23, 24 a 28, 29 a 33, 34 a 38, 39 a 43, 44 a 48, 49 a 53, 54 a 58, 59 ou mais. Em **00 a 18** abre "Indique as pessoas entre 00 a 18 anos": **Idade** (Menor de 1 ano) + **Quantidade** 1. 34 a 38 = 2. "Pessoas no total 3" → Avançar ("Consultando") | preenche grupo, faixas e idades; confere "Pessoas no total" |
| 8 | **Informações / Região** [08] | UF e Cidade vêm preenchidas e travadas pelo CNPJ; painel "Região Indicada: São Paulo" → **Avançar** | confere e avança |
| 9 | **"Você pode personalizar ainda mais..."** [09] | operadora atual, plano atual, hospital, valor desejado → **Pular** | Pular |
| 10 | **Configurações de Planos e Condições Comerciais — aba Contrato** [10][11] | Modalidade de Adesão **Compulsória** (ou Opcional) · Cobertura **Top** (ou Hospitalar) · Modalidade de Pagamento **Faixa Etária** (Custo Médio parecia desabilitado) · Possui mais de 1 titular? **Não** · Desconto Folha de Pagamento Bradesco: **não aplicado** · Desconto de comissionamento (2,5/5/7,5/10%): **nenhum** · Número da Sucursal **978 - SANTANA MERCADO** (havia também 969 - LAPA MERCADO) · Código do Corretor **438451 - NEWPORT...** · Agência Produtora vazia | tudo vem da engrenagem |
| 11 | **aba Grupo 1** [12] | Acomodação **Quarto** (ou Enfermaria) · Coparticipação **Sim** (ou Não) · Região tarifária São Paulo (travada) · quantidades só leitura → **Calcular** | acomodação e coparticipação da versão da vez |
| 12 | **Resultado** [13][14][15] | resumo (Adesão, Cobertura, Modalidade de pagamento, **Reembolso: Específico**, total de pessoas). "Grupo 1 – Saúde": **carrossel de cards** (com setas) — no vídeo, três "Nacional Plus": **R$ 8.062,95** (reembolso 8x tabela), **R$ 6.993,61** (6x), **R$ 5.671,64** (4x). Cada card tem Benefícios, Detalhes do plano e Valores por faixa etária. O corretor marcou o de **R$ 5.671,64**. "Grupo 1 – Dental": Sem plano dental · Premium Top 1 R$ 270,87 · Padrão Doc White R$ 83,70 · Padrão Doc 1 R$ 66,39. **O Padrão Doc 1 já vem marcado pelo portal; aos 69 s o corretor clica em "Sem plano dental"** ("Atenção: ao selecionar esta opção, você também irá retirar o plano dental dos demais grupos"). Aviso: valores indicativos, processo válido 40 dias → **Iniciar cotação** | escolhe o plano pedido no carrossel e clica em **"Sem plano dental"** (confere que ficou marcado); **o ensaio para aqui** (preços já aparecem e nada oficial foi gerado) |
| 13 | **Dados complementares — aba Corretora** [16][17] | sucursal e código já vêm. **E-mail da corretora (assinatura da proposta)** (obrigatório), celular (opcional), posto de atendimento (opcional). **Comissionamento:** Angariação = **"3 Primeiras Parcelas 100%"** (opções: Não Há; 1ª Parcela 100%, 2ª Parcela 50%; 2 Primeiras Parcelas 100%, 3ª Parcela 50%; 1ª Parcela 100%, 2ª Parcela 80%; 1ª Parcela 100%; 1ª Parcela 20%; 3 Primeiras Parcelas 100%) · Corretagem (carrega depois da angariação) = **"2% vitalício a partir da 4ª parcela"** | engrenagem |
| 14 | **aba Intermediário** [18] | papel **Corretor** (ou Produtor, Angariador) · **CPF** do corretor (o portal completa o nome) · e-mail e celular opcionais | engrenagem; o CPF fica no cofre |
| 15 | **aba Transferência Bradesco** [19] | **Não** (Sim pediria CPFs ou cartões Bradesco dos proponentes) | engrenagem (padrão Não) |
| 16 | **aba Processo** [20] | Ramo de atividade: digitou "OUTR" → **OUTROS** · Natureza jurídica veio preenchida (Sociedade Empresarial Limitada) → **Gerar processo** | ⚠ **ponto sem volta**: cria o Número do Processo. Registrar "gerando processo" antes do clique |
| 17 | **Cálculo de Seguro SPG** (página antiga) [21][22] | modal "valores meramente indicativos... válido por 40 dias" → **OK**. Mostra: **Número do Processo** (ex.: 8 dígitos). No campo **"Identifique o cálculo a ser armazenado \*"** o corretor digita **"COM COPAY"** (o Chrome sugere o histórico dele: COM COPAY, SEM COPAY, COMPULSORIO, OPCIONAL, TOP NACIONAL, NAC. FLEX); **esse texto sai no cabeçalho do PDF**. tabela do Perfil 1 (Plano, **Código do Plano** "TPN4 COPART", Região "São Paulo Capital", Coparticipação 30%, Reembolso), valores por faixa (Saúde, Saúde Conjugado, Dental Conjugado), **Totais Saúde** e **Totais Conjugado**. Botões: **Alterar Cotação · Imprimir · Finalizar Cálculo** | lê e confere tudo |
| 18 | **Imprimir** [23] | abre a pop-up `about:blank` com o cálculo (logo "bradesco saúde", o texto do campo "Identifique o cálculo", data) → Imprimir → **Salvar como PDF**. Nomes que ele deu: 1º = **"BRADESCO TNP4.pdf"** (Nacional Plus 4x); 2º = **"BRADESCO TOP NACIONAL.pdf"** (Nacional III), substituindo um arquivo antigo de mesmo nome | captura a pop-up e gera o PDF |
| 19 | **Alterar Cotação** (formulário antigo "Cotação SPG / Dados da Cotação") [24][25][26] | aviso "Nova modalidade de reembolso disponível". Traz tudo de novo: Tipo de Cotação, Código Sucursal, CPD Corretor, Angariação, Corretagem, Produto, CNPJ/razão social/UF, Ramo, Natureza Jurídica, **Tipo de SPG (3 a 29 / 30 a 99 / 100 a 199)**, Quantidade de Titulares, Tipo de Adesão, Categoria Funcional, Kit digital, Transferência, Desconto folha, dados da corretora e do intermediário. **Perfil 1:** Categoria (Sócios), **Plano Saúde** (lista: Efetivo Plus E, Efetivo Plus Q, Ideal 1, Nacional Flex, Nacional II, Nacional III, Nacional Plus, Premium, Saúde 1+, Saúde Efetivo IV; trocou Nacional Plus → **Nacional III**), Região, **Acomodação** (lista: Nacional Plus → Múltiplo 4/6/8; Nacional III → **Quarto Privativo**/Múltiplo 2/Múltiplo 3), **Coparticipação** (lista: **30%**), vidas por faixa → **Calcular** | troca plano, acomodação ou coparticipação da próxima versão |
| 20 | **Modais** [27] | "**Processo #N** — Cotação com Reembolso Específico." → OK; depois o modal dos 40 dias → OK | confere que o número do processo é o mesmo |
| 21 | **Segundo cálculo** [28][29] | Nacional III, "TN3P COPART" → digita "COM COPAY" em "Identifique o cálculo" → Imprimir → PDF | mesmo do passo 17–18 |

**Atenção no passo 19:** logo depois de abrir o formulário, a razão social e a UF apareceram vazias por um instante (quadro 24). Confirmar se elas carregam sozinhas ou se o robô precisa esperar.

## 3. Valores do vídeo (para o simulador e para conferir)

**Cálculo 1 — Nacional Plus (reembolso 4x), Quarto, coparticipação 30%, código TPN4 COPART**
- Por vida: 00–18 = R$ 1.155,96 · 34–38 = R$ 2.257,84 (× 2 = R$ 4.515,68)
- Prêmio Saúde **R$ 5.671,64** · Taxa Kit Digital R$ 0,00 · IOF Saúde **R$ 134,99** · Total 1ª parcela **R$ 5.806,63** · Demais parcelas R$ 5.806,63
- Coluna "Dental Conjugado" (só comparação, o dental não foi contratado): R$ 22,13 por vida → R$ 66,39 · Total Geral R$ 5.738,03 · Total 1ª parcela conjugado R$ 5.873,02

**Cálculo 2 — Nacional III, Quarto Privativo, coparticipação 30%, código TN3P COPART**
- 00–18 = R$ 499,13 · Prêmio Saúde **R$ 2.448,93** · IOF **R$ 58,28** · Total 1ª parcela **R$ 2.507,21**
- Total Geral (com dental) R$ 2.515,32 · Total 1ª parcela conjugado R$ 2.573,60

Conferências: soma (valor da faixa × vidas) = Prêmio Saúde; IOF = 2,38% do prêmio (tolerância de centavos); Total 1ª parcela = prêmio + taxa kit + IOF.

## 4. Regras propostas para o robô

1. **1 pedido (empresa) = 1 processo.** Cada plano × versão (com/sem coparticipação) = 1 cálculo dentro do processo. O primeiro cálculo sai do cotador novo; os seguintes saem de "Alterar Cotação".
2. **Anti-reemissão em dois níveis:**
   - processo: CNPJ + grupos, vidas e idades + condições do contrato;
   - cálculo: processo + plano + acomodação + coparticipação + dental.

   Grave "gerando processo" antes de clicar em **Gerar processo**. Se cair depois do clique, **não gere outro processo**: o pedido fica em "Conferir no portal" ("Acompanhar processos").
3. **Retomada:** se o processo já existe e faltam cálculos, reabra o processo (por "Acompanhar processos" ou "Abrir simulações salvas"; a calibrar) e faça só os que faltam. Se não der para reabrir, pare em "Conferir no portal".
4. **Ensaio:** vai até o **Resultado** (passo 12), lê o preço do card do plano pedido e para **antes de "Iniciar cotação"**. Nada oficial é gerado.
5. **Nunca clicar** em **"Finalizar Cálculo"** (o corretor não clica no vídeo), nem em nada que envie proposta ou inicie contratação.
6. **PDF:** a partir da pop-up do "Imprimir".
   - Arquivo morto: `BRADESCO_<cnpj>_<processo>_<plano>.pdf`.
   - Pasta do cliente: `BRADESCO <PLANO>.pdf`; a versão (COM/SEM COPARTICIPACAO) entra só quando houver as duas. O modelo é configurável.
7. **Coisas na frente dos cliques:** botão de cookies (canto inferior esquerdo), chat "BIA" (canto inferior direito), modais de OK.
8. **Quadro dentro da página:** as páginas antigas (cálculo e Alterar Cotação) parecem estar dentro de um iframe, porque têm barra de rolagem própria. Use `frame_locator`.

## 5. Engrenagem do robô Bradesco (padrão = o que o vídeo mostra)

| Tela | Campo | Padrão |
| - | - | - |
| Login | CPF/CNPJ e senha (cofre `NewportCotacoes/bradesco`) | — |
| Contrato | Modalidade de adesão / Cobertura / Modalidade de pagamento / Mais de 1 titular | Compulsória / Top / Faixa Etária / Não |
| Contrato | Desconto folha Bradesco / Desconto de comissionamento | não / nenhum |
| Corretora | Sucursal / Código do corretor | 978 / 438451 |
| Corretora | E-mail da corretora (assinatura) / Celular | do corretor |
| Comissionamento | Angariação / Corretagem | 3 Primeiras Parcelas 100% / 2% vitalício a partir da 4ª parcela |
| Intermediário | Papel / CPF (no cofre) / e-mail / celular | Corretor / do corretor |
| Grupo | Categoria funcional / Acomodação | Sócios e Diretores / Quarto |
| Grupo | Coparticipação: Com / Sem / Com e sem (e o percentual) | **Com, 30%** (como no vídeo) |
| Dental | Sem plano dental / Padrão Doc 1 / Padrão Doc White / Premium Top 1 | **Sem plano dental** (como no vídeo) |
| Processo | Ramo de atividade / Transferência Bradesco | OUTROS / Não |
| Planos | planos que já vêm marcados | nenhum (escolhe na Nova cotação) |
| PDF | modelo do nome | `BRADESCO {plano}.pdf` (versão entra só com "com e sem") |

## 6. Regra geral: fazer exatamente o que o corretor faz no vídeo

Onde houver escolha, o robô repete o vídeo. Não há decisões pendentes com o corretor.

- **Login:** CPF/CNPJ que o corretor guardar na engrenagem + senha. A etapa da senha não
  aparece no vídeo; ela é calibrada no primeiro ensaio.
- **Um processo por pedido:** "Gerar processo" uma vez por empresa, como no vídeo. Os planos
  seguintes saem de "Alterar Cotação" → Calcular, no mesmo processo.
- **"Finalizar Cálculo":** o corretor não clica, então o robô nunca clica.
- **Coparticipação:** padrão **Com (30%)**, como no vídeo. As opções "Sem" e "Com e sem" ficam na
  engrenagem. A versão "sem" usaria "Alterar Cotação" trocando a coparticipação; esse caminho não
  aparece no vídeo e só é calibrado se alguém escolher essa opção.
- **Dental:** **Sem plano dental**, como no vídeo (o portal pré-marca o Padrão Doc 1 e o corretor troca).
- **Ramo de atividade:** OUTROS. **Natureza jurídica:** a que o portal preencher.
  **Transferência Bradesco:** Não.
- **"Identifique o cálculo a ser armazenado":** digitar **"COM COPAY"** (versão com coparticipação) ou **"SEM COPAY"** (versão sem), como o corretor faz; sai no cabeçalho do PDF.
- **Caminho do plano:** no vídeo, o cotador novo só é usado para o **primeiro** plano (o que ele marca no carrossel do Resultado). Os demais planos (ex.: Nacional III) são escolhidos na lista **"Plano Saúde" do Alterar Cotação**.
- **Acomodação:** Quarto no cotador novo. No Alterar Cotação, a opção de quarto que o portal
  oferecer para o plano (no vídeo, "Quarto Privativo" para o Nacional III).
- **Nome do PDF na pasta do cliente:** o corretor usa nomes curtos próprios ("BRADESCO TNP4", "BRADESCO TOP NACIONAL"). Padrão do robô: `BRADESCO <PLANO>.pdf` (mudável na engrenagem; dá para cadastrar um apelido por plano). A versão só entra no nome quando houver "com" e "sem" do mesmo plano.
