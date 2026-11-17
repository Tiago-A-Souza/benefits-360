# Mapa de seletores (preencher na calibragem)

Para cada tela, anote o que funcionou no portal real e o que precisou mudar em
`operadoras/sulamerica/seletores.py`. Fonte: `saida/sulamerica/mapa/<execução>/*.aria.txt` (árvore de
acessibilidade), `*.html` e `*.png` gerados por `python main.py --ensaio --mapear`.

| Tela (rota) | Seletor em seletores.py | Status | Ajuste feito / observação |
| - | - | - | - |
| Login (LoginGeral.aspx) | `login_campo_cpf`, `login_campo_email`, `login_campo_senha`, `login_ok_entendi`, `login_botao_entrar` | OK (estrutura, 03/11) | ver "Login no portal real" abaixo; falta o login completo |
| Login: respostas | `login_mensagem_erro`, `login_validacao`, `TEXTO_LOGIN_RECUSADO`, `TEXTO_TROCA_SENHA`, `TEXTO_SELECAO_CORRETORA`, `captcha`, `TEXTO_COOKIES` | VALIDAR | mensagem real de senha recusada? aparece a escolha de corretora (EV/EA/AA)? |
| Código de verificação (se houver) | `campo_codigo`, `botao_confirmar_codigo` | VALIDAR | nunca vira mapa; o portal pede código? por SMS ou e-mail? |
| Sair do portal (cabeçalho do portal antigo) | `menu_do_portal`, `botao_sair_do_portal`, `TEXTO_SAIR_DO_PORTAL` | VALIDAR | achado no `01_login.html` de 05/11: menu lateral (ícone de 3 barras, `a.menuLeft` ...`wtMenuLateral2`) com "Sair do Cotador" (`div.logout` ...`wtLogout`, OsAjax); antes do login fica escondido. Se o menu não abrir, o robô dispara o clique direto no item |
| Módulos (LoginGeral.aspx) | `TEXTO_TELA_MODULOS`, `TEXTO_CARD_PME` | OK (04/11) | abriu o cotador (aba: confirmar); demora, e o robô agora espera o tempo de tela. Sem mapa: mesma URL do login |
| Sair da cotação (cotador) | `TEXTO_SAIR_COTACAO`, `modal_sair`, `RX_CONFIRMA_SAIDA`, `RX_CANCELA` | VALIDAR | modal "Deseja realmente sair da cotação?" com fundo escuro; rótulos dos botões? |
| Dados da empresa (/dados-empresa) | `campo_cnpj`, `msg_cnpj_valido`, `campo_vendedor` | VALIDAR | máscara aceita `press_sequentially`? |
| Cuidado 360° (/cuidado-cross) | `radio`, `botao_prosseguir` | VALIDAR | com "Não" aparece modal? |
| Congênere (/congeneres) | `campo_congenere`, `opcao_congenere`, `chip_congenere`, `check_seguro_novo` | VALIDAR | nomes exatos da lista |
| Vidas (/vidas-saude) | `campo_faixa`, `status_vidas` | VALIDAR | |
| Idades (/distribuicao-agravadas) | `campo_idade`, `botao_adicionar_idade` | VALIDAR | quais faixas pedem idade? (vídeo: 0–18) |
| Planos (/precificacao-planos) | `filtro_radio`, `filtro_check`, `botoes_cards`, `card_do_botao`, `botao_pagina`, `botao_desmarcar_todos`, `skeletons` | VALIDAR | |
| Comparação (/comparacao-planos) | texto da página (`extracao.ler_tabela_comparacao`) | VALIDAR | |
| Resumo (/resumo-final) | texto da página (`extracao.ler_resumo`) | VALIDAR | sem "Sair da cotação" nesta tela |
| Emitida (Simulador.aspx) | `TEXTO_EMITIDA`, `TEXTO_PROTOCOLO`, `TEXTO_BAIXAR`, `TEXTO_COPIAR`, `TEXTO_SIM`, `TEXTO_VOLTAR_HOME` | VALIDAR | download direto ou abre aba? |

