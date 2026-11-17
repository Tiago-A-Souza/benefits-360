**Esta pasta é a única versão do projeto. Todas as mudanças são feitas aqui, por você (Claude Code), editando os arquivos existentes. Nunca peça para substituir o projeto inteiro. Depois de cada mudança: rode python -m pytest e faça um commit com uma mensagem clara.**

# Newport Cotações: robô de cotação com tela do corretor

Uma **tela local** (servidor Starlette em 127.0.0.1 + páginas em JavaScript puro) onde o corretor da
Newport pede cotações e baixa os PDFs, e um **robô** em Python + Playwright que faz no portal de cada
operadora o trabalho repetitivo. A primeira operadora é a **SulAmérica, Cotação PME (3 a 29 vidas)**:
o robô preenche o assistente, emite **uma cotação por plano**, baixa o PDF e salva com o nome que o
corretor usa. O fluxo foi levantado de um vídeo gravado por um corretor; os seletores ainda precisam
ser **calibrados no portal real** (ver "Calibragem"). O guia de negócio é o `PLAYBOOK.md`.

## Regras que você (Claude) deve seguir neste projeto

1. **Nunca emitir cotação real sem o usuário pedir nesta conversa.** Para testar no portal, use sempre
   o ensaio (tela: "Ensaiar sem emitir"; linha de comando: `--ensaio`), que vai até o resumo e para
   antes de emitir. Nunca passe `--confirmar` por conta própria e nunca chame `POST /api/trabalhos`
   (ou `/repetir`) com `"modo": "emitir"` sem o usuário pedir. Nunca mande `"reemitir"` (é o botão do
   corretor, ver regra 3).
2. **Login automático, credenciais só no cofre do Windows.** O corretor guarda CPF, e-mail e senha
   uma vez na engrenagem do robô (tela 1, Login); ficam no Gerenciador de Credenciais do Windows
   (`keyring`, serviço `NewportCotacoes/<operadora>`, usuário do Windows) e o robô entra sozinho, só
   quando o portal pede. Você (Claude) nunca pede, lê, digita, grava ou registra credenciais: quem
   guarda é o corretor, na tela; você nunca chama `Cofre.ler()`/`keyring.get_password` nem
   `POST /api/credenciais` com valores reais, e nunca abre mapa de tela de login ou de código, exceto o
   `01_login.*` (tirado antes de digitar, com os campos vazios: é o que calibra o login). As
   credenciais nunca vão para `config_tela.json`, `config.yaml`, `tela.db`, `estado.json`,
   `resultados.xlsx`, logs, eventos SSE, mapa, mensagens de erro, URL ou git; a API de credenciais é só de
   escrita (GET devolve só `{guardadas, email_mascarado, quando, recusadas}`). Senha recusada: o robô para
   na primeira e não tenta de novo até o corretor guardar a senha outra vez (evita bloquear a conta).
   Captcha: o robô para e avisa, nunca tenta resolver. Código de verificação: a tela pede ao corretor.
   Nunca ligue trace do Playwright nem `DEBUG=pw:api` (gravariam o que é digitado). Testes usam o
   cofre de memória (`teste: cofre: memoria`) com o login FALSO do simulador.
3. **Nunca reemitir sozinho.** `saida/<operadora>/estado.json` é o registro que impede emissão duplicada.
   A chave é a cotação real: CNPJ + parâmetros que mudam o preço + plano e acomodação como o portal
   mostra (o id e a grafia do pedido não entram). Não edite à mão. Item travado só sai por
   "Não saiu: liberar" na tela ou `python main.py --liberar "<chave>"`, e só depois que o usuário
   conferir no portal (em "Cotações emitidas") que não há cotação emitida. **Única exceção (decisão do
   usuário, 05/11, para testes e demonstrações):** no aviso "Esta cotação já foi emitida" da Nova
   cotação, o corretor clica em "Emitir de novo mesmo assim" e confirma. O pedido leva `reemitir` com os
   protocolos que ele viu; o servidor só aceita protocolos concluídos (`pdf_ok`) daqueles pedidos e não
   guarda isso nos itens do trabalho ("Tentar de novo" nunca reemite); o robô emite cada um uma vez e o
   item antigo vai para `reemitidos` na mesma gravação do `emitindo` (`Estado.registrar(...,
   substituir_protocolo=)`). Emissão incerta (`emitindo`, `emitida`, `pdf_manual`) nunca é reemitida.
4. O robô **nunca** clica em "INICIAR CONTRATAÇÃO" (SulAmérica) nem em "Finalizar Cálculo" ou em qualquer coisa que
   envie proposta ou contrato (Bradesco). Não crie código que clique neles. Na Bradesco, "Gerar processo" (cria o
   Número do Processo) e o "Calcular" do Alterar Cotação são os pontos sem volta: só com o usuário pedindo (regra 1).
5. **Parar só em ponto seguro.** `nucleo.navegador.Parado` só pode ser levantada entre telas; nunca
   entre o registro "emitindo" (logo antes do clique de emitir) e a leitura do protocolo.
6. `saida/`, `saida_simulador/` e `cotacoes.xlsx` têm dados de clientes, o histórico da tela e a
   sessão do navegador. Não leia PDFs de clientes sem necessidade, não copie esses dados para outros
   arquivos e não versione.
7. A tela só escuta `127.0.0.1` e todo pedido que muda algo precisa do cabeçalho `X-Newport-Tela: 1`
   e da mesma origem (`SoDaPropriaTela` em `app/servidor.py`). Não afrouxe isso: é o que impede um
   site aberto no navegador de disparar emissões. Downloads só servem arquivos de dentro de `saida/`.
8. Ao mudar comportamento, rode `python -m pytest` (núcleo + robô x simulador + tela x simulador). Se
   o portal real se comportar diferente do simulador, ajuste o simulador para refletir o real.
9. **Correção de portal = só em `operadoras/<operadora>/`.** Cada operadora é um módulo separado: seletores,
   textos do portal, telas, login, simulador e regras do produto ficam na pasta dela. Uma mudança no portal
   de uma operadora nunca mexe em `nucleo/`, `app/`, `operadoras/base.py` nem na pasta de outra operadora.
   Nada de texto de portal no núcleo nem na tela: o que for útil para todas vira parte da interface
   (`operadoras/base.py`), com cada operadora implementando.
10. **Mudança em `nucleo/`, `app/` ou `operadoras/base.py` exige os testes de TODAS as operadoras passando**
    (`python -m pytest`: `tests/nucleo/` e `tests/<operadora>/` de cada uma). Os testes do núcleo usam só a
    operadora falsa (`tests/nucleo/operadora_falsa.py`), nunca uma de verdade.
