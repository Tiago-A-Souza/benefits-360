# Newport Cotações: robô de cotação com tela do corretor — Playbook v3

Roteiro para instalar, calibrar e operar o **Newport Cotações**: uma tela no navegador onde o corretor
pede as cotações e baixa os PDFs, e um robô que faz no portal da operadora o trabalho repetitivo.
A primeira operadora é a **SulAmérica, Cotação PME (3 a 29 vidas)**: uma cotação e um PDF por plano,
como o corretor faz hoje. A estrutura já recebe outras operadoras (Seção 14).

**Escopo desta versão:** cada corretor roda o Newport Cotações no próprio computador, com o próprio
login no portal, guardado por ele uma vez na engrenagem do robô (cofre do Windows). O robô entra no
portal sozinho e trabalha com a janela do portal escondida: o corretor só usa a tela do Newport.

**O código está pronto no projeto** (`newport-cotacoes/`). Este playbook explica o que ele faz, como
instalar, como calibrar no portal real e como operar. O passo a passo técnico para o Claude Code está
em `CLAUDE.md`.

## O que mudou em relação à v2

| v2 | v3 |
| - | - |
| Só linha de comando e planilha | **Tela do corretor** no navegador: Nova cotação, andamento ao vivo, lista de cotações com o PDF a um clique, importação de planilha, ajustes e ajuda |
| Uma operadora, código num pacote só | `nucleo/` (o que serve para qualquer operadora) + `operadoras/<operadora>/` (o robô de cada portal) + uma interface comum. A tela mostra sozinha toda operadora registrada |
| PDF só na pasta do cliente e no arquivo morto | Também baixável pela tela, um a um ou vários num .zip, com o nome de sempre |
| Para parar, fechar a janela | Botão **Parar o robô**: para na próxima troca de tela, nunca no meio de uma emissão; **Continuar de onde parou** termina o resto sem repetir |
| Mesmo plano em Enfermaria e Apartamento gerava o mesmo nome de PDF (um substituía o outro) | A acomodação entra no nome quando o plano existe nas duas (`SULAMERICA DIRETO NACIONAL ENFERMARIA.pdf`) |
| Pendência (`VERIFICAR`) só pela linha de comando (`--liberar`) | Resolvida na tela: "Não saiu: liberar" ou "Saiu: já tenho o PDF" (este mantém o bloqueio de reemissão) |
| Retenção de 90 dias anotada, mas manual | Automática: PDFs, prints e logs do robô com mais de `seguranca.retencao_dias` são apagados ao abrir. A pasta do cliente nunca é tocada |
| Padrões só no `config.yaml` (vigência e coparticipação fixas no código) | **Cada corretor configura o próprio robô** pela engrenagem do cartão da SulAmérica: tudo o que o robô preenche no portal, tela por tela (produto, tipo de contratação, vigência, coparticipação, Cuidado 360°, vendedor, planos marcados, nomes dos PDFs...), gravado no computador dele, sem mexer em código |
| Produto 557 - AHO assumido em silêncio | O produto é conferido no filtro, no card e no resumo; se o portal não mostrar o produto configurado, o robô para sem cotar |
| Login manual, na janela do portal | **Login automático**: o corretor guarda CPF, e-mail e senha na engrenagem (cofre do Windows); o robô entra sozinho quando o portal pede, com a janela escondida. Código de verificação é pedido na tela |

## Sumário

0. Antes de começar: autorização, LGPD e limites
1. Visão geral da solução
2. Pré-requisitos e instalação
3. Estrutura do projeto
4. A tela do corretor
5. Planilha de entrada (para várias empresas)
6. Configuração do robô (engrenagem) e `config.yaml`
7. Calibrar no portal real
8. Como o robô percorre o cotador
9. Login automático
10. Linha de comando e saídas
11. Erros, reexecução e registro de andamento
12. Testes
13. Operação no dia a dia
14. Evolução e novas operadoras
15. Solução de problemas
16. Checklist final
17. Glossário

---

## 0. Antes de começar: autorização, LGPD e limites

**0.1 Termos de uso.** A tela de login informa que a senha é de uso exclusivo do corretor e que ele
responde pelo uso do sistema. Antes do uso real:

- Peça autorização por escrito à SulAmérica (canal de corretores ou gerente comercial), descrevendo o
  uso: robô local, operado por funcionário da Newport, que **entra no portal com o login do próprio
  corretor**, guardado no cofre do Windows do computador dele. Como a senha é de uso exclusivo do
  corretor, deixe claro que o robô a usa automaticamente e pergunte se isso é aceito.
- Pergunte se existe API ou integração oficial para corretores. Se existir, ela substitui a navegação
  e a lógica do projeto (tela, validações, saídas) é reaproveitada.
- Guarde a resposta junto do projeto. Repita para cada operadora nova.

**0.2 Dados pessoais (LGPD).** O robô lida com CNPJ e razão social de clientes, nome de vendedores e
idades de beneficiários (sem nomes).

- O login do portal (CPF, e-mail e senha) fica **só no cofre do Windows** (Gerenciador de
  Credenciais), guardado pelo próprio corretor na engrenagem do robô. Continua valendo: CPF, senha e
  token nunca entram em código, planilha, configuração, histórico da tela, registro, prints, mensagens
  de erro ou log. A tela nunca mostra a senha de volta (só "senha guardada" e o e-mail mascarado).
- O cofre é do usuário do Windows: **em máquina compartilhada, cada corretor entra com o próprio
  usuário do Windows** (nunca um usuário comum para todos).
- **Ao sair da Newport**, o corretor (ou a TI) usa "Apagar credenciais" na engrenagem do robô e apaga
  `saida\<operadora>\perfil_navegador`.
- O navegador do robô não guarda senha nem o que é digitado em formulários.
- A tela só atende o próprio computador (`127.0.0.1`) e recusa pedidos que venham de outros sites
  abertos no navegador.