**LGPD: login e código de verificação no mapa.** O login é automático (cofre do Windows). Na tela de
login (URL igual à `urls.login` da operadora ou `input[type=password]` em qualquer frame), o
`Mapeador.registrar` (`nucleo/navegador.py`) só grava o `01_login.*` que o robô tira ANTES de digitar,
com todos os campos vazios: é ele que calibra os seletores do login. Depois que o robô começa a digitar,
nada da tela de login é gravado, nem em erro (forcar=True); a tela de código de verificação nunca é
gravada. O log diz "mapa não gravado: tela de login" (ou "...de código de verificação"). A tela de
módulos tem a mesma URL do login e também não tem mapa: se a etapa `modulos` falhar, calibre pelo texto
do log ou peça ao usuário um print feito por ele, sem dados de login. Nas outras telas, os valores de
login que o robô leu saem do HTML e da árvore como ••• e ficam cobertos no print.

## Login no portal real (mapa de 03/11, `01_login` com os campos vazios)

- 1º "Testar login" falhou antes de digitar ("Não consegui preencher o login"): o seletor da caixa
  "Ok, entendi!" era `get_by_role("checkbox", name="Ok, entendi")`, mas a caixa **não tem nome acessível**
  (`<input type=checkbox class="check-custom aceite">` sem `<label>`; o texto é um
  `<div class="aceite_texto">Ok, entendi!</div>` logo depois). Agora: o texto exato "Ok, entendi!" e a
  caixa imediatamente antes dele (`preceding-sibling`), um elemento só. As credenciais não foram marcadas
  como recusadas (nada foi digitado).
- Página feita em OutSystems (`VanillaTheme`, `OsAjax`). Um `<form>` só, **sem iframe**; os campos já
  vêm no HTML (não carregam depois). Sem banner de cookies por cima (o ACEITO já tinha sido clicado).
- Campos sem `<label>`: o nome acessível vem do placeholder. `get_by_role("textbox", name=...)` exato acha
  um só: "CPF" (`wtInpCodCPFVendedor`, maxlength 20, aceita só dígitos e . - ao digitar), "E-mail"
  (`wtInpEmlVendedor`, maxlength 250), "Senha" (`wtInpPassword`, type=password, **maxlength 16**).
  O robô não digita um valor maior que o `maxlength` (seria cortado e recusado): para antes e avisa.
- Botão: `input type=submit` "Entrar" (`wtBtnLogin3`), `OsPage_ClientValidate` + `OsAjax`.
- AJAX: sair do CPF (`onblur`) clica num botão escondido (`wtBtnBlurCPF`) que faz POST; a caixa faz POST
  (`OsAjax ... 'Change'`); Entrar faz POST e **a página não recarrega**. O robô sai do CPF (`blur`) e
  espera a resposta, marca a caixa e espera, e só então clica em Entrar. A recusa vem como mensagem
  (`.Feedback_Message_Error`, a confirmar) e a validação do formulário como `.ValidationMessage`
  (validação = "falha", nunca "recusado").
- Blocos escondidos na mesma página, que podem aparecer depois do Entrar: "REDEFINIR A SENHA"
  (`wtCntExpiraSenha`, troca de senha), "Com qual módulo deseja trabalhar?" (`wtCntSelModulo`, módulos) e
  "Selecione sua Corretora ou EV / Gerente Comercial ou EA / Ação de Apoio ou AA" (`wtCntSelEVEAAA`):
  se este aparecer, o robô para com "selecao_corretora" (ainda não sabe escolher).
- O simulador imita essa tela (caixa sem nome, botão escondido do CPF, AJAX, blocos escondidos, senha
  de no máximo 16 caracteres).