11. **`operadoras/sulamerica/`, `operadoras/bradesco/` e `operadoras/amil/` estão CONGELADAS** (versões aprovadas pelo
    Tiago; tags `sulamerica-v1-aprovado` 06/11 e `sulamerica-v2-aprovado` 15/11, `bradesco-v1-aprovado` 10/11 e
    `bradesco-v2-aprovado` 15/11, `amil-v1-aprovado` 15/11; vale a tag mais nova). Não mude nada nessas pastas nem em
    `tests/<operadora>/` sem pedido explícito do Tiago para aquela operadora. Trabalho no núcleo (`nucleo/`, `app/`,
    `operadoras/base.py`) ou em outra operadora não pode exigir mudança nas congeladas: se exigir (ex.: um método novo
    na interface que elas teriam de implementar, um teste delas que quebraria), **pare e pergunte antes**. O que for
    novo na interface entra com um padrão em `operadoras/base.py` que deixa as congeladas como estão. Para ver o que
    mudou depois da aprovação: `git diff <tag> -- operadoras/<id>`. **Portal que mudou** (o log da SulAmérica avisa
    "O PORTAL DA SULAMÉRICA FOI ATUALIZADO") é o caso típico de pedido do Tiago para mexer: corrija só a pasta daquela
    operadora, espelhe a mudança no simulador, rode os testes dela e crie a tag nova (`<id>-vN-aprovado`).

## Como rodar (Windows, PowerShell, na pasta do projeto)

```
.\.venv\Scripts\Activate.ps1
python -m app                                         # a tela (http://127.0.0.1:8600)
python -m app --config config_simulador.yaml          # a tela ligada ao simulador (porta 8601)
python -m operadoras.sulamerica.simulador             # o simulador (portas 8765 e 8766)
python main.py --validar                              # só confere a planilha
python main.py --ensaio --mapear --linha 2            # calibragem: uma linha, sem emitir
python main.py                                        # emissão real (pede EMITIR)
python main.py --pendencias | --registro | --liberar "<chave>"
python -m pytest                                      # todos os testes, de todas as operadoras (~25 min)
python -m pytest tests/nucleo                         # só o núcleo e a tela, com a operadora falsa (rápidos)
python -m pytest tests/sulamerica                     # só a SulAmérica (unidades + robô x simulador + tela)
python -m pytest tests/sulamerica/test_sulamerica_unidades.py   # SulAmérica sem navegador (rápidos)
python -m pytest tests/bradesco                       # só a Bradesco (unidades + robô x simulador + tela)
python -m pytest tests/amil                           # só a Amil (unidades + robô x simulador + tela)
python -m operadoras.amil.simulador                   # o simulador da Amil (porta 8785; pede o código de 8 dígitos)
python main.py --operadora amil --ensaio --mapear --linha 2   # calibragem da Amil (o ensaio JÁ CRIA a oportunidade)
python -m operadoras.bradesco.simulador               # o simulador da Bradesco (portas 8775 e 8776)
python main.py --operadora bradesco --ensaio --mapear --linha 2   # calibragem da Bradesco, sem gerar nada
```

Os `.bat` da raiz fazem o mesmo para o corretor (`instalar.bat`, `Abrir Newport Cotacoes.bat`,
`Treinar no simulador.bat`). A tela e a linha de comando não rodam juntas na mesma pasta de saída:
a tela segura a trava (`nucleo/trava.py`) enquanto a janela da operadora estiver aberta.

Cada cotação leva por volta de 30 s (e, se o portal pedir um código de verificação, o robô espera o
corretor digitar na tela por até 5 minutos). Isso pode passar do tempo limite de um comando: rode em
segundo plano e acompanhe `saida/sulamerica/logs/`, ou peça ao usuário para rodar no terminal dele e
depois leia o log. A janela do portal fica escondida (headless); para calibrar, ligue "Mostrar a janela
do portal (para calibrar)" em Robôs (`geral.modo_visual`). Se o portal estranhar o headless, use
`geral.janela_escondida: fora_da_tela` no `config.yaml`.

## Mapa do código

| Arquivo | O que faz |
| - | - |
| `app/servidor.py` | rotas da tela e da API, validação dos pedidos, downloads (PDF e .zip), ajustes, pendências |
| `app/trabalhador.py` | os robôs: um por operadora (`_RoboOperadora`: thread, fila, janela do portal, trava, log `cotacao.<operadora>`, folga de saída); o `Trabalhador` coordena, divide o pedido com várias operadoras e só conclui quando todas terminam; avisos ao vivo, Parar |
| `app/banco.py` | histórico da tela em SQLite (`saida/tela.db`): pedidos, cotações, registro detalhado, planos vistos, empresas |
| `app/eventos.py` | eventos ao vivo para a tela (SSE em `/api/eventos`) |
| `app/web/` | `index.html`, `css/estilo.css`, `js/base.js` (API, peças comuns), `js/app.js` (rotas, aviso de mudança não salva), `js/telas/*.js` (`robos.js` e `robo.js` são a engrenagem), `fontes/` (Poppins local) |
| `main.py` | linha de comando, confirmação de emissão, laço dos pedidos |
| `nucleo/` | o que vale para qualquer operadora: `modelo` (faixas, resultado), `estado` (anti-reemissão), `saidas` (xlsx, nomes de PDF), `navegador` (abrir escondido, esperas, `Mapeador`, `ErroFluxo`, `ErroLogin`, `Parado`), `credenciais` (login no cofre do Windows, `ocultar`, filtro do log), `registro` (config), `configuracao` (campos da engrenagem: ler, validar, gravar), `trava`, `retencao`, `texto` |
| `operadoras/base.py` | a interface que toda operadora implementa (com os padrões de quem não declara) |
| `operadoras/__init__.py` | registro das operadoras (`_REGISTRO`); cada uma carrega à parte: se falhar, fica "indisponível" e as outras seguem |
| `operadoras/sulamerica/fluxo.py` | máquina de estados: identifica a tela pela URL e chama a etapa; Parar; recuperação de PDF |
| `operadoras/sulamerica/etapas.py` | uma função por tela; confere o que já está preenchido (modo cópia) antes de preencher |
| `operadoras/sulamerica/seletores.py` | **todos** os seletores, marcados VALIDAR. É o arquivo da calibragem |
| `operadoras/sulamerica/extracao.py` | leitura de texto das telas (cards, tabela por faixa, resumo, protocolo). Funções puras |
| `operadoras/sulamerica/cartao.py` | o card de um plano na tela Planos (`PlanoNaTela`) |
| `operadoras/sulamerica/planilha.py` | validação dos pedidos (tela e planilha) e a planilha modelo |
| `operadoras/sulamerica/login.py` | login automático com o login do cofre: recusa (para na 1ª), código de verificação, captcha, troca de senha |
| `operadoras/sulamerica/simulador/` | imitação local do cotador (mesmas URLs e textos do vídeo) |
| `tests/nucleo/` | núcleo e tela com a operadora falsa mínima (`operadora_falsa.py`); nenhuma operadora de verdade |
| `tests/sulamerica/` | `test_sulamerica_unidades.py` (sem navegador), `test_sulamerica_simulador.py` (robô x simulador), `test_sulamerica_tela.py` (tela x simulador) |
| `operadoras/bradesco/` | Bradesco, Cotação SPG: `fluxo.py` (um processo por empresa), `etapas.py` (uma função por tela, Gerar processo, cálculo, Imprimir, Alterar Cotação), `login.py` (CPF/CNPJ -> senha), `seletores.py` (todos VALIDAR), `extracao.py`, `telas.py` (quadro/iframe das páginas antigas, botões de escolha, listas), `pedido.py` (assinaturas do processo e do cálculo), `planilha.py`, `cartao.py`, `simulador/` |
| `tests/bradesco/` | `test_bradesco_unidades.py`, `test_bradesco_simulador.py`, `test_bradesco_tela.py` |
| `operadoras/amil/` | Amil (vendasmil), Cotação PME: `fluxo.py` (uma oportunidade por empresa, uma cotação por plano), `etapas.py` (uma função por tela; Concluir Cotação; recuperar o PDF), `login.py` (usuário/senha + código de 8 dígitos pedido na tela; mede a sessão), `seletores.py` (todos VALIDAR), `extracao.py` (valores e conferências), `telas.py`, `pedido.py`, `planilha.py`, `simulador/` |
| `tests/amil/` | `test_amil_unidades.py`, `test_amil_simulador.py`, `test_amil_tela.py` |