- `saida\` (PDFs, prints de tela, registro, histórico da tela, sessão do navegador) fica só na máquina
  do corretor, com acesso restrito. `saida\<operadora>\perfil_navegador` guarda cookies de sessão:
  trate como senha.
- A cópia para a pasta do cliente (OneDrive/SharePoint da Newport) só acontece quando a pasta é
  informada. É o mesmo lugar onde o corretor já salva hoje.
- Retenção automática: ao abrir a tela (e a cada execução pela linha de comando) o robô apaga os
  arquivos dele com mais de 90 dias (`seguranca.retencao_dias`): PDFs de `pdfs\`, prints de `mapa\`,
  `logs\` e o registro detalhado da tela. Não apaga o registro que impede reemissão nem a pasta do cliente.

**0.3 Limites.**

- O robô **não inicia contratação**. Ele emite a cotação, baixa o PDF e para.
- Cada emissão gera um protocolo real na operadora. Por isso existe o **ensaio** (para antes de emitir).
- A simulação (antes de emitir) vale só no dia. A proposta emitida vale **45 dias** (no vídeo: emitida
  em 16/10, válida até 30/11).
- Os seletores vieram do vídeo e precisam ser confirmados no portal real (Seção 7). Mudanças visuais
  no site podem quebrar o robô; o mapa de telas existe para corrigir rápido.

## 1. Visão geral da solução

```
 tela do corretor (navegador)        robô (Python + Playwright, uma janela por operadora)       saídas
 ┌──────────────────────────┐       ┌─────────────────────────────────────────────────┐     ┌──────────────────────────┐
 │ Nova cotação:             │       │ login automático → módulo "Cotação PME"          │     │ PDF na pasta do cliente   │
 │  CNPJ, vidas por faixa,   │       │ → dados da empresa → Cuidado 360°                │     │  SULAMERICA <PLANO>.pdf   │
 │  opções, planos           │ ────► │ → congênere → vidas → [idades exatas]            │ ──► │ PDF baixável pela tela    │
 │ Importar planilha         │       │ → planos (filtros, 2 páginas, 1 plano)           │     │  (um a um ou .zip)        │
 │ Andamento ao vivo, Parar  │ ◄──── │ → comparação → resumo → EMITE → baixa o PDF      │     │ resultados.xlsx           │
 │ Cotações: Baixar PDF      │ avisos│ → COPIAR COTAÇÃO p/ o próximo plano → … → HOME   │     │ estado.json (anti-repetir)│
 └──────────────────────────┘       └─────────────────────────────────────────────────┘     └──────────────────────────┘
```

| Decisão | Motivo |
| - | - |
| Tela local no navegador (`http://127.0.0.1:8600`) | Nada para instalar além do Python; nenhum dado sai do computador |
| Um robô por vez, portal aberto (escondido) entre pedidos | O robô entra uma vez; as cotações seguintes reaproveitam a sessão |
| Login automático com o login do cofre do Windows | O corretor só usa a tela; a senha nunca vai para arquivo nem log; recusa para na 1ª vez; código de verificação pedido na tela |
| Máquina de estados pela URL | Cada tela do cotador novo tem rota própria; telas opcionais e cópia de cotação são naturais |
| Um plano por cotação + "Copiar cotação" | É o processo do corretor; gera um PDF por plano, como a pasta do estudo já organiza |
| Registro de andamento | Garante que nada é emitido duas vezes, pela tela ou pela linha de comando |
| Conferências antes de emitir | Soma das faixas = preço do card; IOF 2,38% por vida; CNPJ e plano no resumo |
| Operadora = módulo | Uma operadora nova não mexe na tela nem nas outras operadoras |
| Simulador local | Treino e testes sem gastar protocolo |

## 2. Pré-requisitos e instalação

**2.1 Máquina:** Windows 10 ou 11, internet estável, acesso ao portal da operadora com o login do corretor.

**2.2 Instalar (uma vez por computador):**

1. Python 3.11 ou mais novo em <https://www.python.org/downloads/>. Marque **"Add python.exe to PATH"**.
2. Descompacte o projeto em `C:\Newport\newport-cotacoes`.
3. Dê dois cliques em **`instalar.bat`**. Ele cria o ambiente (`.venv`), instala as bibliotecas e o
   navegador do robô (Chromium, separado do Chrome do usuário) e roda os testes rápidos. Leva alguns
   minutos na primeira vez.

**2.3 Abrir no dia a dia:** dois cliques em **`Abrir Newport Cotacoes.bat`**. Abre uma janela preta
(o servidor da tela; deixe aberta) e a tela no navegador. Para fechar, feche a janela preta.

**2.4 Treinar sem portal:** **`Treinar no simulador.bat`** abre a tela ligada ao simulador local
(aparece "Simulador local" no menu). Nada é emitido de verdade e o login de treino (falso) já vem
guardado, só na memória.

Instalação manual (PowerShell, na pasta do projeto), se preferir:

```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
python -m pytest tests/nucleo
python -m app                      # abre a tela
```

Se o PowerShell bloquear a ativação: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 3. Estrutura do projeto

```
newport-cotacoes\
├── instalar.bat, Abrir Newport Cotacoes.bat, Treinar no simulador.bat
├── CLAUDE.md                 contexto e regras para o Claude Code
├── PLAYBOOK.md               este documento
├── config.yaml               padrões, tempos, nomes de arquivo, por operadora (sem senha)
├── config_simulador.yaml     a mesma tela, apontando para o simulador local
├── main.py                   linha de comando (planilha, ensaio, pendências)
├── app\                      a tela: servidor local, fila do robô, histórico e páginas (web\)
├── nucleo\                   serve para qualquer operadora: modelo, registro anti-reemissão,
│                             saídas, navegador, configuração, retenção
├── operadoras\
│   ├── base.py               a interface que toda operadora implementa
│   └── sulamerica\           o robô da SulAmérica: fluxo, etapas, seletores, extração,
│                             planilha, login e o simulador\ do portal
├── tests\                    testes automáticos (núcleo, robô x simulador, tela x simulador)
├── codegen\mapa_seletores.md anotações da calibragem
└── saida\                    criada ao usar (NÃO compartilhar)
    ├── tela.db               histórico da tela (pedidos, cotações, registro detalhado)
    ├── config_tela.json      ajustes feitos pela tela
    └── sulamerica\
        ├── resultados.xlsx   histórico: uma linha por plano
        ├── estado.json       registro de andamento (impede reemissão)
        ├── pdfs\             propostas baixadas (arquivo morto)
        ├── mapa\             prints/HTML/árvore das telas (calibragem e erros)
        ├── logs\             um log por execução
        └── perfil_navegador\ sessão do navegador (cookies)
```

## 4. A tela do corretor