- 2º "Testar login" (16:12): os seletores do login funcionaram (preencheu, marcou, Entrar) e o portal
  respondeu em `.Feedback_Message_Error`: **"Já existe um acesso ativo para esse CPF. Tente novamente mais
  tarde."** Não é senha errada, mas o robô (que trata toda mensagem de erro como recusa) marcou o login
  como recusado. Agora `TEXTO_ACESSO_ATIVO` vira o motivo `acesso_ativo`: para, avisa e **não** marca
  recusado. O portal só aceita uma sessão por CPF: o corretor não pode estar logado no navegador comum
  (ou em outro computador) enquanto o robô entra. A mensagem de senha errada de verdade ainda não foi vista.
- 3º a 7º "Testar login" (04/11): a senha guardada tinha mais de 16 caracteres (o `maxlength` do campo); o
  robô parou antes de digitar, mas a tela mostrava a mensagem genérica. Agora o motivo é `senha_comprida`
  (tela: "A senha guardada é maior do que o portal aceita", com o link para a engrenagem) e a engrenagem
  recusa ao guardar uma senha maior que `senha_max` (16, declarado no campo `credenciais` da operadora).

## Primeiro pedido no portal real (04/11, credencial de testes)

- Login OK. Clicar em "Cotação PME" abriu o cotador (`/dados-empresa`, "Comece por aqui", vendedor
  "TESTE - LEONARDO TURYA" já escolhido), mas o robô desistiu antes: esperava 30 s fixos e só conferia
  se a URL ainda tinha "LoginGeral.aspx". Agora espera o tempo de tela (`timeout_tela_ms`) até alguma aba
  (a mesma ou nova) estar numa rota do cotador (pelo caminho da URL) ou mostrar "Comece por aqui".
  A identificação de tela também passou a olhar só o caminho da URL (nunca a consulta, ex.: `?volta=`).
- Na recuperação, "Sair da cotação" abre um modal **"Deseja realmente sair da cotação?"** com fundo
  escuro (`data-slot="dialog-overlay"`) que cobre a tela: o robô clicava de novo em "Sair da cotação" por
  baixo do fundo até estourar o tempo. Agora acha o diálogo (`modal_sair`) e clica no botão que confirma
  (`RX_CONFIRMA_SAIDA`; se não, o único que não é cancelar). **VALIDAR** os rótulos: o próximo mapa
  `NN_modal_sair.*` mostra.
- Depois disso o robô ia para a página de login com a sessão viva e o portal respondeu "Já existe um
  acesso ativo para esse CPF". Agora, de dentro do cotador, o robô nunca volta ao login: sai pelo botão
  + modal; se não conseguir, só avisa, e o pedido seguinte só começa se a tela voltar ao início (módulos ou
  "Comece por aqui" com o CNPJ vazio).
- Depois da emissão, `recuperar_pdf_automatico: false`: PDF que não baixou fica em "Conferir no portal"
  (baixar à mão) e o robô não reabre a página da emissão (ver a pergunta abaixo).

## 05/11: "acesso ativo" causado pelo próprio robô

- Pedidos de 05/11 11:42–11:44 e 11:55: o robô já tinha a sessão aberta (tela de módulos) e, "para conferir",
  recarregava a LoginGeral.aspx. O portal real mostra o formulário de novo e recusa o segundo login ("Já
  existe um acesso ativo para esse CPF"). Agora `entrar()` confia na tela que já é do portal logado (módulos,
  cotador, emissão) e só abre o login numa página em branco; se a sessão tiver caído, a próxima tela leva ao
  login (a tela de módulos aceita isso) e o robô entra ali.
- "Acesso ativo" de outro lugar (navegador comum, janela fechada sem sair): o robô espera 1 min e tenta de
  novo, por até 10 min (`login_reentrada_ms`, `login_liberacao_ms`), sem marcar o login como recusado.
- O tour "Guia de navegação" aparece com atraso e podia cobrir o Continuar entre a conferência e o clique:
  agora é pulado antes de qualquer ação (`page.add_locator_handler`).