## API da tela (resumo)

`GET /api/operadoras` (formulário de cada operadora: campos com `multiplica`, planos, etapas, `versoes`, `textos`) ·
`GET /api/estado` (também `operadoras_indisponiveis`) · `POST /api/validar`
(devolve também `ja_emitidas`: plano, protocolo, quando) ·
`POST /api/trabalhos` `{modo: ensaio|emitir, confirmado, itens: [{operadora, pedidos: [...]}], reemitir?: [protocolos]}` ·
`GET /api/trabalhos/{id}` · `POST /api/trabalhos/{id}/parar` · `POST /api/trabalhos/{id}/repetir` ·
`POST /api/conectar/{op}` · `GET /api/cotacoes?busca&status&limite` · `GET /api/cotacoes/{id}/pdf` ·
`GET /api/pdfs.zip?trabalho=|ids=` · `GET /api/pendencias` · `POST /api/liberar` · `POST /api/concluir` ·
`GET|PUT|DELETE /api/robos/{op}` (configuração do robô: esquema com valor atual e padrão da Newport;
grava só os campos declarados; DELETE volta aos padrões) · `GET|PUT /api/geral` · `POST /api/importar` ·
`GET /api/modelo/{op}` · `GET /api/eventos` (SSE).
`POST /api/sair/{op}` ("Sair do portal agora": 409 com o robô trabalhando) ·
`GET|POST|DELETE /api/credenciais/{op}` (login do portal no cofre do Windows, com os campos que a operadora
declara; POST só grava, GET só diz `{guardadas, quando, recusadas}` e os campos mascarados, ex.:
`email_mascarado`; a senha nunca volta) · `POST /api/codigo/{op}` (código de
verificação para o robô digitar) · `POST /api/conectar/{op}` é o "Testar login". Sem login guardado (ou
recusado), `POST /api/trabalhos` e `/api/conectar` respondem 409 com `motivo` e o robô nem abre o portal.
Eventos: `trabalho`, `conexao` (inclui `saindo`), `login_entrando`, `login_ok`, `codigo_necessario`, `login_problema`,
`etapa`, `pedido`, `cotacao`, `log`, `catalogo`, `saiu_do_portal`.

## Como adicionar uma operadora (roteiro: copiar a estrutura da SulAmérica)

0. **Copiar a estrutura** de `operadoras/sulamerica/` para `operadoras/<id>/`: `__init__.py` (a classe),
   `seletores.py`, `etapas.py`, `fluxo.py`, `extracao.py`, `login.py`, `telas.py`, `pedido.py`, `planilha.py`,
   `cartao.py` e `simulador/`. Troque tudo o que é do portal; nada da pasta nova importa `operadoras.sulamerica`
   (nem o contrário). Testes em `tests/<id>/` (`test_<id>_unidades.py`, `test_<id>_simulador.py`,
   `test_<id>_tela.py`), com nomes de arquivo que não se repetem entre pastas.
1. **Mapear o portal:** peça ao usuário um vídeo de um corretor fazendo a cotação do login ao PDF.
   Monte a tabela de telas (URL, o que fazer, sinal de tela pronta), como a da SulAmérica abaixo.
2. **Criar `operadoras/<id>/`** com uma classe que herda de `Operadora` (`operadoras/base.py`):
   - identidade: `id`, `nome`, `produto`, `cor`, `min_vidas`, `max_vidas`, `faixas_idade_exata`,
     `etapas` (ids e nomes curtos, na ordem do portal; a tela numera e acende cada uma);
   - `PADRAO_CONFIG`: padrões da seção `operadoras.<id>` do `config.yaml`;
   - `campos(cfg)`: opções do formulário. Cada campo: `chave`, `rotulo`, `tipo`
     (`sim_nao` | `escolha` | `texto` | `sugestoes`), `opcoes`, `padrao`, `ajuda`, `titulo` (para
     `sim_nao`) e `visivel_se` (`{"outra_chave": "valor"}`);
   - `configuracao(cfg)`: o robô tela por tela, com o que o corretor configura na engrenagem
     (ver "Configuração do robô pelo corretor" abaixo);
   - `planos_conhecidos()`: planos que a tela oferece antes de o robô ler o portal;
   - `montar_pedido(dados, cfg, linha)`: valida o pedido (o mesmo dicionário vem da tela e da
     planilha); erro = `ValueError` com `.problemas` (lista de frases para o corretor);
   - `qtd_cotacoes`, `ler_registros`, `ler_planilha`, `criar_modelo`;
   - `nova_sessao(..., avisar, parar, pedir_codigo)`, `login`, `conectado`, `recuperar_pdfs`, `processar`;
   - `campos_login()`: os campos do login do portal (`chave`, `rotulo`, `tipo` cpf | email | texto | senha,
     `mascara`, `artigo`); o cofre (`NewportCotacoes/<id>`) valida, guarda e mascara só esses. Na tela
     "login" de `configuracao()`, um campo `{"tipo": "credenciais", "campos": self.campos_login()}` (sem chave):
     a engrenagem desenha esses campos (nunca na configuração). `mensagens_login`: as frases de login só dela;
   - `textos_tela()`: os textos da operadora na tela (Ajuda, Nova cotação, Andamento, avisos), no lugar dos
     genéricos; `rotulos_versao()` e `nome_versao_planilha` se houver mais de uma cotação por plano (ex.: com
     e sem coparticipação); `versoes(pedido)` para o aviso de "já emitida"; `exemplo_pdf` no campo do nome do PDF;
   - `treino()` (simulador de treino e login falso) e `sair(sessao)` (logout no portal), se houver;
