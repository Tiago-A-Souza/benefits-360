# Porto Seguro — acesso autorizado ao Corretor Online

Como o robô entra no portal da Porto **sem burlar reCAPTCHA**. Nenhum CPF, senha ou SUSEP real entra neste arquivo; os códigos de teste são fictícios (`AAAAAA`, `BBBBBB`).

## O que está autorizado

1. Abrir a página pública `corretor.portoseguro.com.br/corretoronline`.
2. Recusar localização e cookies sozinho.
3. Clicar em **Acessar o Corretor Online** (modal na mesma página, não popup).
   O contrato estável do portal é `window.openLogin()`. O botão do header
   (`data-gtm-name=login`, texto num `div.text-btn`) só dispara essa função. O robô chama
   `openLogin()` primeiro; se não existir, clica por CSS / texto / shadow DOM, sem exigir
   caixa visível na janela. Insiste até o modal de CPF/senha aparecer.
   O mapa da 1ª tela só roda **depois** desse clique: um iframe sem URL na landing
   fazia o Playwright pendurar no evaluate e o robô nunca clicava.
4. Preencher CPF e senha do cofre Windows `NewportCotacoes/porto`.
5. **Parar.** O corretor clica em **ENTRAR** na janela do Chromium do robô.
6. Escolher o código SUSEP no dropdown **só por clique** (sem digitar). Aceita o sufixo ` (P)` no rótulo.
7. Guardar a sessão no `perfil_navegador` da pasta de saída. Se a sessão ainda vale, o robô não pede login de novo.

## O que não está autorizado

- Resolver, burlar ou esconder o reCAPTCHA (serviço de captcha, stealth, token injetado, `navigator.webdriver`).
- Clicar em **ENTRAR** quando o modal tem reCAPTCHA: o portal responde *«Por motivos de segurança, não conseguimos validar seu acesso»*. Esse aviso **não** é senha errada; o robô não marca o login como recusado.
- Preencher o CPF de «recuperar senha» (`#logonSenha`). O campo do login é `#logonPrincipal`.
- Escrever CPF, senha ou SUSEP real em log, mapa, commit, teste ou YAML.

## Por que o clique em ENTRAR é da pessoa

O rodapé do modal avisa que o login é protegido por reCAPTCHA (muitas vezes invisível). Um clique do Playwright no **ENTRAR** falha a verificação. O clique da pessoa, com CPF e senha já preenchidos, é o passo que o portal aceita. O robô espera até 5 min (`timeout_codigo_ms`) e segue na SUSEP.

O texto de ajuda *«O Recaptcha serve para a sua maior segurança»* **não** é desafio. Desafio visível = «Não sou um robô» / bframe. Iframe de reCAPTCHA não é varrido com `is_visible`/`evaluate` (trava o Playwright ~30 s).

## Robô de teste vs robô real

| | Teste (esta frente) | Real |
| - | - | - |
| Porta | 8602 | 8600 — **não mexer nesta frente** |
| Pasta | `rpa/saida_teste_porto/` (gitignore) | `rpa/saida/` |
| Front | 5176 | 5173 |
| Cofre | o mesmo `NewportCotacoes/porto` no Windows | o mesmo |
| Config | `rpa/config_teste_porto.yaml` | `rpa/config.yaml` |

Subir o teste, a partir de `rpa/`:

```
python -m app --config config_teste_porto.yaml --sem-navegador
```

O Chromium de teste usa `saida_teste_porto/porto/perfil_navegador`. Não versionar.

## Sequência no corretor

1. Em Conexões da Porto, guardar CPF, senha e o código SUSEP do dropdown (o sufixo `(P)` é opcional).
2. Ligar **Mostrar a janela do portal**.
3. **Testar login**.
4. Quando o painel pedir, clicar em **ENTRAR** na janela do portal (não no Benefits).
5. O robô escolhe a SUSEP e avisa login feito.

## Testes (só fictício)

- `tests/porto/test_porto_susep.py` — clique no dropdown (`AAAAAA` / `BBBBBB`).
- `tests/porto/test_porto_entrada.py` — página pública, modal, CPF `#logonPrincipal`, reCAPTCHA não clica em ENTRAR.
- `tests/porto/test_porto_simulador.py` — ensaio até o passo 3; `exigir_captcha` para o robô **sem burlar**.
- Simulador: CPF `529.982.247-25`, senha `Treino#Porto1`, SUSEP `AAAAAA`.