**Menu:** Início, Nova cotação, Cotações, Importar planilha, Robôs, Ajuda. No pé do menu fica o
cartão de cada operadora com a situação (Desconectado, Entrando no portal, Esperando o código,
Conectado, Robô trabalhando), a **engrenagem** que abre a configuração do robô (Seção 6) e o botão
**Cadastrar o login** (enquanto não houver login guardado), **Atualizar a senha** (se o portal recusou)
ou **Testar login** (o robô entra no portal e para na tela de módulos, sem cotar). O corretor nunca vê
nem mexe na janela do portal.

**Nova cotação** (uma empresa):

1. **Empresa:** CNPJ (conferido na hora), um nome para achar depois (opcional) e a pasta COTAÇÕES do
   cliente (opcional, com o botão "Escolher pasta"). CNPJ já cotado oferece "Usar os mesmos dados da
   última cotação".
2. **Vidas por faixa etária:** as 10 faixas da ANS como colunas; clique na coluna ou use + e −. O
   total aparece embaixo, com o limite da operadora (3 a 29). Nas faixas em que o portal pede idade
   exata (marcadas com *), aparece o campo das idades.
3. **Operadora:** o que é da empresa (plano atual e operadora atual) e uma frase com o que o robô vai
   preencher no portal, tirada da configuração do robô (ex.: "Compulsória, 24 meses, com e sem
   coparticipação (2 cotações por plano), com Cuidado 360°, produto 557 - AHO"). **Mudar só nesta
   cotação** abre essas opções para uma cotação diferente, sem mexer na configuração (a coparticipação
   tem três botões: Sem coparticipação, Com coparticipação, Com e sem); a engrenagem leva à configuração.
   Por fim, os **planos**: já vêm marcados como o robô foi configurado; escolha na lista (agrupada por
   acomodação; cada plano vira uma cotação e um PDF, ou duas com "Com e sem") ou "Os mais baratos"
   (N planos). A lista cresce sozinha com os planos que o robô encontra no portal. O rodapé conta as
   cotações de verdade: 1 plano com "Com e sem" = "Gerar 2 cotações".
4. **Ensaiar sem emitir** percorre as telas com o primeiro plano e para antes de emitir.
   **Gerar N cotações** pede confirmação e emite.

**Andamento:** mostra a tela do portal em que o robô está (etapas numeradas), qual plano está cotando
("plano 1 de 2"), a faixa dourada quando o portal pede um código de verificação (digite o código que
chegou no seu celular/e-mail; o robô digita no portal) ou quando o login não deu certo (com o link para a
engrenagem), e cada cotação assim que fica pronta, com
**Baixar PDF**, **Abrir pasta** e "ver por faixa" (valor mensal por vida em cada faixa, total sem IOF e
IOF). Com mais de um PDF, **Baixar os N PDFs (.zip)**. No fim:

| Resultado | Botões |
| - | - |
| Ensaio concluído | **Gerar as cotações** (emite o mesmo pedido) e Ensaiar de novo |
| Pronto: N cotações emitidas | Abrir a pasta do cliente |
| Cotações ficaram sem emitir | **Tentar de novo as que faltaram** (o que saiu não sai de novo) |
| Parado (você clicou em Parar) | **Continuar de onde parou** |
| O robô parou (erro) | Tentar de novo |

**Parar o robô:** o robô para na próxima troca de tela. Se uma cotação já estiver sendo emitida, ela
termina antes, com o PDF. As que não começaram ficam como "Parada", e "Continuar de onde parou" emite
só essas.

**Com e sem coparticipação (padrão da Newport):** para cada plano a Newport sempre pega a cotação com e
a sem coparticipação. O portal não faz as duas numa cotação só, então o robô faz duas, cada uma com o
seu protocolo e o seu PDF, nesta ordem: plano 1 com, plano 1 sem, plano 2 com, plano 2 sem. No
Andamento e em Cotações as duas versões do mesmo plano aparecem juntas (plano, "com coparticipação" /
"sem coparticipação", total com IOF, protocolo, Baixar PDF), e o .zip leva as duas. Parar, "Continuar
de onde parou" e "Tentar de novo as que faltaram" valem por versão: se a "com" saiu e a "sem" falhou, só
a "sem" é refeita.

**Cartão da SulAmérica** (menu à esquerda): mostra a conexão (Desconectado, Entrando no portal,
Conectado, Robô trabalhando, Saindo do portal) e o botão da vez: Cadastrar o login, Testar login ou
**Sair do portal agora** (só com o robô parado; libera o CPF na hora).

**Cotações:** a lista de tudo o que o robô fez, com busca por empresa, CNPJ, plano ou protocolo e os
filtros Emitidas (padrão), Não emitidas, Ensaios e Tudo. Marque várias e baixe num .zip (com mais de
uma empresa, cada uma vai numa pasta). "cotar de novo" abre a Nova cotação com a mesma empresa, as
mesmas vidas e os mesmos planos; as opções do robô (coparticipação, vigência...) vêm da configuração de
hoje. No
topo aparecem as **pendências** que pedem conferência no portal (Seção 11).

**Situações de cada cotação:**

| Na tela | Significa |
| - | - |
| Emitida | protocolo emitido e PDF salvo |
| Ensaio ok | percorreu as telas e parou antes de emitir |
| Não emitida | falhou antes de emitir (nada foi emitido); o motivo aparece embaixo |
| Conferir no portal | algo falhou depois do clique de emitir; ver Seção 11 |
| Já emitida antes | a mesma cotação já tinha saído; o robô não emite de novo (o PDF anterior continua para baixar). Para emitir de novo de propósito, ver Seção 11 |
| Parada | você parou o robô antes desta cotação |

**Importar planilha:** arraste a planilha (Seção 5). A tela confere todas as linhas antes de começar,
mostra as prontas e as com problema (com o motivo) e oferece Ensaiar ou Gerar só as prontas.

**Robôs:** um cartão por operadora, com o resumo de como o robô cota hoje, a engrenagem
(**Configurar**) e os ajustes para todos os robôs: prints das telas e **Mostrar a janela do portal (para
calibrar)**, ambos desligados no dia a dia, e a pasta do robô. A senha nunca volta para a tela.

**Sem login guardado** (ou recusado pelo portal), Nova cotação, Importar planilha e Testar login não
abrem o portal: a faixa "Cadastre o login da SulAmérica na engrenagem do robô" leva à engrenagem.

## 5. Planilha de entrada (para várias empresas)

Baixe o modelo pela tela (Importar planilha → "Baixar a planilha modelo") ou com
`python main.py --criar-modelo`. Uma linha por empresa. A aba `como_preencher` explica cada coluna.
Formate a coluna `cnpj` como Texto.

| Coluna | Exemplo | Obrigatória | Observação |
| - | - | - | - |
| `id` | `NP-0142` | Não | Rótulo do pedido nos resultados. Não controla reemissão (ver Seção 11) |
| `cnpj` | `11.222.333/0001-81` | Sim | Com ou sem máscara; dígito verificador conferido |
| `vendedor` | (vazio) | Não | Vazio = usuário logado. Senão, nome como aparece na lista do cotador |
| `cuidado_360` | `sim` | Não | Vazio = configuração do robô (padrão da Newport: `sim`, como no vídeo) |
| `seguro_novo` | `nao` | Sim | `sim` quando a empresa não tem plano hoje |
| `congenere_atual` | `NOTREDAME` | Se `seguro_novo = nao` | Nome da lista do portal (ver "Nomes das operadoras" na configuração do robô) |
| `tipo_contratacao` | `compulsoria` | Não | `compulsoria`, `cbo` ou `flex` (vazio = configuração do robô) |
| `vigencia_meses` | `24` | Não | `12` ou `24` (vazio = configuração do robô) |
| `coparticipacao` | `as_duas` | Não | `com`, `sem` ou `as_duas` (vazio = configuração do robô; o padrão da Newport é `as_duas`). `as_duas` = duas cotações por plano, com e sem coparticipação (também aceita "com e sem" e "ambas") |
| `vidas_0_18` … `vidas_59_mais` | `1`, `0`, … `2` … | Sim | 10 colunas; total de 3 a 29 |
| `idades_0_18`, `idades_59_mais`… | `0` ou `0; 7; 12` | Quando o portal pedir | Idade exata de cada vida da faixa, separadas por `;`. No vídeo o portal pediu a 0–18 |
| `planos` | `Especial Mais \| Apartamento; Executivo R1 \| Apartamento` | Não | Cada plano vira uma cotação e um PDF. `menor_preco` (ou `menor_preco:2`) para os mais baratos. Vazio = os planos marcados na configuração do robô |
| `pasta_destino` | `C:\Users\...\COTAÇÕES` | Não | Pasta COTAÇÕES do cliente; vazio = PDF só no robô (baixável pela tela) |

**Validações antes de abrir o navegador:** colunas com os nomes do modelo (coluna com nome diferente
recusa a planilha inteira, para nada ser ignorado em silêncio); CNPJ válido; total de vidas de 3 a 29;
congênere quando não é seguro novo; idades dentro da faixa e na quantidade de vidas; planos
informados (na linha ou marcados na configuração do robô); `pasta_destino` existente; valores aceitos
em cada coluna; ids únicos. As colunas obrigatórias são só as da empresa: `cnpj`, `seguro_novo` e as
de vidas; as demais, vazias, seguem a configuração do robô.

A planilha de entrada **nunca é alterada** pelo robô.

## 6. Configuração do robô (engrenagem) e `config.yaml`

**Cada corretor configura o próprio robô, sem depender de ninguém mexer no código.** A engrenagem do
cartão da SulAmérica (no pé do menu, em Robôs ou ao lado do nome da operadora na Nova cotação) abre
**O caminho do robô no portal**: as 11 telas na ordem em que o robô passa por elas (a mesma numeração
do Andamento), com o que ele faz em cada uma e o que dá para mudar:

| # | Tela do portal | O que o corretor configura |
| - | - | - |
| 1 | Login | CPF, e-mail e senha do portal (**Guardar**, **Testar login**, **Apagar credenciais**). Vão para o cofre do Windows, nunca para a configuração. **Guardar** recusa a senha maior que o campo do portal (o robô lê o limite real a cada login: 16 até o portal dizer outro) e pergunta antes de guardar senha ou e-mail que comece ou termine com espaço (não tira sozinho). **Sair do portal depois de** (minutos sem pedidos; padrão 3) |
| 2 | Módulo PME | (nada: o robô escolhe Cotação PME 3 a 29 vidas) |
| 3 | Empresa | vendedor (vazio = quem fez o login) |
| 4 | Cuidado 360° | incluir ou não |
| 5 | Operadora atual | nomes das operadoras: como a Newport escreve → como o portal mostra |
| 6 | Vidas | (nada: informadas em cada cotação) |
| 7 | Idades | faixas em que o portal pede a idade de cada vida |
| 8 | Planos | produto Saúde PME, tipo de contratação, vigência contratual, coparticipação (**Sem coparticipação**, **Com coparticipação** ou **Com e sem**, o padrão da Newport: 2 cotações por plano) e os planos que já vêm marcados (ou os N mais baratos) |
| 9 | Comparação | (nada: o robô confere a soma das faixas e para se não bater) |
| 10 | Resumo | (nada: o robô confere tudo antes de emitir) |
| 11 | PDF | nome do PDF na pasta do cliente (com exemplo, inclusive o das duas versões), substituir ou não o antigo, nomes curtos, o que fazer depois da última cotação. Com "Com e sem", a versão entra no nome: `SULAMERICA ESPECIAL MAIS COM COPARTICIPACAO.pdf` e `... SEM COPARTICIPACAO.pdf` (no lugar de `{versao}`, se o modelo tiver; senão, logo depois do plano), e a acomodação continua entrando quando o plano existe nas duas |

Exemplo: a Newport passa a cotar com vigência de 12 meses. O corretor abre a engrenagem, clica em
**12 meses** na tela Planos e em **Salvar configuração**. Daí em diante a Nova cotação já vem com 12
meses, a planilha com a coluna vazia usa 12 e o robô marca 12 meses no filtro do portal. Para uma
cotação só, ele usa **Mudar só nesta cotação** na própria Nova cotação, e a configuração continua igual.

Na página do robô:

- cada escolha diferente do padrão da Newport mostra "Padrão da Newport: ..." e **Voltar ao padrão**;
- **Voltar aos padrões da Newport** desfaz todas as escolhas do robô;
- sair da página com mudanças não salvas pede confirmação;
- a configuração fica no computador do corretor (`saida\config_tela.json`): cada corretor tem a sua.

**Login (tela 1):** o CPF é conferido antes de guardar. Depois de guardado, a tela mostra só "Login
guardado hoje às 10:12 (e-mail ti***@***.com.br)"; os campos voltam vazios e a senha aparece como "senha
guardada". Para trocar, digite de novo CPF, e-mail e senha (senha vazia mantém a guardada). A senha da
SulAmérica tem no máximo 16 caracteres (é o limite do campo no portal): a engrenagem recusa uma maior, que
quase sempre é um espaço a mais. Se o portal
recusou a senha, o robô só tenta de novo depois que você guardar a senha outra vez. Ao sair da Newport,
**Apagar credenciais**.

**Segurança:** a tela só grava os campos que a operadora declara (nunca URL, pasta de saída,
conferências ou tempos que não estão na lista) e confere cada valor. O login do portal não é
configuração: vai direto para o cofre do Windows, por uma API que só aceita gravar e apagar. Mudar vigência, coparticipação,
contratação, Cuidado 360° ou produto gera **outra cotação** para o registro anti-reemissão, como deve
ser. O produto é conferido no filtro, no card do plano e no resumo: se o portal não mostrar o produto
configurado, o robô para sem cotar.

**`config.yaml`** guarda os **padrões da Newport** (o que vale para quem nunca mexeu na engrenagem e o
que "Voltar aos padrões da Newport" restaura) e o que só a equipe técnica muda: URLs, conferências
(IOF 2,38%, tolerância) e os demais tempos de espera. Seções: `geral`, a porta da `tela`, uma seção por
operadora em `operadoras:` e `seguranca` (`retencao_dias`; 0 desliga). `ativa: false` esconde uma
operadora da tela sem apagar a configuração.

## 7. Calibrar no portal real

Os seletores (`operadoras\sulamerica\seletores.py`) foram escritos a partir do vídeo e estão marcados
**VALIDAR**. A calibragem confirma cada um no site de verdade **sem emitir nada**.

**Antes:** o corretor guarda o login na engrenagem do robô (tela 1, Login) e liga em Robôs "Mostrar a
janela do portal (para calibrar)", para ver o que o robô faz, e "Guardar print de cada tela". O robô entra
sozinho; a sessão fica salva no perfil do navegador por um tempo. O print do login (`01_login`) é tirado
antes de o robô digitar, com os campos vazios; depois de digitar, nenhuma tela de login ou de código de
verificação vira print.

**Ciclo de calibragem (com o Claude Code aberto na pasta do projeto):**

1. Monte `cotacoes.xlsx` com **uma** empresa real, que a Newport cotaria de qualquer forma.
2. Rode `python main.py --ensaio --mapear --linha 2` (ou peça ao Claude Code: "rode o ensaio da linha 2").
   Pela tela: ligue "Guardar print de cada tela" em Robôs e use **Ensaiar sem emitir**.
3. O robô para na primeira tela em que algo não bater e salva em `saida\sulamerica\mapa\<execução>\` o
   print, o HTML e a árvore de acessibilidade daquela tela.
4. Peça ao Claude Code: "o ensaio quebrou na etapa X; leia o mapa e corrija o seletor". Ele ajusta
   `operadoras\sulamerica\seletores.py` e anota em `codegen\mapa_seletores.md`.
5. Repita até o ensaio terminar com `ENSAIO_OK` e os valores baterem com a tela do portal.
6. Primeira emissão real com **um** plano; depois com **dois** (testa "Copiar cotação"); depois peça
   de novo a mesma cotação para confirmar que nada é reemitido (Seção 12).

O `playwright codegen` continua útil para investigar uma tela específica
(`playwright codegen https://os11.sulamerica.com.br/SaudeCotador/LoginGeral.aspx`). Ele grava o que é
digitado: **não digite a senha com ele aberto**, ou apague a linha gravada.

## 8. Como o robô percorre o cotador

O robô olha a URL, descobre em que tela está e executa a etapa correspondente. Cada etapa espera a
tela carregar, confere o que já está preenchido e só preenche o que falta. Entre uma tela e outra ele
avisa a tela do corretor (é o que aparece no Andamento) e verifica se o corretor pediu para parar.

| Tela (URL) | O robô faz | Confere antes de seguir |
| - | - | - |
| Login (`os11.../LoginGeral.aspx`) | aceita cookies; preenche CPF, e-mail e senha do cofre; marca "Ok, entendi!"; ENTRAR (código de verificação: pede na tela) | tela "Selecione um módulo" |
| Módulos (mesma URL) | clica em "Cotação PME"; segue se abrir em aba nova | cotador novo abriu |
| Dados da empresa (`/dados-empresa`) | troca o vendedor se pedido; digita o CNPJ tecla a tecla | "CNPJ válido" e razão social |
| Cuidado 360° (`/cuidado-cross`) | marca Sim/Não; no modal "Confirmação", Prosseguir | saiu da tela |
| Congênere (`/congeneres`) | escolhe a operadora na lista (vira etiqueta) ou marca "seguro novo" | etiqueta visível |
| Vidas (`/vidas-saude`) | preenche as 10 faixas | "N vidas distribuídas" = total pedido |
| Idades (`/distribuicao-agravadas`, quando aparece) | informa a idade de cada vida pedida | todas as faixas "Completo" |
| Planos (`/precificacao-planos`) | acerta filtros (marca e desmarca); lê as 2 páginas; "Desmarcar todos"; marca o plano. Na 2ª versão de "Com e sem" (cópia), troca só a coparticipação no filtro e lê a lista de novo; se a cópia não deixar trocar, sai da cotação e refaz essa versão do começo | card mostra contratação, vigência e a coparticipação desta versão |
| Comparação (`/comparacao-planos`) | lê o valor por vida de cada faixa | quantidades = pedido; soma = preço do card; um plano só |
| Resumo (`/resumo-final`) | lê total sem IOF, IOF e total; registra "emitindo" logo antes do clique; Continuar | IOF 2,38% por vida; total; CNPJ; plano exato; vidas, contratação, vigência, coparticipação e operadora anterior em "Características da Cotação". Se a cotação já estiver no registro, não emite |
| Emitida (`os11.../Simulador.aspx`) | lê o protocolo; baixa o PDF; copia para a pasta do cliente | PDF válido com o protocolo |
| Próxima cotação (outro plano ou a versão sem coparticipação) | como no vídeo: COPIAR COTAÇÃO → SIM → "Comece por aqui" já preenchido; passa por todas as telas conferindo o que já está preenchido e mudando só o que é diferente (na tela Planos, o filtro de coparticipação). Não sai do portal nem fecha nada. Se a cópia não deixar trocar a coparticipação: Sair da cotação e NOVA COTAÇÃO, na mesma aba, sem login | CNPJ da cópia = CNPJ do pedido |
| Fim do pedido | "Voltar para a Home" (sem o botão, "Nova cotação") | painel "Estou em cotações" (`PainelCotacao.aspx`) ou assistente novo |
| Painel "Estou em cotações" | próximo pedido: NOVA COTAÇÃO (ou SELECIONAR OUTRO MÓDULO → Cotação PME) | cotador aberto |

No ensaio, o robô para no resumo (não clica em Continuar), registra `ENSAIO_OK` e sai da cotação.
**Parar** só é atendido entre telas e nunca entre o clique de emitir e a leitura do protocolo.

## 9. Login automático

**Uma vez por computador (e quando a senha mudar):** na engrenagem do robô, tela 1 (Login), o corretor
digita CPF, e-mail e senha do portal e clica em **Guardar**; depois, **Testar login**. O login fica no
cofre do Windows (Gerenciador de Credenciais), no usuário do Windows dele.

**Uma sessão por CPF:** o portal não aceita o mesmo CPF logado em dois lugares. Enquanto o robô estiver
no portal, não entre com o mesmo CPF pelo navegador comum (nem em outro computador), e vice-versa.

**No dia a dia:** o robô entra no portal sozinho, com a janela escondida, **só quando o portal pede**
(no primeiro pedido, ou se a sessão expirar no meio de um pedido; aí ele entra de novo e continua de onde
estava, sem reemitir nada). O corretor não mexe na janela do portal.

**Sair do portal (libera o CPF):** o robô sai do portal ("Sair do Cotador", no menu do portal) e fecha a
janela, para o corretor poder usar o portal no navegador dele:

- quando a fila esvazia, depois de uma folga sem pedidos: **3 minutos** (padrão da Newport), configurável
  na engrenagem, tela 1 (Login), "Sair do portal depois de". 0 = não sai sozinho;
- quando o corretor clica em **Parar** e não sobra nada na fila;
- quando a tela fecha (a janela preta): o Windows dá uns 5 segundos; se não der tempo, a sessão expira
  sozinha no portal;
- no botão **"Sair do portal agora"** do cartão da SulAmérica (só com o robô parado).

Nunca no meio de uma cotação, nem entre o clique de emitir e o PDF. Na próxima cotação o robô entra
sozinho de novo. O log diz "Saí do portal (fila vazia há 3 min)" (ou o motivo).

| O portal... | O robô | O corretor |
| - | - | - |
| aceita o login | segue para a cotação | nada |
| pede código de verificação | espera (até 5 min) | digita na faixa dourada da tela o código que chegou no celular/e-mail |
| recusa a senha | **para na primeira vez** e marca o login como recusado; não tenta de novo (evita bloquear a conta) | confere a senha entrando no portal pelo navegador comum e guarda de novo na engrenagem |
| diz "Já existe um acesso ativo para esse CPF" no começo do trabalho | **espera e entra de novo sozinho** (a cada 1 min, por até 10 min; a tela mostra "Esperando o portal liberar"); **não** marca o login como recusado | nada; se passar de 10 min, sair do portal no navegador comum (ou no outro computador) e pedir de novo |
| diz "acesso ativo" **no meio de um pedido** (a sessão caiu e alguém entrou com o CPF) | **para na hora**, avisa na tela e não insiste; não marca recusado; o que já saiu continua registrado | sair do portal no outro lugar e pedir de novo (o robô só faz o que faltou) |
| mostra captcha | para e avisa; nunca tenta resolver | entra uma vez pelo navegador comum e tenta de novo |
| pede troca de senha | para e avisa | troca no portal pelo navegador comum e guarda a nova na engrenagem |
| (não há login guardado) | nem abre o portal | "Cadastre o login da SulAmérica na engrenagem do robô" |

Regras (continuam valendo): CPF, senha e token nunca vão para `.py`, `.yaml`, `.xlsx`, histórico da
tela, registro, prints ou log; em máquina compartilhada, cada corretor usa o próprio usuário do Windows;
ao sair da Newport, **Apagar credenciais** na engrenagem e apagar `perfil_navegador`; não compartilhe
`perfil_navegador`; no fim do dia, se quiser, faça logout no cotador pelo navegador comum.

## 10. Linha de comando e saídas

A tela é o caminho do dia a dia. A linha de comando continua para calibragem, lotes e suporte:

```
python -m app                            abre a tela (o mesmo que o .bat)
python main.py --validar                 confere a planilha
python main.py --ensaio                  percorre tudo sem emitir
python main.py                           emite (pede para digitar EMITIR)
python main.py --linha 5                 só a linha 5   |   --id NP-0142  só esse pedido
python main.py --pendencias              itens que pedem conferência
python main.py --registro                todas as cotações registradas, com a chave
```

Tela e linha de comando não rodam ao mesmo tempo na mesma pasta de saída: o segundo avisa que já
existe um robô rodando.

**Saídas (em `saida\sulamerica\`):**

- `resultados.xlsx`
  - aba `cotacoes`: uma linha por plano, com status, protocolo, preço, total sem IOF, IOF, total,
    **valor por vida de cada faixa**, PDF e erro;
  - aba `precos_planos`: preço de todos os planos listados para cada empresa;
  - aba `erros_planilha`.
- `pdfs\SULAMERICA_<cnpj>_<protocolo>.pdf` — arquivo morto, nome único (é o que a tela entrega, com o nome de corretor).
- `<pasta do cliente>\SULAMERICA <PLANO>.pdf` — cópia para o estudo, com o nome que o corretor usa.
- `mapa\` — telas registradas (com mapear ligado, e sempre que há erro).
- `logs\` — registro cronológico.

## 11. Erros, reexecução e registro de andamento

**Princípios:**

- Um pedido com erro não derruba os outros. Um plano inexistente não impede os demais do mesmo pedido.
- Toda conferência que falha para **antes** de emitir.
- Pedir de novo é seguro: o registro (`saida\sulamerica\estado.json`) pula o que já foi feito e
  **nunca reemite**, venha o pedido da tela ou da planilha.
- **"A mesma cotação"** = mesmo CNPJ + mesmos parâmetros que mudam o preço (vidas por faixa, idades,
  vigência, coparticipação, tipo de contratação, Cuidado 360°, congênere) + mesmo plano e acomodação
  (com "Com e sem", a versão com e a sem são duas cotações diferentes; a "com" é a mesma de um pedido
  "com": se já saiu antes, só a "sem" é emitida)
  como aparecem no portal. O id, a posição na planilha e a grafia do plano não importam. Mudou um
  parâmetro (ex.: a empresa contratou mais gente)? É outra cotação, e o robô emite.
- Para **emitir de novo de propósito** a mesma cotação (teste, demonstração, a de 45 dias venceu): em
  Nova cotação (ou "Cotar de novo" no Início), clique em Gerar. A tela avisa "Esta cotação já foi
  emitida" com o protocolo; clique em **"Emitir de novo mesmo assim"** e confirme. Sai um protocolo
  novo no portal; o de antes continua lá e o PDF de antes continua em Cotações. Vale só para cotação
  concluída (com PDF) e só naquele pedido: "Tentar de novo", planilha e pedido repetido continuam
  bloqueados. O registro guarda a cotação de antes em `reemitidos`, com o protocolo.
- Pela linha de comando, o equivalente é liberar o item com `python main.py --liberar "<chave>"` (a
  chave aparece em `python main.py --registro`).

**Ciclo de cada plano no registro:**

| Status | Significa | O que o robô faz na próxima vez |
| - | - | - |
| (sem registro) | nada emitido | cota normalmente |
| `emitindo` | clicou em emitir e não confirmou o protocolo | **não reemite**; mostra "Conferir no portal" |
| `emitida` | protocolo capturado, PDF não salvo | **não tenta de novo** (padrão, `recuperar_pdf_automatico: false`): fica em "Conferir no portal" para baixar à mão; com a opção ligada, tenta baixar pela página da emissão |
| `pdf_manual` | protocolo existe, PDF não recuperado | pede download manual em "Cotações emitidas" |
| `pdf_ok` | concluído | pula ("Já emitida antes") |

**Quando aparecer "Conferir no portal":** a pendência aparece no topo de Cotações. Entre no portal, em
"Cotações emitidas", e procure a empresa:

- **Saiu:** baixe o PDF lá e clique em **"Saiu: já tenho o PDF"**. O item fica concluído e continua
  bloqueando reemissão.
- **Não saiu:** clique em **"Não saiu: liberar"** e peça de novo. Liberar sem conferir pode gerar
  cotação repetida.

Pela linha de comando: `python main.py --pendencias` e `python main.py --liberar "<chave>"`.

| Sintoma | Causa provável | Ação |
| - | - | - |
| Faixa "Cadastre o login..." | não há login guardado | guardar o login na engrenagem do robô (tela 1) |
| "recusou o login guardado" | senha errada ou trocada | conferir no navegador comum e guardar de novo na engrenagem |
| "pediu um captcha" / "trocar a senha" | o portal quer uma pessoa | resolver no navegador comum e tentar de novo |
| "não encontrei '...' na tela" | site mudou ou seletor errado | ensaio com mapa e ajuste do seletor (Seção 7) |
| "Continuar continua desabilitado" | campo obrigatório que o robô não preencheu | olhar o print `*_continuar_desabilitado.png` |
| Timeout em "CNPJ válido" | Receita fora do ar ou CNPJ não encontrado | conferir o CNPJ; tentar depois |
| "o portal pede a idade exata..." | faltam idades | preencher as idades da faixa |
| "o plano '...' não está na lista" | nome/acomodação diferente do portal | escolher na lista da tela (ela mostra os nomes vistos no portal) |
| "valores da comparação não batem" | tela diferente do esperado | não emitiu; investigar com o mapa |
| "Já emitida antes" | a mesma cotação já foi emitida | baixar o PDF anterior; para emitir de novo de propósito, "Emitir de novo mesmo assim" no aviso da Nova cotação |
| "já existe um robô rodando" | tela e linha de comando ao mesmo tempo | esperar um terminar |
| `resultados_AAAAMMDD_HHMMSS.xlsx` criado | `resultados.xlsx` estava aberto no Excel | fechar o Excel; juntar depois |

## 12. Testes

**Automáticos (sem portal):** `python -m pytest` roda:

- `tests/nucleo/`: o núcleo e a tela com uma operadora falsa mínima (registro anti-reemissão, cofre,
  saídas, operadora que não carrega, robô travado que não segura o de outra operadora, pedido com duas
  operadoras que só conclui quando as duas terminam), sem nenhuma operadora de verdade;
- `tests/sulamerica/test_sulamerica_unidades.py`: leitura e validação, extração de valores, nomes de PDF,
  registro, retenção;
- `tests/sulamerica/test_sulamerica_simulador.py`: o robô contra o simulador (ensaio sem emitir; dois planos com
  "Copiar cotação" e reexecução sem duplicar; falha no download recuperada sem reemitir; plano
  inexistente sem travar os outros);
- `tests/sulamerica/test_sulamerica_tela.py`: a tela inteira como o corretor usa (ensaiar, gerar, baixar o PDF e o .zip,
  pedir de novo sem reemitir, parar no meio e continuar, configurar o robô pela engrenagem e conferir
  que o robô marcou 12 meses no portal, importar planilha com linha ruim, resolver pendência, recusar
  pedidos de fora).

Leva por volta de 25 minutos. Cada operadora tem a sua pasta de testes (`tests/<operadora>/`); mudança no
núcleo, na tela ou em `operadoras/base.py` exige todas passando. `Treinar no simulador.bat` mostra tudo
funcionando na tela.

**No portal real, nesta ordem. Não pule etapas:**

1. **Ambiente:** `instalar.bat` termina com os testes passando.
2. **Login:** guardar o login na engrenagem e clicar em Testar login. Esperado: "Login ok na SulAmérica"
   (com "Mostrar a janela do portal" ligado, para ver o robô entrar).
3. **Ensaio de uma empresa** até "Ensaio ok" (calibragem da Seção 7).
4. **Ensaio de 3 a 5 empresas variadas:** com e sem idades exatas, seguro novo, 12 meses, sem coparticipação.
5. **Primeira emissão real, 1 plano.** Comparar protocolo, valores e PDF com o portal.
6. **Emissão de 2 planos** da mesma empresa (testa "Copiar cotação" e a cópia para a pasta do cliente).
7. **Pedir de novo** a mesma cotação: tudo "Já emitida antes", nenhum protocolo novo.
8. **Parar no meio** de um pedido de 3 planos e continuar: cada plano emitido uma vez só.
9. **Lote pequeno acompanhado** (5 empresas pela planilha). Comparar com a cotação manual de pelo menos uma.

Divergência entre robô e cotação manual = investigar antes de seguir.

## 13. Operação no dia a dia

**Antes:** autorização da operadora arquivada; nenhuma outra janela do cotador aberta na máquina;
Newport Cotações aberto (janela preta + tela). Quando a Newport mudar um padrão (ex.: vigência), cada
corretor ajusta na engrenagem do robô.

**Durante:** a tela mostra o andamento; a janela do portal fica escondida. Se o portal pedir um código
de verificação, digite na faixa dourada da tela.
Dá para usar o computador normalmente.

**Depois:** conferir as cotações (situação e valores) e uma amostra de PDFs nas primeiras semanas;
tratar as pendências em Cotações; enviar propostas aos clientes pelo canal combinado, nunca em lote
sem revisão.

## 14. Evolução e novas operadoras

**Como entra uma operadora nova (Amil, Bradesco, Porto...):**

1. Grave em vídeo a cotação feita por um corretor, do login ao PDF, como foi feito para a SulAmérica.
2. Crie `operadoras\<id>\` com uma classe que herda de `operadoras\base.py` (`Operadora`): nome, cor,
   limites de vidas, faixas com idade exata, etapas, opções do formulário (`campos`) e os métodos do
   robô (`montar_pedido`, `nova_sessao`, `login`, `processar`...). `operadoras\sulamerica\` é o exemplo.
3. Registre em `operadoras\__init__.py` e crie a seção `operadoras: <id>:` no `config.yaml`.
4. Faça um simulador do portal novo e os testes; depois calibre no portal real (Seção 7).

A tela, o histórico, o registro anti-reemissão, os downloads e os ajustes passam a valer para ela sem
mudança. O passo a passo técnico está em `CLAUDE.md`.

**Outras evoluções:**

- **Integração com o sistema de estudos:** `resultados.xlsx` e a tela já trazem o valor por vida de
  cada faixa; dá para alimentar o estudo direto, usando o PDF como documento oficial.
- **30 vidas ou mais:** é outro módulo ("Módulo Cotação"), não coberto pelo vídeo. Mapear com um vídeo novo.
- **Agendamento:** o login é automático, mas se o portal pedir código de verificação alguém precisa
  estar na tela; captcha nunca é resolvido pelo robô.
- **API oficial:** se existir, troca só a camada de navegação da operadora.

## 15. Solução de problemas

- **"python não é reconhecido"**: reinstale marcando "Add python.exe to PATH" e rode `instalar.bat` de novo.
- **A tela não abre**: veja a janela preta. Se diz que a porta está em uso, já há um Newport Cotações
  aberto: use a aba que já existe no navegador (`http://127.0.0.1:8600`).
- **"o navegador do robô não está instalado"**: rode `instalar.bat` de novo (ou `playwright install chromium`).
- **"Não consegui falar com o robô"**: a janela preta foi fechada; abra pelo `.bat` de novo.
- **Certificado ou proxy**: se a máquina acessa o site no navegador comum, peça à TI para liberar o
  Chromium do Playwright no proxy.
- **Erro de bloqueio do `perfil_navegador`**: feche a tela (janela preta) e abra de novo; a janela do
  portal fecha junto.
- **"Escolher pasta" não abre**: cole o caminho da pasta no campo.

## 16. Checklist final

**Preparação**
- [ ] Autorização da operadora obtida e arquivada
- [ ] Python e `instalar.bat` rodados; testes passando
- [ ] Corretor treinado no simulador (`Treinar no simulador.bat`), inclusive na engrenagem do robô

**Calibragem**
- [ ] Ensaio de uma empresa até "Ensaio ok", valores conferidos com o portal
- [ ] `codegen\mapa_seletores.md` preenchido
- [ ] Ensaio de empresas variadas (idades exatas, seguro novo, 12 meses, sem coparticipação)

**Emissão**
- [ ] 1 plano emitido e conferido; 2 planos com "Copiar cotação"; pedir de novo sem duplicar
- [ ] PDFs na pasta do cliente com o nome certo e baixáveis pela tela
- [ ] Parar no meio e continuar sem duplicar
- [ ] Lote pequeno acompanhado e comparado com cotação manual

**Operação**
- [ ] Corretores treinados no login da engrenagem (Guardar, Testar login, Apagar credenciais ao sair), nas pendências e na conferência
- [ ] Responsável técnico e responsável de negócio nomeados

## 17. Glossário

- **RPA:** automação de tarefas repetitivas feitas em telas, como um humano faria.
- **Playwright:** biblioteca que controla um navegador real a partir de código.
- **Seletor:** forma de localizar um elemento na página (botão, campo, texto).
- **Ensaio:** execução que percorre todas as telas e para antes de emitir.
- **Mapa:** print, HTML e árvore de acessibilidade de cada tela, para calibrar seletores.
- **Registro de andamento:** `saida\<operadora>\estado.json`, que impede emissão duplicada.
- **Congênere:** operadora de saúde de onde a empresa está vindo.
- **Cuidado 360°:** benefício da SulAmérica que inclui odonto e vida sem custo adicional na proposta.
- **Idades exatas (agravadas):** faixas em que o portal pede a idade de cada vida.
- **Copiar cotação:** atalho do portal que reaproveita todos os dados para cotar outro plano.
- **Protocolo:** número da cotação emitida ("Protocolo Saúde nº ...").
- **IOF:** 2,38% sobre o prêmio de saúde; o portal calcula por vida e soma.
- **Coparticipação:** parte do custo paga pelo beneficiário ao usar o plano.