3. **Contrato do robô** (o que a tela espera de `processar`):
   - chamar `avisar("etapa", etapa=<id>, pedido=..., plano="Nome | Acomodação", indice=i, total=n)` a
     cada tela, e `avisar("login_entrando")` / `avisar("login_ok")` no login;
   - entrar no portal sozinho com `nucleo.credenciais.cofre(cfg, id).ler()` só quando o portal pedir;
     qualquer falha vira `nucleo.navegador.ErroLogin(frase fixa, motivo)` com `from None` (nunca o valor
     digitado); `Mapeador.registrar(..., login_vazio=True)` só antes de digitar, `mapa.login_digitado = True`
     antes do primeiro `fill`;
   - registrar cada plano com `sessao.resultados.plano(ResultadoPlano(...))`; status `OK`,
     `ENSAIO_OK`, `ERRO`, `VERIFICAR`, `PULADO` ou `PARADO`; com `pdf_arquivo` (dentro de
     `saida/<id>/pdfs/`), `pdf_nome` (o nome que o corretor recebe) e `valores_por_vida`;
   - usar `nucleo.estado.Estado` como a SulAmérica: procurar antes, gravar `emitindo` (com fsync)
     logo antes do clique de emitir, `emitida` com o protocolo, `pdf_ok` com o PDF;
   - levantar `Parado` quando `parar()` for verdadeiro, só entre telas e nunca durante a emissão.
4. **Registrar** em `operadoras/__init__.py` (`_REGISTRO`: id, nome, módulo, classe) e criar `operadoras: <id>:`
   no `config.yaml`. Cada operadora tem a sua pasta `saida/<id>/` (registro anti-reemissão, PDFs, logs, mapa,
   perfil do navegador), o seu serviço no cofre e a sua seção no `config.yaml`.
5. **Simulador e testes** em `operadoras/<id>/simulador/` e `tests/<id>/`, como os da SulAmérica. Rode
   `python -m pytest` inteiro (regra 10): o núcleo e as outras operadoras têm que continuar passando.
6. **Calibrar** no portal real com ensaio + mapa (seção abaixo), sem emitir.

A tela, o histórico, os downloads, as pendências e os ajustes passam a funcionar para a operadora nova
sem mudança em `app/`.

## Fluxo observado no vídeo (SulAmérica, referência para calibrar)

| # | Tela / URL | O que o robô faz | Sinal de tela pronta |
| - | - | - | - |
| 1 | `os11.../SaudeCotador/LoginGeral.aspx` | aceita cookies (ACEITO); preenche CPF, e-mail e senha do cofre, marca "Ok, entendi!", ENTRAR | "Selecione um módulo" |
| 2 | mesma URL (postback) | clica no card "Cotação PME" (3 a 29 vidas) | URL muda para o cotador novo |
| 3 | `sas-cotador-saude.paas.../dados-empresa` | Vendedor vem com o usuário logado; digita CNPJ; espera "CNPJ válido" e razão social | "Comece por aqui" |
| 4 | `/cuidado-cross` | Sim/Não; com Sim aparece modal "Confirmação" → Prosseguir | "Deseja adicionar o Cuidado 360°?" |
| 5 | `/congeneres` | digita a operadora atual, escolhe a sugestão (vira "chip"); ou "Este é um seguro novo." | "De qual congênere" |
| 6 | `/vidas-saude` | quantidade nas 10 faixas; confere "N vidas distribuídas" (3 a 29) | "Distribua as vidas da empresa" |
| 7 | `/distribuicao-agravadas` (só às vezes) | idade exata por vida nas faixas pedidas (vídeo: 0–18) → "+ Adicionar idade" até "Completo" | "Especifique as idades" |
| 8 | `/precificacao-planos` | filtros (557-AHO, Compulsória, 24 meses, com coparticipação no vídeo); 14 planos em 2 páginas; marca **um** plano | "Planos disponíveis" |
| 9 | `/comparacao-planos` | lê valor por vida em cada faixa; confere soma = preço do card | "Comparação de Planos" |
| 10 | `/resumo-final` | lê totais e "Características da Cotação"; confere com o pedido (falha fechada); grava "emitindo" logo antes do clique; Continuar | "Resumo da Simulação" |
| 11 | (mesma URL) | "Cotacao enviada com sucesso!" (sem acento) → "Gerando proposta..." (~14 s) | redireciona |
| 12 | `os11.../Simulador.aspx?Token=...` | lê "Protocolo Saúde: nº ..."; BAIXAR COTAÇÃO SAÚDE; salva PDF | "COTAÇÃO EMITIDA COM SUCESSO!" |
| 13 | (mesma) | próxima cotação (outro plano ou a versão sem coparticipação): COPIAR COTAÇÃO → modal "Deseja copiar a cotação?" → SIM (volta ao passo 3, tudo preenchido, CNPJ travado), sem sair do portal nem fechar nada (confirmado no vídeo em 05/11). Última cotação: "Voltar para a Home" | |
| 14 | `os11.../SaudeCotador/PainelCotacao.aspx` (05/11) | painel "ESTOU EM COTAÇÕES": é o começo depois da Home; o próximo pedido usa "NOVA COTAÇÃO" (ou "SELECIONAR OUTRO MÓDULO") | "Estou em cotações" |

## Bradesco (Cotação SPG): o que é diferente

Mapa do vídeo: `codegen/bradesco_mapa_video.md` (quadros e vídeo em `codegen/docs/`, fora do git: têm dados
pessoais). Onde houver escolha, o robô faz exatamente o que o corretor faz no vídeo (Seção 6 do mapa).
- **Um pedido (empresa) = um processo.** "Gerar processo" cria o Número do Processo (válido 40 dias). Cada plano ×
  versão (com/sem coparticipação) é um cálculo no mesmo processo: o 1º sai do cotador novo, os outros de **Alterar
  Cotação** -> Calcular. O robô nunca clica em "Finalizar Cálculo".
- **Registro em dois níveis** (`saida/bradesco/estado.json`): o processo (chave `assinatura_processo()`: CNPJ, grupo,
  vidas e idades, contrato, corretora, comissionamento, ramo; item "Processo") e cada cálculo (`assinatura()` = a do
  processo + coparticipação e dental; plano e acomodação na chave). "emitindo" é gravado antes do "Gerar processo"
  (processo e 1º cálculo) e antes de cada "Calcular" do Alterar Cotação. Caiu depois do clique: "Conferir no portal"
  ("Acompanhar processos"), nunca outro processo. Processo que já existe com cálculos faltando: o robô ainda não
  reabre (a calibrar), marca "Conferir no portal".
