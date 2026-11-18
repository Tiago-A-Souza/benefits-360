# Manual de manutenção do robô de cotações (Newport)

Para quem vai consertar o robô sem ter visto como ele foi construído. Escrito em 18/11/2026 por quem o mantinha
(Claude Code, trabalhando com o Tiago). Regras de ouro:

- **Fato** = visto no código, num log ou num teste. **Suposição** = marcada como tal. **Não sei** = listado no fim.
- Nenhum exemplo abaixo contém senha, CPF de pessoa ou dado de cliente. Quando aparece um CNPJ, é o fictício
  `11.222.333/0001-81` dos testes.
- O robô de verdade é o código de `operadoras/<id>/`. O que está em `C:\np\rpa` é outra cópia/instalação do projeto
  (ver "Não sei": não conferi como ela se liga a esta).

---

## 1. Como o robô é organizado

### 1.1 Pastas

| Pasta / arquivo | O que é |
|---|---|
| `main.py` | linha de comando (`--ensaio`, `--mapear`, `--linha`, `--liberar`...) |
| `app/` | a **tela do corretor** (Starlette em `127.0.0.1:8600`, JS puro em `app/web/`) e o coordenador dos robôs (`app/trabalhador.py`) |
| `nucleo/` | o que vale para **qualquer** operadora: navegador (`navegador.py`), anti-reemissão (`estado.py`), saídas (`saidas.py`), cofre de senhas (`credenciais.py`), trava (`trava.py`), configuração (`registro.py`, `configuracao.py`) |
| `operadoras/base.py` | a interface que toda operadora implementa |
| `operadoras/<id>/` | **tudo** que é de uma operadora: `fluxo.py` (máquina de telas), `etapas.py` (uma função por tela), `seletores.py`, `extracao.py` (lê texto das telas), `login.py`, `telas.py`, `pedido.py`, `planilha.py`, `simulador/` |
| `tests/nucleo`, `tests/<id>` | testes (o núcleo só usa a operadora falsa `tests/nucleo/operadora_falsa.py`) |
| `config.yaml` | padrões da Newport e URLs reais; `config_simulador.yaml` liga tudo ao simulador (porta 8601) |
| `saida/<id>/` | tudo que o robô produz (ver seção 2). **Nunca versionar** (`.gitignore`) |
| `codegen/` | mapas dos vídeos dos corretores e notas de calibragem |
| `docs/` | este manual |

Operadoras: `sulamerica` (Cotação PME 3 a 29 vidas), `bradesco` (Cotação SPG), `amil` (vendasmil, Cotação PME).

### 1.2 Peças que importam para consertar

- **Um robô por operadora** (`app/trabalhador.py`, classe `_RoboOperadora`): cada operadora tem a sua thread, fila,
  janela de navegador, trava, log (`cotacao.<id>`). O `Trabalhador` divide um pedido entre operadoras e só conclui o
  trabalho quando todas terminam. Cada thread abre o seu próprio `sync_playwright()`.
- **Trava** (`nucleo/trava.py`): trava de arquivo por pasta de saída; impede dois robôs (tela + linha de comando) mexendo
  em `saida/<id>/` ao mesmo tempo. A tela segura a trava enquanto a janela da operadora estiver aberta.
- **`estado.json` = anti-reemissão** (`nucleo/estado.py`). Chave = CNPJ + parâmetros que mudam o preço + plano e
  acomodação **como o portal mostra** (o id e a grafia do pedido não entram). Estados: `emitindo` (gravado com fsync
  logo antes do clique de emitir), `emitida` (protocolo lido), `pdf_ok` (PDF salvo), `pdf_manual`; a Amil tem também
  `digitando` (não bloqueia). Todos os outros bloqueiam nova emissão. Item travado só sai por "Não saiu: liberar" na
  tela ou `python main.py --liberar "<chave>"`, **depois de conferir no portal** que não há cotação emitida. Nunca edite
  o arquivo à mão.
- **Confirmação humana**: a tela só emite com `confirmado: true` no pedido (botão "Gerar", que o corretor clica); a
  linha de comando pede para digitar EMITIR; "Emitir de novo mesmo assim" é um botão da tela com confirmação, e é a
  única exceção à regra de nunca reemitir (o servidor só aceita protocolos `pdf_ok` do próprio pedido).
- **Parar** (`nucleo.navegador.Parado`) é levantado na hora, inclusive no meio da espera de uma tela. Não é levantado entre gravar `emitindo` e ler o protocolo.
- **Tela local**: só escuta `127.0.0.1`, e todo pedido que muda algo exige `X-Newport-Tela: 1` + mesma origem
  (`SoDaPropriaTela`, `app/servidor.py`). Não afrouxar: é o que impede um site aberto de disparar emissões.

### 1.3 O que NÃO pode mudar sem reaprovação (e por quê)