- Simulador: `um_acesso_por_cpf` (recarregar o login com a sessão viva mostra o formulário e o 2º login é
  recusado) e `acesso_ativo_por` (as próximas N entradas recebem "acesso ativo").
- "Pedido que não fez nada" (11:41, 11:55): era a mesma cotação emitida em 04/11 (protocolo 8692472), que o
  registro anti-reemissão pula ("Já emitida antes"). Para uma demonstração, usar outra empresa ou outro plano.

## 05/11: a tela final de cada cotação ficava aberta

- Nas 3 emissões reais (04/11 17:08, 05/11 13:07 e 14:58) o robô baixou o PDF e depois ficou procurando o
  botão "Voltar para a home" (texto exato) até a janela ser fechada ("Target page ... has been closed").
- A tela da cotação emitida (Simulador.aspx) não virava mapa: o `Mapeador` a tomava por tela de código de
  verificação (algum `input` com "token"/"código" no nome; o próprio URL tem `?Token=`). Agora só conta
  campo de código **visível** (quem digita o código precisa ver o campo), e o log diz qual campo fez a
  tela ser tomada por tela de código (o nome do campo, nunca o valor).
- O robô agora: grava o mapa da emissão antes (`NN_emitida`) e depois do download (`NN_emitida_pdf`)
  (o fechamento das abas abertas pelo download foi desfeito depois); para voltar ao começo, procura
  "Voltar para a home" num botão, link ou texto, aceitando "Voltar para home" e "Voltar ao início" (`RX_VOLTAR_HOME`).
  Se esse botão não aparecer, usa "Nova cotação" (assistente novo do cotador). Espera o começo em qualquer
  aba. Nunca recarrega o login nem a página da emissão.
- **VALIDAR** na próxima emissão: o texto real do botão e se o download abre outra aba (os mapas
  `NN_emitida*` mostram). Simulador: `pdf_abre_aba`, `sem_voltar_home`.

## 05/11 19:55: a tela da emissão no mapa e o painel "Estou em cotações"

- Primeira emissão com a tela da emissão no mapa (`12_emitida`, `13_emitida_pdf`). Botões reais:
  "BAIXAR COTAÇÃO SAÚDE", "Iniciar Contratação" (o robô nunca clica), "Nova cotação", "ENVIAR POR E-MAIL",
  "COPIAR COTAÇÃO", "Voltar para a Home", "ADICIONAR EMAIL", e o banner de cookies (ACEITO). Os seletores
  `TEXTO_BAIXAR`, `botao_copiar`, `botao_voltar_home` e `botao_nova_cotacao` casam com esses textos. O
  download não abriu outra aba.
- "Voltar para a Home" leva a `os11.../SaudeCotador/PainelCotacao.aspx`: painel **"ESTOU EM COTAÇÕES"**
  (cartão "NOVA COTAÇÃO", contadores em preenchimento/concluídas/perto de expirar/em análise/criticadas/
  recusadas, "IR PARA O MÓDULO IMPLANTAÇÃO", "VER TODAS AS COTAÇÕES", "SELECIONAR OUTRO MÓDULO", menu de 3
  barras). O robô não conhecia: esperou 60 s, parou e, no pedido seguinte, recarregaria o login com a sessão
  viva. Agora o painel é um começo (`ROTA_PAINEL`, `TEXTO_PAINEL`, etapa `painel`: "NOVA COTAÇÃO" abre o
  cotador; sem o cartão, "SELECIONAR OUTRO MÓDULO"), conta como sessão aberta em `entrar()` e serve para
  sair do portal (o menu está nele também). **VALIDAR** no próximo mapa (`NN_painel`): para onde "NOVA
  COTAÇÃO" leva.
- O painel não virou mapa ("mapa não gravado: tela de login"): provavelmente um campo de senha escondido no
  cabeçalho. Agora só conta como tela de login o campo de senha visível ou com algo digitado (o caminho da
  LoginGeral.aspx continua bloqueado sempre).