- **"Emitir de novo mesmo assim"** (a exceção da regra 3, decisão do usuário para testes e demonstrações, 07/11 na
  Bradesco): gera um processo NOVO com os cálculos de novo; o processo e os cálculos antigos (concluídos, `pdf_ok`, com
  o número que o corretor viu no aviso) vão para "reemitidos" na mesma gravação do "emitindo". Processo ou cálculo
  incerto (`emitindo`, `emitida`) nunca: o corretor resolve antes ("Saiu: já tenho o PDF").
- **Ensaio** vai até o Resultado, lê o preço do card de cada plano pedido e para antes de "Iniciar cotação".
- **Dental e layout do cálculo (vídeo, 69 s):** o Resultado já vem com o Padrão Doc 1 marcado e o corretor clica em
  "Sem plano dental" (padrão da engrenagem). O robô clica no dental pedido, confere que só ele ficou marcado e grava no
  log o que veio e o que ficou. Com "Sem plano dental" a página do cálculo tem Saúde Conjugado, "Totais Saúde" e
  "Totais Conjugado" (1ª parcela = prêmio + IOF); com um dental marcado o portal mostra a linha "Plano Dental" e um
  "Totais" só (1ª parcela já com o dental). Com "Sem plano dental" e sem "Totais Saúde" o robô NÃO imprime e para com
  o motivo (o processo já existe: "Conferir no portal").
- **Dental na chave do processo (10/11):** o dental entra na chave de registro do processo (`assinatura_processo()`) só
  quando não é o "Padrão Doc 1", para as chaves antigas continuarem valendo. É **só a chave do registro**: no portal o
  robô continua escolhendo o dental no Resultado ("Sem plano dental" é o padrão do vídeo). Motivo: o robô ainda não
  reabre um processo para acrescentar cálculo; sem isso, trocar o dental de uma empresa já cotada travava em "o processo
  já existe" sem o aviso de "Emitir de novo". O mesmo pedido repetido continua protegido (aviso + botão). O log grava
  "Registro: o dental ... entra só na chave de registro do processo".
- **Página do cálculo lenta (10/11):** depois de "Processo N gerado!" o portal chegou a levar mais de 100 s para mostrar a
  página do cálculo, com o aviso "válido por 40 dias" (OK) por cima. A espera só termina com o título "Cálculo de Seguro
  SPG" e o número no mesmo texto (`_numero_no_texto`); depois o robô espera o quadro pelo tempo da emissão
  (`timeout_emissao_ms`, não o da tela), fecha o aviso OK quando aparecer e grava no log "Esperando a página do cálculo
  (N s). Tela: ..." a cada 20 s. Antes ele desistia em 60 s e o processo ficava gerado sem PDF.
- **Aba sem resposta e Parar na espera do cálculo (10/11):** em 4 de 5 pedidos de 10/11 a tela do cálculo apareceu (com o
  aviso OK por cima) mas os quadros da aba do robô davam TargetClosedError, com a aba "aberta" (causa ainda NÃO
  confirmada). `_garantir_pagina` sonda a aba (`_responde`) e, se ela não responde, segue em outra aba que responda; o log
  traz "A aba do robô não responde (...). Abas: aba 0: /caminho responde | ..." (`_diagnostico_das_abas`, só caminhos) e,
  a cada 20 s, "Esperando a página do cálculo (N s). Tela: ... | Abas: ...". Com esse log da próxima falha dá para ver se
  o portal abriu o cálculo em outra aba, se a aba morreu ou se foi o navegador. Com o número do processo já guardado, o
  Parar vale na espera (`_parar_na_espera`, depois de 3 s) e o pedido fica em "Conferir no portal" com o número.