`operadoras/sulamerica/`, `operadoras/bradesco/`, `operadoras/amil/` e os testes delas estão **congelados**: são versões
aprovadas pelo Tiago depois de emitir de verdade no portal.

| Tag | Quando | Observação |
|---|---|---|
| `sulamerica-v1-aprovado` | 06/11 | primeira versão aprovada |
| `sulamerica-v2-aprovado` | 15/11 | depois do portal atualizado (ver 3.1) |
| `bradesco-v1-aprovado` / `-v2-aprovado` | 10/11 / 15/11 | a pasta da v2 é idêntica à v1 (só mudou `config.yaml`) |
| `amil-v1-aprovado` | 15/11 | |

Por quê: cada mudança sem reaprovação pode quebrar a emissão que já funciona, e emissão errada gera cotação real num
portal de seguradora. Regra prática: só mexer com **pedido explícito do Tiago para aquela operadora**; corrigir só a
pasta da operadora; espelhar no simulador; rodar os testes dela; criar a tag nova `<id>-vN-aprovado`. Para ver o que
mudou depois da aprovação: `git diff <tag> -- operadoras/<id>`. Mudança em `nucleo/`, `app/` ou `operadoras/base.py`
exige os testes de **todas** as operadoras (regra 10 do `CLAUDE.md`) e não pode forçar mudança nas congeladas.

---

## 2. Onde olhar quando algo dá errado

Tudo em `saida/<id>/` (`<id>` = `sulamerica`, `bradesco` ou `amil`), exceto o histórico da tela (`saida/tela.db`).

| O quê | Caminho | Para quê |
|---|---|---|
| **Log da execução** | `saida/<id>/logs/execucao_AAAAMMDD_HHMMSS.log` | começo de tudo. Uma linha por fato. Veja o **último** (`ls -t`). É UTF-8; no PowerShell 5 use `Get-Content -Encoding UTF8` ou aparece "Ã§" |
| **Mapa de telas** | `saida/<id>/mapa/AAAAMMDD_HHMMSS/NN_<etapa>.png/.html/.aria.txt` | print, HTML e árvore de acessibilidade da tela. Só com "Guardar print de cada tela" ligado (`execucao.mapear`) **e** sempre nas falhas |
| **Mapa de erro** | `.../NN_ERRO_<etapa>.*` e `NN_ERRO_<etapa>.erro.txt` | o `.erro.txt` traz o erro inteiro do Playwright, `visibilidade`/`foco`, se a página desenha quadros (`requestAnimationFrame`), requisições pendentes e com erro (host e caminho, sem query) e erros de JavaScript do portal. **Leia antes de supor a causa** |
| **portal.json** | `saida/<id>/portal.json` | fatos aprendidos do portal (nunca credenciais): `senha_max`, `copia_trava_copart`, `build_cotador` (SulAmérica), sessão da Amil (`sessao_login_em`, `sessao_viva_em`, `sessao_duracoes_min`) |
| **estado.json** | `saida/<id>/estado.json` | o que já foi emitido; `itens`, `reemitidos`, `liberados`, `criterios`. `python main.py --registro` e `--pendencias` listam |
| **resultados.xlsx** | `saida/<id>/resultados.xlsx` | uma linha por plano: status, protocolo, totais, `valor_vida_<faixa>`, erro, etapa_erro |
| **PDFs** | `saida/<id>/pdfs/` | arquivo morto; a cópia vai para a pasta do cliente (`pasta_destino`) |
| **Histórico/eventos da tela** | `saida/tela.db` (SQLite): tabelas `trabalhos`, `cotacoes`, `eventos`, `catalogo`, `empresas` | `eventos` guarda cada linha de log por trabalho, inclusive de execuções cujo arquivo de log você não achar. `trabalhos.itens_json` guarda os pedidos |
| **Ajustes do corretor** | `saida/config_tela.json` | o que ele mudou na engrenagem do robô |
| **API ao vivo** | `GET /api/estado` (conexão de cada robô, trabalho atual), `GET /api/trabalhos/{id}`, `GET /api/eventos` (SSE) | `atual: null` = nada rodando |

### 2.1 Como achar em que etapa o robô parou

1. No log, a linha `falha na etapa <etapa> (tela): <mensagem>` (ou `(dado do pedido)`). A etapa é o nome da tela.
2. A tela do corretor mostra a mesma coisa: "O robô parou na tela <nome>: <mensagem>. Pedir de novo é seguro: nada foi emitido."
3. O mapa `NN_ERRO_<etapa>` é a tela **no instante da falha**. Compare com o mapa `NN_<etapa>` de uma execução que
   deu certo (mesma pasta `mapa/`, outro horário).