- O pedido desta execução tinha só a versão "com": "Cotar de novo" trazia a coparticipação da cotação
  antiga. Agora traz só empresa, vidas e planos; o que o robô preenche vem da configuração de hoje.

## 06/11 (madrugada): o modal "Copiar Cotação" tem o conteúdo num iframe

- Primeira execução com as duas versões pedidas: a "com" saiu (protocolo 8701467) e o robô clicou em COPIAR
  COTAÇÃO, mas parou no modal. Mapa `14_ERRO_emitida`: `dialog "Copiar Cotação"` com um `iframe`
  (`PopUpCotDuplicar.aspx?InIdCotacao=...`); "Deseja copiar a cotação?", NÃO e SIM ficam dentro do iframe e o
  robô procurava na página. Agora procura no iframe (`sel.frame_modal_copiar`) e, se não houver, na página.
  O simulador imita o iframe. **VALIDAR**: o SIM do iframe (botão ou link) leva ao "Comece por aqui".

## 05/11 21:16 e 22:15: só a versão "com" foi pedida (JavaScript velho na tela)

- A aba da tela mandou a coparticipação da cotação antiga: o Chrome reaproveitava o JavaScript antigo até
  depois do F5 (sem `Cache-Control`). Agora os arquivos vão sem cache e com a versão do servidor no endereço.
- Por um tempo, entre uma cotação e a próxima, o robô saía do portal e abria uma janela nova. **Desfeito** em
  05/11: o corretor reviu o vídeo e confirmou que entre a versão com e a sem ele **não** sai nem fecha nada:
  COPIAR COTAÇÃO → "Deseja copiar a cotação?" → SIM → "Comece por aqui" preenchido → todas as telas (só muda
  o que for diferente) → na tela Planos troca o filtro de coparticipação → emite e baixa o 2º PDF.
  Também saiu o fechamento das abas que o download abrisse.

## 05/11: "Com e sem" coparticipação (2 cotações por plano)

- Caminho escolhido: a 1ª versão (com) faz o fluxo inteiro; a 2ª (sem) usa **Copiar cotação** e, na tela
  Planos, troca só o filtro de coparticipação (marca "Sem coparticipação" e desmarca "Com") e lê a lista
  de novo. O card e as "Características da Cotação" do resumo são conferidos com a versão da vez (se não
  baterem, para sem emitir).
- Se a cópia não deixar trocar o filtro (caixa desabilitada), o robô sai da cotação ("Sair da cotação" +
  modal, mesma aba, sem login nem logout) e faz a 2ª versão por NOVA COTAÇÃO no painel. Guarda isso em
  `saida/sulamerica/portal.json` (`copia_trava_copart`) e, das próximas vezes, troca de versão direto pelo
  "Nova cotação" da tela da emissão. O log diz qual caminho valeu: "Filtro 'Sem coparticipação': marcado"
  (cópia) ou "Na cotação copiada o portal não deixou mudar o filtro" (plano B).
- **VALIDAR** no portal real: qual dos dois caminhos funciona (o simulador faz os dois: padrão = a cópia
  deixa trocar; `copia_trava_copart` = travada). Anotar aqui depois da primeira emissão real com "Com e sem".

## Perguntas que só o portal real responde

- [ ] "Sair da cotação" pede confirmação? Para onde leva?
- [ ] "Voltar para a home" leva à tela de módulos sem pedir login de novo?
- [ ] Na cópia, o plano anterior vem marcado na tela de planos?
- [ ] A URL da emissão (Simulador.aspx?Token=...) continua válida depois (recuperação de PDF)?
      E abrir essa URL de novo **não gera protocolo novo**? (A recuperação de PDF reabre essa URL; o robô
      confere o protocolo, mas só percebe um protocolo novo depois que ele já existe. Confirmar antes de
      confiar na recuperação automática.)
- [ ] Quanto tempo a sessão dura sem atividade?