- **Alterar Cotação no portal real (calibrado pelo mapa de 10/11, `NN_alterar_form_N.*`; ainda sem Calcular):** os
  selects são `rede.codigo` (Plano Saúde: "Nacional III", sem o Nx), `acomodacao.acmdEscolhidas` (lista múltipla: "Quarto
  Privativo", "Multiplo 2", "Multiplo 3") e `fatorModerador.codigo` (Coparticipação: "--" = sem, "30%"). O texto "Plano
  Saúde" também está numa tabela escondida antes; pelo rótulo o 1º select seguinte era a Categoria Funcional.
  `select_antigo` usa o name do portal, depois o label (simulador) e por último a célula visível. O robô grava
  `NN_alterar_form_N.*` assim que o formulário abre. `codigoSucursal` não é código de verificação
  (`_campos_de_cadastro_no_mapa`). O "Calcular" ainda não foi exercitado no portal real.
- **Modo de testes (`teste_repetir`, decisão do Tiago, 10/11):** repetir a mesma cotação é rotina na calibragem e o
  registro anti-reemissão travava o robô na Home ("o processo já existe", processo "emitindo" de uma página que não
  carregou). Com `operadoras.bradesco.teste_repetir: true` (ligado no `config.yaml`; padrão do código: false; campo em
  Robôs > Bradesco, passo Portal), antes de cada pedido o robô tira do registro o processo e os cálculos daquela empresa
  (qualquer situação, inclusive "emitindo"), no mesmo "liberar" da tela: vão para `liberados` no `estado.json` com o
  número do processo, e o pedido gera um processo NOVO no portal. Log: "MODO DE TESTES: tirei do registro...". Só nesta
  fase; para o uso de verdade, desligar (a regra 3 volta a valer: o registro é o que impede processo duplicado).
- **Identificação do cálculo:** o robô digita "COM COPAY" ou "SEM COPAY" (versão do cálculo; mudável na engrenagem) em
  "Identifique o cálculo a ser armazenado"; sai no cabeçalho do PDF. A janela "Imprimir" é mapeada (`NN_calculo_imprimir.*`)
  logo depois de o PDF sair dela.
- **Só ensaio até a calibragem:** `emissao_liberada: false` no `config.yaml` (a Nova cotação começa com a Bradesco
  desmarcada e o robô recusa emitir sem portal). Ligar só com o pedido do Tiago, depois do ensaio conferido.
- **Planos:** o nome do card mais o reembolso quando ele tem multiplicador ("Nacional Plus 4x | Quarto"; os três
  Nacional Plus do vídeo só se diferenciam pelo 4x/6x/8x). No Alterar Cotação o "4x" vira a acomodação "Múltiplo 4";
  sem multiplicador, a opção de quarto ("Quarto Privativo") ou "Enfermaria".
- **Login** em duas etapas (CPF/CNPJ -> Continuar -> senha no nidp); o cofre `NewportCotacoes/bradesco` guarda
  CPF/CNPJ, senha e o CPF do intermediário (aba Intermediário). Mesmas regras de segurança da SulAmérica.
- **PDF:** a janela "Imprimir" (about:blank) salva como PDF (`page.pdf`, só com a janela do portal escondida; com ela
  visível o robô tenta pelo CDP). `window.print` é desligado no navegador do robô.
- As páginas antigas (cálculo e Alterar Cotação) ficam num iframe: `telas.quadro_com` acha o quadro pelo texto.
- **Portal real (calibrado em 07/11, ensaio até o Resultado e as abas dos Dados complementares, sem gerar nada):**
  login em duas páginas (CPF/CNPJ da corretora; depois CPF de acesso + senha no nidp); SAÚDE é `<a>` sem href;
  aviso de campanha (`div.modal.pn-modal.in`) fechado antes dos cliques; Cotação SPG pelo "Conferir" do Acesso
  rápido (pelo endereço direto o portal dá "Error 403: AuthorizationFailed"); ela abre a área antiga num iframe
  (EEEM, "Acompanhamento de Processos") e o cotador novo sai de Ações -> "Iniciar Nova Cotação SPG", noutro iframe
  (`saudeexterno.../eeem-fed-simulacao-cotacao`): cada tela é procurada nos quadros (`Sessao.onde`) e o mapa grava
  o HTML e a árvore de cada iframe. Escolhas são `<button role="radio">`, listas são ng-select (opções
  `div.ng-option`), campos sem nome acessível (por `formcontrolname` ou pelo rótulo), números digitados (com `fill`
  o portal não conta). O mapa da tela de login só antes de digitar; depois, o log descreve a tela sem valores.
- **Muitas entradas seguidas** (07/11: ~15 em 25 min, junto com uma queda do portal) deram "AuthorizationFailed"
  logo depois da senha: o robô apaga os cookies dele e entra de novo uma vez; se continuar, para. Calibre com
  poucas execuções.

## Amil (vendasmil, Cotação PME): o que é diferente

Mapa do vídeo: `codegen/amil_mapa_video.md` (quadros e vídeo em `codegen/docs/`, fora do git). Estado e dúvidas: `codegen/amil_status.md`.
- **Uma oportunidade (OPP) por empresa, uma cotação (COT) por plano.** Registro em dois níveis (`saida/amil/estado.json`): a OPP
  (chave = o CNPJ; "emitindo" antes de "Concluir Oportunidade", "pdf_ok" com o OPP e o id da URL assim que o número aparece; uma OPP
  conhecida é REABERTA, nunca criada de novo) e cada COT (chave = empresa + vidas + corretor + dental + plano). A COT é gravada como
  **"digitando"** assim que aparece (status que NÃO bloqueia: serve para continuar a mesma cotação em vez de criar outra),
  **"emitindo" antes de "Concluir Cotação"** (o ponto sem volta), "emitida" quando o portal diz Concluída e "pdf_ok" com o PDF.
- **Caiu depois de Concluir Cotação:** o robô reabre a COT (pelo id da URL ou pela lista "Cotações da Oportunidade") e baixa o PDF,
  sem criar outra; se o portal ainda a mostra em Digitação, conclui a MESMA. Parar vale entre telas e, depois de 3 s, enquanto o
  portal conclui/gera o PDF (a COT já é conhecida; a próxima execução recupera).
- **O ensaio da Amil JÁ CRIA a oportunidade e uma cotação "Em Digitação" por plano** (vencem em 1 dia): é o único jeito de ver o
  preço. Para em Revisar Cotação, sem Concluir Cotação. A tela avisa (Nova cotação, Ajuda, engrenagem). Cotação concluída é PULADA
  no ensaio; "digitando" é reaproveitada.
- **Nunca** clicar em "Criar Proposta", "Enviar por E-mail" nem "+ Incluir Plano Médico" (não há seletor para eles; o simulador conta
  os cliques e os testes exigem 0).
- **Login:** cofre `NewportCotacoes/amil` (usuário e senha). Todo login pede um **código de 8 dígitos enviado por e-mail**: o robô pede
  na tela do Newport (mesma faixa da SulAmérica) e digita; o código nunca vai para log, mapa nem `portal.json`. A sessão fica no
  perfil do navegador e o robô registra em `portal.json` quando começou (`sessao_login_em`), quando a viu aberta
  (`sessao_viva_em`) e quanto durou a anterior (`sessao_duracoes_min`; log "A sessão anterior durou de X a Y min"). Sair do portal
  (fila vazia, Parar, fim da linha de comando) faz o próximo login pedir um código novo. A 1ª etapa do login não está no vídeo:
  o mapa `NN_login.*` (antes de digitar) calibra.
- **Valores:** o valor por vida muda com o total de vidas, então o robô só lê a grade depois de preencher todas as faixas (duas leituras
  iguais e conferindo). Confere: quantidade por faixa, subtotal = valor × vidas, soma = Valor Total; no Revisar, 50% na 1ª e 2ª parcelas
  só com o selo (Total Geral = metade do mensal; sem selo = mensal), após 12 meses = mensal + dental. A tela mostra o valor por mês (a
  partir da 3ª parcela); o resto vai para o log.
- **Aditivo e dental:** o vídeo não mostra se vêm marcados. O robô confere o estado final (dental em "Aderir", aditivo AMIL RESGATE
  SAÚDE I presente quando o plano tem) e só clica no dental se faltar. Plano sem dental: segue sem.
- **PDF:** `cotacao-COT-XXXXXXX.pdf` pelo botão "Baixar PDF" (evento de download; o botão fica "Gerando PDF…" antes). Arquivo morto
  `AMIL_<cnpj>_<COT>.pdf`; pasta do cliente `AMIL <apelido do plano> <nome curto da empresa>.pdf` (apelido em `arquivos.nomes_arquivo`;
  nome curto = "nome para achar depois" da Nova cotação, que entra no lugar de `{versao}` do núcleo).
- **Emissão liberada (Tiago, 12/11):** o ensaio no portal real (login com código, OPP, COT, Vínculo, plano, grade, aditivo/dental,
  Revisar Cotação) foi conferido e `emissao_liberada: true` no `config.yaml`; o padrão do código continua false. "Concluir Cotação"
  só roda quando o Tiago clica em Gerar (nunca por conta do Claude). Exercitados no portal real em 12/11 (1ª emissão, 2 planos na mesma
  OPP, PDFs baixados e conferidos): login com código, continuar COT em Digitação, Concluir Cotação + PDF. Ainda NÃO exercitados:
  plano sem aditivo/dental, pedir de novo (anti-duplicidade), Parar no meio.

## Lições de 15/11 (portais que mudam e vários robôs juntos)

- **A SulAmérica foi atualizada** entre 06/11 e 15/11 (hash do `layout`/`webpack` do cotador Next.js mudou) e o robô, que
  funcionava, passou a parar. Dois efeitos: (1) o card do plano mostra "R$ X por vida / mês" e o total em outra linha
  ("Total estimado: R$ Y / mês (N vidas)"); o preço do card é o TOTAL (`extracao.preco_do_card`), que bate com a soma das
  faixas da Comparação; (2) com os robôs rodando juntos, a troca de tela às vezes muda a URL e a barra mas deixa o corpo da
  tela anterior para sempre (sem requisição pendente, sem erro de JavaScript, página desenhando). F5 manda o assistente de
  volta a `/dados-empresa` vazio (o estado só existe na aba): `telas.esperar_tela` recarrega uma vez (antes do resumo,
  nunca depois) e `fluxo.processar_pedido` retoma o pedido pela tela da empresa (`TelaReiniciou`, até 6 vezes por pedido).
  Numa rodada com os três robôs travou 4 vezes e todas se recuperaram. O simulador reproduz isso (`travar_troca_cuidado`).
- Depois de "Sair da cotação" o portal novo mostra "Selecione um módulo" em `Simulador.aspx?Token=...`, a mesma URL da cotação
  emitida: `identificar_etapa` olha também o conteúdo (`tela_modulos_visivel`).
- O mapa de erro (`NN_ERRO_<etapa>.erro.txt`, só no núcleo) guarda o erro inteiro do Playwright, visibilidade/foco, se a
  página desenha quadros (`requestAnimationFrame`), requisições pendentes e com erro (host e caminho, sem query) e erros de
  JavaScript do portal. Leia ele antes de supor a causa.
- A faixa do código de verificação da tela é uma só e é compartilhada: ela só some quando a operadora que a pediu deixa de
  esperar (`NP._conferirFaixaCodigo`); eventos de outra operadora não a escondem (a Amil esperava um código sem campo).
- Reiniciar a tela com um robô no meio de uma cotação mata o processo sem sair do portal: a SulAmérica fica com "acesso ativo
  para este CPF" por alguns minutos (o robô espera e tenta de novo a cada 60 s, por até 10 min). Só reinicie com a fila vazia.
- Tempos por tela: SulAmérica e Bradesco com `timeout_tela_ms` 150 e 180 s no `config.yaml` (a Cotação SPG da Bradesco chegou a
  levar 62 s; o portal fica 70 s na busca de processos).

## Armadilhas já conhecidas

- "24 meses" e "Com coparticipação" aparecem no filtro **e** em todos os cards: buscar filtro por papel (checkbox), nunca só por texto. Filtro tem que marcar o desejado **e desmarcar** o outro.
- Nomes de plano se repetem ou se contêm: "Direto Nacional" existe em Enfermaria e Apartamento; "Especial Vital" está contido em "Especial Vital R1". Identificar por nome exato + acomodação. Quando o mesmo plano existe nas duas acomodações, a acomodação entra no nome do PDF.
- A lista de planos é paginada (12 por página no vídeo).
- A tela de módulos tem a mesma URL do login: não dá para "voltar ao início" com `goto`; usar os botões da tela final.
- Com a sessão viva, nunca recarregar a LoginGeral.aspx (05/11: nem da tela de módulos): o portal mostra o
  formulário de novo e recusa o segundo login. `entrar()` confia na tela que já é do portal (módulos, cotador,
  emissão); se a sessão tiver caído, a próxima tela leva ao login e o robô entra ali. "Acesso ativo" de outro
  lugar: o robô espera `login_reentrada_ms` e tenta de novo, até `login_liberacao_ms` (senha errada continua
  parando na primeira). O tour "Guia de navegação" é pulado sozinho antes de qualquer ação
  (`page.add_locator_handler`, `telas.pular_tour_sempre`).
- Sair do portal (05/11): "Sair do Cotador" fica no menu lateral do cabeçalho do portal antigo (ícone de 3 barras,
  `sel.menu_do_portal`, `sel.botao_sair_do_portal`; achado no `01_login.html`). `etapas.sair_do_portal` volta à tela
  de módulos (sai da cotação ou da emissão), clica e espera o login. O trabalhador sai e fecha a janela: fila
  vazia há `tempos.sair_do_portal_min` (padrão 3; 0 = nunca), Parar com a fila vazia, "Sair do portal agora"
  (`POST /api/sair/{op}`, só com o robô parado) e a janela preta fechando (`SetConsoleCtrlHandler`, ~4 s).
  Nunca no meio de uma cotação. "Acesso ativo" **no meio de um pedido** (`entrar(insistir=False)`): para na
  hora e avisa; a espera de 1 em 1 min só vale no começo do trabalho.
- O robô relê a cada login o `maxlength` do campo de senha e guarda em `saida/<op>/portal.json`
  (`nucleo.configuracao.aprender`); a engrenagem usa esse limite no Guardar (16 até o portal dizer outro).
  Nada de credencial nesse arquivo.
- De dentro do cotador, nunca ir para a página de login com a sessão viva: o portal mostra o login e recusa o
  segundo acesso ("Já existe um acesso ativo para esse CPF"). Sair pelo "Sair da cotação" + modal "Deseja
  realmente sair da cotação?" (fundo escuro que cobre a tela).
- O cotador demora a abrir depois de "Cotação PME" (mais de 30 s no portal real em 04/11): esperar a rota do
  cotador ou "Comece por aqui", nunca um tempo fixo curto. Rotas sempre pelo caminho da URL (`sel.caminho`).
- Entre uma cotação e a próxima do mesmo pedido (ex.: a versão sem coparticipação): **COPIAR COTAÇÃO**, como o
  corretor no vídeo. O robô **nunca** sai do portal nem fecha a página da emissão, abas ou o navegador entre
  cotações (decisão do usuário em 05/11, depois de rever o vídeo; a "janela nova" foi desfeita). Plano B, se a
  cópia não deixar trocar a coparticipação (`FiltroTravado`): "Sair da cotação" na mesma aba e NOVA COTAÇÃO no
  painel, sem login; o robô guarda isso em `portal.json` (`copia_trava_copart`) e, das próximas vezes, troca de
  versão pelo "Nova cotação" da tela da emissão. Logout só no fim da fila (folga), no Parar com a fila vazia,
  em "Sair do portal agora", ao fechar a tela e no fim da linha de comando.
- A tela nunca roda JavaScript velho: a página aponta para os arquivos com `?v=<versao>` (muda a cada vez que a
  tela abre), os arquivos vão com `Cache-Control: no-cache` (`_ArquivosSemCache`) e a página recarrega sozinha
  quando o servidor reinicia (`NP.conferirVersao` na reconexão do SSE). 05/11: o Chrome guardava o JS antigo
  até depois do F5 e a Nova cotação mandava a coparticipação da cotação anterior.
- "Voltar para a Home" leva ao painel "Estou em cotações" (`PainelCotacao.aspx`), não à tela de módulos. O painel
  é um começo (etapa `painel`) e conta como sessão aberta (`login._sessao_na_tela`, `painel_visivel`): sem isso o
  robô recarregaria o login com a sessão viva. O mapa só toma uma tela por "login" com campo de senha visível
  ou preenchido (o painel tem um escondido). "Cotar de novo" (Nova cotação) não traz os campos do robô da
  cotação antiga: valem os da configuração de hoje.
- Fim de cada cotação (05/11): depois do PDF, o robô vai para "Copiar cotação" (próxima) ou "Voltar para a Home"
  (última; se não houver o botão, "Nova cotação") e espera o começo em qualquer aba. Não fecha abas. A tela da
  emissão vira mapa (`NN_emitida`, `NN_emitida_pdf`): o mapa só toma uma tela por "tela de código" se o campo
  de código estiver visível.
- PDF que não baixou depois de emitir: com `recuperar_pdf_automatico: false` (padrão) fica em "Conferir no
  portal" e o robô não reabre a página da emissão. Não ligue sem confirmar no portal que reabrir não gera
  protocolo novo.
- Telas carregam com skeleton sem texto; esperar o título da tela e o fim dos skeletons, nunca tempo fixo.
- Textos com e sem acento no mesmo portal: usar sempre `rx()` de `nucleo/texto.py`.
- IOF de 2,38% é calculado **por vida e arredondado**, depois somado (vídeo: 58,16; sobre o total daria 58,15).
- Na cópia de cotação, o plano anterior pode vir marcado: o robô usa "Desmarcar todos" antes de escolher.
- O PDF baixado vem como `PropostaComercialCuidado360_<protocolo>-1.pdf`; o robô guarda como
  `saida/sulamerica/pdfs/SULAMERICA_<cnpj>_<protocolo>.pdf`, copia para a pasta do cliente como
  `SULAMERICA <PLANO>.pdf` e a tela entrega com esse mesmo nome.

## Calibragem no portal real (seu trabalho principal aqui)

1. Peça ao usuário uma planilha com **uma** linha real (empresa que a Newport cotaria de qualquer forma).
2. O corretor guarda o login na engrenagem do robô (tela 1, Login) e liga em Robôs "Mostrar a janela do
   portal (para calibrar)" e "Guardar print de cada tela". Rode o ensaio pela tela ("Ensaiar sem emitir",
   o usuário clica) ou `python main.py --ensaio --mapear --linha <n>`. O robô entra sozinho.
   (Se a tela estiver aberta com a janela do portal, ela segura a trava: peça para fechar a tela antes.)
   O mapa do login (`01_login.*`) é tirado antes de digitar, com os campos vazios: é o que calibra
   `login_campo_*`, `login_ok_entendi` e `login_botao_entrar`. Depois de digitar, nenhuma tela de login
   ou de código vira mapa; se o login falhar, calibre pelo `01_login` e pelo log.