4. Etapas da SulAmérica: `dados_empresa`, `cuidado_360`, `congenere`, `vidas`, `idades`, `planos`, `comparacao`,
   `resumo`, `emitida`, `modulos`/`painel` (começo). Bradesco (ids do `__init__.py`): `login`, `portal`, `empresa`, `grupos`, `regiao`, `personalizar`, `configuracao`,
   `resultado`, `complementares`, `calculo`, `alterar` (o erro `inicio` também aparece, na fase de abrir o cotador). Amil: `login`, `oportunidade`, `vinculo`, `planos`,
   `revisar`, `concluir` (+ o PDF).

### 2.2 Mensagens de erro e o que significam

| Mensagem (trecho) | Significa |
|---|---|
| `não encontrei 'título da tela X' na tela em Ns` | a tela esperada não apareceu no prazo (`tempos.timeout_tela_ms`). Veja o `.erro.txt`: página desenhando? requisição pendente? (ver 3.1, "tela travada") |
| `valores da comparação não batem: faixas ausentes...` | a tabela ainda não tinha carregado quando foi lida |
| `valores da comparação não batem: soma das faixas X difere do preço do plano Y` | preço do card lido errado (era por vida, 15/11) ou valor mudou de verdade |
| `o registro diz que esta cotação já foi feita; não crio outra` | anti-reemissão; é proteção, não defeito. Use "Emitir de novo mesmo assim" se for teste |
| `Login: o portal diz que já existe um acesso ativo para este CPF` + `O robô tenta entrar de novo em 60 s` | outra sessão do mesmo CPF (sessão antiga do robô, ou navegador do corretor). O robô espera até 10 min (`login_liberacao_ms`) |
| `O portal recusou o login guardado...` | senha recusada: o robô **para** e não tenta de novo até o corretor guardar a senha outra vez (evita bloquear a conta) |
| `O portal ... pediu um captcha` / `pede para trocar a senha` | robô para; o corretor resolve no navegador dele |
| `O portal pediu o código de verificação de 8 dígitos` (Amil) | a tela pede o código na faixa dourada; o robô espera até 5 min (`timeout_codigo_ms`) |
| `Começo de pedido fora da tela de módulos (X); voltando ao início` | o pedido começou numa tela que não é o começo; o robô tenta sair da cotação |
| `não achei 'Voltar para a home' nem 'Nova cotação' na tela da cotação emitida` | o robô achou que estava na página de cotação emitida (só pela URL); ver 3.1 (módulos na URL da emissão) |
| `falha na etapa ... (dado do pedido)` | plano inexistente, idade faltando etc.; erro do pedido, não do portal |
| status `VERIFICAR` | emissão incerta (passou do clique de emitir mas o PDF/protocolo não foi confirmado): **conferir no portal** antes de qualquer coisa |
| `Target page, context or browser has been closed` | alguém fechou a janela do robô (ou o processo foi encerrado). Não é erro de seletor |
| `Locator.click: Timeout 30000ms exceeded` | algo cobre o elemento (modal) ou a página não terminou de carregar; o log só mostra a 1ª linha, o resto está no `.erro.txt` |

Avisos (WARNING) que **parecem erro e não são** estão na seção 7.

---

## 3. Falhas conhecidas por operadora

Cada item: **sintoma → causa → conserto**. Frequência é o que observei; marcada quando é impressão.

### 3.1 SulAmérica (o primeiro robô; Next.js no cotador, WAF Incapsula)

1. **Preço do card errado (15/11, frequente depois do portal atualizado).**
   - Sintoma: `soma das faixas 1882.35 difere do preço do plano 627.45` (ou similar) na etapa `comparacao`.
   - Causa: o portal passou a mostrar no card "R$ 627,45 por vida / mês" e, numa linha à parte, "Total estimado: R$ 1.882,35 /
     mês (3 vidas)". O robô lia o 1º valor em R$ do card (por vida); a Comparação soma as faixas (o total).
   - Conserto: `extracao.preco_do_card` lê "Total estimado"; cai no 1º valor se o card for do layout antigo.
     Teste: `test_card_do_plano_usa_o_total_nos_dois_layouts_do_portal`.