3. Se falhar, o log diz a etapa. Leia `saida/sulamerica/mapa/<execução>/NN_ERRO_<etapa>.aria.txt` (árvore
   de acessibilidade: papéis e nomes dos elementos) e, se precisar, o `.html` e o `.png` do mesmo número.
4. Corrija **só** `operadoras/sulamerica/seletores.py`. Mexa em `etapas.py` apenas se a tela se comportar
   de outro jeito (ex.: um modal a mais). Anote a mudança em `codegen/mapa_seletores.md`.
5. Rode de novo até o ensaio chegar ao resumo com `ENSAIO_OK` em `saida/sulamerica/resultados.xlsx` e
   valores iguais aos da tela.
6. Só então, **com o usuário pedindo**, faça a primeira emissão real com um plano. Depois, dois planos
   (testa "Copiar cotação"). Depois, peça de novo a mesma cotação para confirmar que nada é reemitido.
7. Rode `python -m pytest` no fim. Se precisou mudar o comportamento, espelhe a mudança no simulador.

Decisões de negócio: os **padrões da Newport** ficam no `config.yaml` (padrões do vídeo: Cuidado 360° =
sim, contratação compulsória, 24 meses, produto 557 - AHO, um PDF por cotação via "Copiar cotação", nome
`SULAMERICA <PLANO>.pdf`, `nomes_arquivo` para exceções, ex.: Executivo R1 → EXECUTIVO). Coparticipação:
**"Com e sem" (`as_duas`, decisão do usuário em 05/11)**: a Newport sempre pega as duas, então cada plano
vira duas cotações (plano 1 com, plano 1 sem, plano 2 com...), cada uma com protocolo e PDF próprios
(`SULAMERICA <PLANO> COM COPARTICIPACAO.pdf` / `... SEM COPARTICIPACAO.pdf`). **Cada corretor muda os dele na engrenagem do robô** (tela Robôs > SulAmérica), que grava em
`saida/config_tela.json`. Não mude os padrões do `config.yaml` sem o usuário.

## Configuração do robô pelo corretor (engrenagem)

- O esquema vem de `Operadora.configuracao(cfg)`: uma entrada por tela do portal (na ordem de `etapas`),
  com os campos que o corretor pode mudar. Tipos e validação em `nucleo/configuracao.py`; a página é
  `app/web/js/telas/robo.js` e desenha qualquer operadora sem código novo na tela.
- A chave de cada campo é o caminho na seção `operadoras.<id>` do `config.yaml` (`padroes.vigencia_meses`,
  `tempos.timeout_tela_ms`, `arquivos.nome_pdf_destino`...). `PUT /api/robos/{op}` recusa qualquer
  chave que não esteja declarada: nunca exponha URL, pasta de saída ou conferências ali.
- Campo que muda o preço da cotação (vigência, coparticipação, contratação, Cuidado 360°, produto...)
  **tem que entrar em `Pedido.assinatura()`**, senão o registro anti-reemissão acharia que é a mesma
  cotação. O produto só entra quando não é o 557 - AHO, para as chaves já gravadas continuarem valendo.
- "Com e sem" coparticipação: o pedido fica com `coparticipacao = "as_duas"`, e cada alvo (`PlanoAlvo`)
  leva a sua (`"com"`/`"sem"`, `etapas.com_versoes`). `Andamento.pedido` devolve a versão do alvo atual
  (`Pedido.na_versao`): é ela que vale para filtros, conferências do card e do resumo, nome do PDF e chave
  do registro (a versão "com" tem a mesma chave de um pedido "com"). Na 2ª versão o robô copia a cotação e
  troca só o filtro; se a cópia travar o filtro (`FiltroTravado`), sai da cotação e refaz do começo. Campo
  que multiplica as cotações na Nova cotação: `"multiplica": {"as_duas": 2}` em `campos()`; opção de
  escolha com 3º item = frase do resumo.
- Campos de cotação que vêm da configuração levam `"robo": True` em `campos()`: a Nova cotação mostra
  numa frase e abre em "Mudar só nesta cotação". Os da empresa levam `"empresa": True`.