2. **Tela travada com corpo antigo (15/11; aconteceu em toda rodada que tinha os três robôs juntos).**
   - Sintoma: `não encontrei 'título da tela cuidado_360' na tela em 150s` (também em `vidas`, `idades`, `comparacao`).
     No mapa de erro: URL e barra de navegação da tela nova, mas o **corpo é o da tela anterior** e o print sai quase
     branco; `.erro.txt`: `visibilidade: visible`, quadros de animação `ok`, **zero** requisições pendentes, nenhum erro de
     JavaScript.
   - Causa: **não confirmada.** O front-end novo da SulAmérica deixa a troca de tela pela metade. Observado em 15/11: travou em **todas** as 8 rodadas em que a
     Amil estava no pedido; nas rodadas sem a Amil (5 ensaios/emissões solo ou só com a Bradesco) não travou, **exceto uma espera de ~60 s na Comparação
     num ensaio solo** (16:28, o conteúdo apareceu sozinho). Por que a Amil influenciaria (navegadores são separados) não sei.
   - Conserto que funciona: `telas.esperar_tela` (só antes do resumo) espera 15 s, **recarrega a página uma vez**; o F5
     leva o assistente de volta a `/dados-empresa` vazio (o estado só existe na aba) e levanta `TelaReiniciou`;
     `fluxo.processar_pedido` retoma o pedido pela tela da empresa (até 6 vezes por pedido). Na rodada de 15/11 19:53 travou 4
     vezes (1 em Idades, 3 no Cuidado 360°) e todas se recuperaram, com 4 cotações emitidas. Log: `recarregando a página
     uma vez` e `retomando o pedido desde a tela da empresa`. O simulador reproduz (`sim.travar_troca_cuidado`).
   - Nunca recarregar no `resumo` nem depois dele (emissão em andamento).
3. **Conteúdo da Comparação lido antes de existir.** Sintoma: `faixas ausentes na comparação: [todas]`. O título "Comparação de
   Planos" aparece numa região de status antes do corpo. Conserto: `etapas._esperar_conteudo` relê até as 10 faixas existirem
   (o resumo espera "Características da Cotação").
4. **Tela de módulos na URL da emissão (15/11).** Depois de "Sair da cotação" o portal novo mostra "Selecione um módulo" em
   `Simulador.aspx?Token=...&InFlgViaSimulador=True`, a URL que antes era só da cotação emitida. `identificar_etapa` olhava só
   o caminho e dizia "emitida"; o pedido seguinte falhava em `emitida`. Conserto: confere também `tela_modulos_visivel`.
5. **Acesso ativo (sempre que uma sessão fica aberta).** O portal permite **uma sessão por CPF**. Janela fechada sem sair, ou
   tela reiniciada com robô no meio, deixa a sessão viva por alguns minutos: `já existe um acesso ativo`. É esperado: o robô espera
   60 s e tenta de novo até 10 min. O robô sai do portal sozinho com a fila vazia há 3 min (`tempos.sair_do_portal_min`).
   Medido: da sessão deixada às 17:37 o login só entrou às 17:40.
6. **Tour "Guia de navegação" e cookies "ACEITO".** Cobrem a tela; o robô pula o tour sozinho antes de qualquer ação
   (`telas.pular_tour_sempre`) e aceita cookies.
7. **Nunca recarregar `LoginGeral.aspx` com a sessão viva** (o portal recusa o segundo login). De dentro do cotador, sair pelo
   "Sair da cotação" + modal.
8. **Cotação copiada que trava a coparticipação** (`FiltroTravado`): plano B (sair e refazer), guardado em
   `portal.json:copia_trava_copart`. Raro.
9. **Portal atualizado = causa nº 1 de "parou do nada".** Desde 15/11 o log diz `O PORTAL DA SULAMÉRICA FOI ATUALIZADO` quando o hash
   do build (`webpack-*.js`, `app/layout-*.js`) muda (`etapas.avisar_se_o_portal_mudou`, `portal.json:build_cotador`). Esse aviso só
   existe na SulAmérica; nas outras operadoras uma mudança do site só aparece como falha de seletor.

### 3.2 Bradesco (Portal de Negócios, páginas antigas em iframe)

1. **Cotação SPG demora a abrir (15/11).** `o Cotador de planos SPG não abriu (não achei 'Iniciar Nova Cotação SPG' no menu Ações)`. A página
   levou 62 s para carregar porque a chamada `.../eeem-srv-processos/v1/processos/buscar` do portal ficou **71 s pendente** (o
   `.erro.txt` mostrou). Conserto: `timeout_tela_ms` 180 s no `config.yaml`. Causa de a busca ser lenta: não sei (suposição: muitos
   processos de teste na corretora).
2. **Modal de campanha ("Seguros Friday")** cobre a Home (`div.modal.pn-modal.modal-aviso`, às vezes sem a classe `in`).
   O robô fecha com locator handler + remoção no DOM (`etapas.fechar_avisos`). O Chrome pedindo notificação por cima
   também trava o clique: o perfil do robô bloqueia notificações. Se o clique em "Conferir" estourar 30 s com o modal
   aberto, é ele.
3. **Página do cálculo lenta (10/11):** depois de "Processo N gerado!" o portal chegou a levar mais de 100 s; a espera usa
   `timeout_emissao_ms` e loga "Esperando a página do cálculo (N s)".
4. **Aba sem resposta (10/11):** 4 de 5 pedidos tiveram `TargetClosedError` nos quadros com a aba "aberta". Causa **não confirmada**;
   `_garantir_pagina` sonda e segue em outra aba; o log traz as abas.
5. **`AuthorizationFailed` depois da senha** quando há muitas entradas seguidas (07/11, ~15 em 25 min) ou abrindo a Cotação SPG pelo
   endereço direto. O robô apaga os cookies e entra de novo uma vez. Calibre com poucas execuções.
6. **Login em duas páginas** (CPF/CNPJ da corretora; depois CPF de acesso + senha no nidp). Respostas HTTP 404 de `load_app.js`
   e `load_app.css` no nidp aparecem na rede e **não** impediram o login (suposição: inofensivas).
7. **Alterar Cotação/"Calcular"** (2º plano em diante) nunca foi exercitado no portal real.
8. **`teste_repetir: true`** (`config.yaml`) tira do registro o processo e os cálculos da empresa antes de cada pedido: cada pedido
   gera processo **novo**. Serve para calibrar; em uso real tem que estar `false` (senão a proteção anti-reemissão da Bradesco fica desligada).

### 3.3 Amil (vendasmil; React; todo login pede código por e-mail)

1. **Código de verificação sem campo na tela (15/11).** A faixa dourada do código é única; eventos de outra operadora
   (`conexao`/`login_ok`) a escondiam e a Amil esperava 5 min. Conserto: `NP._conferirFaixaCodigo` (`app/web/js/base.js`): só some quando
   a operadora que pediu deixa de esperar. Teste: `test_codigo_da_amil_nao_some_quando_o_robo_de_outra_operadora_muda_de_estado`.
2. **Botão "Iniciar Sessão"**, não "Entrar" (12/11): `seletores.login_botao_entrar` aceita os dois.
3. **Rótulos não ligados aos inputs**: razão social e nome fantasia pelo `name` (`input[name=razaoSocial]`, `nomeEmpresa`).
4. **Lista de corretor sem `role=option`**: as opções são texto ("<cpf> – NOME"); `telas.escolher_na_lista` cai para o texto. Com o corretor
   **já escolhido** o campo vira um botão "NOME ×" (não um combobox): `seletores.corretor_ja_escolhido`.
5. **Corretor `-` na revisão** quando a cotação é retomada (Em Digitação): o portal perde o vínculo; o robô volta pelo "← Anterior"
   (`etapas._voltar_ao_vinculo`) e escolhe o corretor de novo. A revisão falha fechada se o corretor não bate.
6. **Totais lidos do lugar errado**: o aditivo tem "Valor Total R$ 0,00" próprio; `extracao.ler_totais_da_grade` corta em "Aditivos do Plano".
7. **Mapa não grava a tela do Vínculo** (campo "código do corretor" parecia campo de código): `telas.ajustar_mapa` troca a regra só na Amil.
8. **Duração da sessão**: o log `A sessão anterior durou de X a Y min` mede entre login e a última vez que o robô viu a sessão. Valores como
   "0 a 4106 min" acontecem quando o robô ficou dias parado (não são duração real).

---

## 4. Como diagnosticar e consertar uma tela travada (passo a passo)

1. **Pedir ao usuário**: o print da tela "Cotações deste pedido" (mostra etapa e mensagem), o horário aproximado, quais operadoras
   rodavam juntas e se ele mexeu no navegador/tela. Se for reiniciar a tela, perguntar se há robô rodando.
2. **Conferir se a tela roda o código novo**: `GET /api/estado` e o rodapé; a tela só carrega código novo ao reiniciar o servidor
   (o JS vem de disco). Falhou numa rodada que o usuário rodou **antes** do meu commit? Compare a hora do log com `git log`.
3. **Ler** o último `execucao_*.log` da operadora; achar `falha na etapa`; depois o `NN_ERRO_<etapa>.png`, `.aria.txt` e `.erro.txt`.
4. **Comparar** com um mapa bom da mesma etapa (outra pasta de `mapa/`) e com `portal.json:build_cotador` (SulAmérica): o portal
   mudou? (`grep -o 'webpack-[0-9a-f]*.js'` nos `.html` de duas datas.)
5. **Classificar**: (a) seletor/texto mudou → corrigir `seletores.py`/`extracao.py`; (b) tela lenta/não renderiza → espera ou
   recuperação; (c) estado/sessão (acesso ativo, sessão caída) → nada a corrigir, esperar; (d) dado do pedido → pedir ao usuário.
6. **Reproduzir sem emitir**: no **simulador** (`python -m operadoras.<id>.simulador`; as portas 8765/8766 SulAmérica, 8775/8776
   Bradesco, 8785 Amil) ou em **ensaio** real (pela tela, "Ensaiar sem emitir", ou `python main.py --operadora <id> --ensaio
   --mapear --linha N`; a tela também aceita `POST /api/trabalhos` com `"modo": "ensaio"` e os `itens` de um trabalho anterior,
   lidos de `tela.db:trabalhos.itens_json`). **Nunca** `"modo": "emitir"` por conta própria.
7. **Escrever o teste primeiro** quando der: acrescente ao simulador a situação real (foi assim com `travar_troca_cuidado` e com o card
   "Total estimado") e confirme que o teste **falha sem o conserto e passa com ele** (`git stash` do arquivo do conserto).
8. **Consertar o mínimo**, só na pasta da operadora (regra 9). Falha fechada: se não tem certeza do que está na tela, parar com erro.
9. **Validar**: testes de unidade (rápidos), os testes de robô x simulador relacionados (`-k`), um ensaio real **solo** da operadora, e só
   então, com o usuário pedindo, a rodada real. Para tela travada, **rode também com as três operadoras juntas** — era o único
   jeito de reproduzir.
10. **Não quebrar o que funciona**: nunca reiniciar a tela com robô rodando (`/api/estado` → `atual: null`); nunca mexer em arquivo
    congelado sem pedido; commit pequeno com mensagem que diz o que o portal fez; tag nova só quando o Tiago aprovar.

---

## 5. Regras de segurança

- **Nunca emitir em teste.** Para testar no portal real use sempre o ensaio. Emissão real só quando o usuário pede, naquela conversa.
- **O que o ensaio cria no portal real**:
  - SulAmérica: nada (vai até o Resumo e sai da cotação).
  - Bradesco: nada oficial (vai até o Resultado, lê o preço do card, para antes de "Iniciar cotação"). Com `teste_repetir`, mexe só no registro local.
  - **Amil: cria de verdade a Oportunidade (OPP) e uma Cotação "Em Digitação" por plano** (vencem em 1 dia); para em "Revisar Cotação", sem "Concluir".
    É o único jeito de ver o preço. Cada ensaio da Amil deixa rascunhos no portal.
- **Pontos sem volta que o robô nunca clica sozinho**: "INICIAR CONTRATAÇÃO" (SulAmérica); "Finalizar Cálculo" (Bradesco); "Criar Proposta",
  "Enviar por E-mail", "+ Incluir Plano Médico" (Amil, sem seletor no código, e o simulador conta os cliques: os testes exigem 0). "Gerar processo" e
  "Calcular" (Bradesco), "Concluir Cotação" (Amil) e o Continuar do Resumo (SulAmérica) só rodam quando o corretor clica em Gerar.
- **Credenciais só no cofre do Windows** (`keyring`, serviço `NewportCotacoes/<operadora>`, usuário do Windows). Quem guarda é o corretor, na engrenagem
  do robô. O agente **nunca** lê, digita, grava nem registra credenciais; nunca chama `Cofre.ler()` nem `POST /api/credenciais` com valores reais.
  A API só devolve `{guardadas, email_mascarado, quando, recusadas}`.
- **Mapa de tela de login/código**: só o `01_login.*`, tirado antes de digitar, com os campos vazios. Depois de digitar nada da tela de login vira mapa;
  a tela de código nunca. Valores de login que o robô leu saem como `•••` nos mapas e no log (`FiltroSegredos`).
- **Nunca ligar trace do Playwright** nem `DEBUG=pw:api` (gravariam o que é digitado).
- **Dados pessoais**: `saida/`, `saida_simulador/` e `cotacoes.xlsx` têm CNPJ e razão social de clientes, PDFs, o `tela.db` (`ultimo_pedido_json` guarda o pedido
  inteiro) e a sessão do navegador (cookies, em `saida/<id>/perfil_navegador`). Estão no `.gitignore`; não copie esses dados para outros arquivos, commits,
  documentos ou mensagens; não leia PDF de cliente sem necessidade. Em exemplos use o CNPJ fictício dos testes.
- **Um robô por pasta de saída** (trava); uma sessão por CPF no portal da SulAmérica.

---

## 6. Como testar

### 6.1 O que existe

| Grupo | Arquivos | O que cobre |
|---|---|---|
| Núcleo + tela, operadora falsa | `tests/nucleo/test_nucleo.py`, `test_nucleo_operadora_falsa.py` | texto/CNPJ, mapa de erro, requisições pendentes, API de reemissão, registro, trabalhador |
| SulAmérica | `tests/sulamerica/test_sulamerica_unidades.py` (sem navegador), `..._simulador.py` (robô x simulador), `..._tela.py` (tela x simulador) | |
| Bradesco | `tests/bradesco/test_bradesco_unidades.py`, `..._simulador.py`, `..._tela.py` | |
| Amil | `tests/amil/test_amil_unidades.py`, `..._simulador.py`, `..._tela.py` | inclui a faixa do código |

Simuladores (imitam o portal, login falso, cofre na memória): `python -m operadoras.sulamerica.simulador` (8765/8766), `...bradesco.simulador` (8775/8776),
`...amil.simulador` (8785, pede o código de 8 dígitos). Os testes sobem os deles sozinhos. A tela com os simuladores: `python -m app --config config_simulador.yaml`.

### 6.2 Quanto demoram (medido em 15/11, nesta máquina)

| Execução | Testes | Tempo |
|---|---|---|
| `tests/nucleo` | 10 | ~4 s |
| `tests/sulamerica/test_sulamerica_unidades.py` | 35 | ~4 s |
| robô x simulador SulAmérica, 3 testes (`-k "ensaio or travada or emite_dois"`) | 3 | ~3 min |
| robô x simulador SulAmérica, 8 testes | 8 | ~8 min |
| Bradesco + Amil (simulador + unidades) | 79 | ~13 min |
| núcleo + SulAmérica inteira | 100 | 29 min sozinho; 53 min quando rodou em paralelo com outro grupo |
| **suíte completa** (`python -m pytest`) | 180 | 43 min |

Não rode grupos em paralelo com robôs reais: a carga atrapalha os dois lados.

### 6.3 Falha intermitente conhecida

- Na suíte completa de 15/11, `tests/sulamerica/test_sulamerica_simulador.py::test_senha_errada_para_na_primeira_e_nao_tenta_de_novo` falhou uma vez com
  `TargetClosedError` ("Login: não consegui fazer o passo 'caixa Ok, entendi!'") e **passou** rodando sozinho (39 s) e nas rodadas seguintes. Foi tratado como
  intermitente (navegador de teste fechado no meio do login); a causa não foi investigada. **Fato.**
- O Tiago relatou que o teste do Bradesco "parar entre telas" falhou uma vez de forma intermitente (provavelmente `test_parar_so_entre_telas_e_nunca_durante_o_calculo`,
  `tests/bradesco/test_bradesco_simulador.py:174`). **Eu não vi essa falha; está registrada aqui só pelo que o Tiago disse.** Nas execuções de 15/11 os testes do Bradesco passaram (79).

### 6.4 O que rodar antes de commitar

- Mudou só uma operadora: unidades dela + os testes de robô x simulador relacionados (`-k`) + (se houver) o ensaio real solo.
- Mudou `nucleo/`, `app/` ou `operadoras/base.py`: **todos** os testes de todas as operadoras (regra 10) — ou, se o Tiago dispensar explicitamente a suíte completa (como em 15/11),
  núcleo + a operadora afetada + uma amostra das outras, e **diga isso no commit**.
- Mudou comportamento de portal: espelhe no simulador (regra 8) e escreva o teste que reproduz a falha.
- Mudou só documentação: nada a rodar.

---

## 7. O que o código não diz

- **Parece erro e não é**:
  - `Não achei o botão 'Voltar para a home' na tela da cotação emitida` / `... 'Nova cotação' ...` (WARNING) logo depois de um **ensaio** da SulAmérica: o ensaio sai pelo
    "Sair da cotação", o fluxo seguinte tenta os botões de depois da emissão. (Isso virou erro de verdade só no bug 3.1-4.)
  - `O texto do PDF não cita COT-XXXXXXX; confira o arquivo` (Amil, WARNING): aparece em **todas** as emissões. O PDF **está certo** (conferi um: 8 páginas, número da
    cotação, plano e valor presentes; o número aparece sem "COT-"). A checagem olha só as 3 primeiras páginas — o número fica depois delas (suposição). Compara só os dígitos desde 15/11 e o aviso continua; não corrigi.
  - `Não consegui sair do portal (fila vazia há 3 min). Fechei a janela; a sessão do portal expira sozinha` (Amil): o logout nem sempre funciona; a sessão expira.
  - `mapa não gravado: tela de login`: normal (LGPD); só é gravado o `01_login.*`.
  - `A sessão anterior durou de 0 a N min`: ver 3.3-8.
  - Códigos de saída 127 de tarefas em segundo plano **no shell do Claude** não são do robô.
  - Falha 404 de `load_app.js/css` no login da Bradesco: não impediu login (suposição).
  - `Saí do portal (fila vazia há 3 min)`: o robô sai e fecha a janela sozinho; o próximo pedido entra de novo (na Amil, pede código novo).
- **Manhas**:
  - SulAmérica: o ensaio é rápido (~26 s); duas emissões (com e sem copart) ~85 s. O robô copia a cotação para a 2ª versão; o PDF vem como
    `PropostaComercialCuidado360_<protocolo>-1.pdf` e é renomeado.
  - SulAmérica: IOF é calculado **por vida e arredondado**, depois somado (58,16, não 58,15 sobre o total).
  - Bradesco: o cálculo e o "Imprimir" saem em iframes antigos; o PDF vem da janela "Imprimir" (`page.pdf`, só com a janela do portal escondida).
  - Amil: o valor por vida **muda com o total de vidas**; o robô só lê a grade depois de preencher todas as faixas. Cada login pede código (15 min de validade) — **a Amil nunca roda sozinha**.
  - Janelas do portal ficam escondidas (headless); `geral.modo_visual: true` mostra a janela (só para calibrar; atenção: com ela visível a tela segura a trava).
  - O JS da tela é servido sem cache e a página recarrega sozinha quando o servidor reinicia; se o corretor ficar com uma aba aberta de antes de uma mudança, o botão pode não registrar
    (aconteceu em 15/11): pedir F5.
  - Reiniciar a tela mata robôs e deixa sessões abertas no portal (ver 3.1-5).
- **Mudanças recentes nos sites**: SulAmérica atualizada entre 06/11 e 15/11 (3.1). Bradesco: campanha "Seguros Friday 2026" de 3 a 30/11 aparece como modal. Amil: "Iniciar Sessão" (12/11).
- **Horários em que falham**: não identifiquei padrão de horário. As falhas da SulAmérica de 15/11 foram à tarde/noite de um **domingo** (suposição: carga do portal diferente; **não verificado**).
- **A SulAmérica travou em todas as rodadas com a Amil** (8 de 8) e quase nunca sem ela (1 espera de 60 s em 6 rodadas); **causa desconhecida**, só correlação.

---

## 8. Primeiro atendimento (uma página)

**O que pedir ao usuário quando o robô travar:**
1. O print da tela "Cotações deste pedido" (etapa e mensagem).
2. Que operadoras rodaram **juntas** e a hora aproximada.
3. Se alguém mexeu no navegador, fechou janela ou reiniciou a tela naquele momento.
4. Se for o caso, o `NN_ERRO_<etapa>.erro.txt` (e o `.png`) da execução (em `saida/<id>/mapa/<data>/`).

**O que o agente faz primeiro (nesta ordem):**
1. `GET http://127.0.0.1:8600/api/estado` (ou olhar a tela): há robô rodando? Se sim, **não reinicie nada**.
2. Ler o último `saida/<id>/logs/execucao_*.log` (UTF-8) e achar `falha na etapa`.
3. Ler `NN_ERRO_<etapa>.erro.txt` e `.aria.txt`; comparar com um mapa bom da mesma etapa.
4. Procurar a mensagem na tabela 2.2 e a falha na seção 3. Se for "acesso ativo" ou sessão: esperar, não é defeito.
5. SulAmérica: o log avisou "PORTAL ATUALIZADO"? Se sim, comece pelo seletor/texto que mudou.
6. Reproduzir no simulador ou com **ensaio solo** antes de consertar. **Nunca emitir**; nunca editar `estado.json`; nunca mexer em pasta de operadora congelada sem pedido do Tiago.
7. Só reiniciar a tela com `atual: null`. Subir a tela como processo independente (no Windows: `Start-Process` ou o `.bat`), não presa ao shell.

---

## 9. O que eu não sei ou nunca confirmei

- **Por que a SulAmérica trava com os robôs juntos** (8 de 8 rodadas com a Amil; só 1 espera em 6 sem ela). Não achei a causa; só a recuperação (recarregar + retomar).
- **Se a recuperação funciona sempre**: foi provada em 4 travadas reais seguidas (15/11) e no simulador; não sei a taxa em uso contínuo.
- **Quando exatamente** o portal da SulAmérica foi atualizado: só sei que foi entre 06/11 (última execução antes) e 15/11.
- **Por que a busca de processos da Bradesco levou 71 s** e por que a aba "não responde" em 10/11.
- **Se o teste do Bradesco "parar entre telas" é intermitente** (só o relato do Tiago; não vi).
- **Por que o aviso "O texto do PDF não cita COT-..." da Amil persiste** depois do ajuste (a causa provável é a posição do número no PDF; não verifiquei).
- **O que ainda não foi exercitado no portal real**: Amil com plano sem aditivo/dental, "pedir de novo" na Amil e Parar no meio; Bradesco com 2º plano (Alterar Cotação → Calcular); Parar no meio de uma emissão real em qualquer operadora.
- **Como `C:\np\rpa` se liga a este projeto**: vi um processo dele (`python -m app --config config_simulador.yaml`, portas 8600 e dos simuladores) em 17/11, mas não li o código dele nem sei se é cópia, fork ou integração. Não sei se o caminho de saída, o cofre e as portas lá são os mesmos.
- **Comportamento com dois corretores na mesma máquina**: pela leitura do código (trava por pasta, cofre por usuário do Windows) não suporta; não foi testado.
- **Horários/dias de pior desempenho dos portais**: nunca medi.
- **Se o simulador da Amil e o da Bradesco refletem a versão atual dos portais reais** nos detalhes que mudaram depois de 12/11 e 10/11 (só o da SulAmérica foi atualizado em 15/11).
