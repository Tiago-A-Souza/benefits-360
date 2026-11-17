# Newport Cotações

Tela do corretor + robô que faz o trabalho repetitivo no portal da operadora. A primeira operadora é a
**SulAmérica, Cotação PME (3 a 29 vidas)**: o corretor informa a empresa, as vidas por faixa e os
planos; o robô preenche o portal, emite **uma cotação por plano**, baixa o PDF e entrega na tela e na
pasta do cliente com o nome de sempre (`SULAMERICA <PLANO>.pdf`). O robô entra no portal sozinho, com
o login que o corretor guarda uma vez na engrenagem do robô: fica no cofre do Windows (Gerenciador de
Credenciais), nunca em arquivo, histórico ou log, e a senha nunca volta para a tela.

## Instalar e abrir (Windows)

1. Instale o Python 3.11 ou mais novo (<https://www.python.org/downloads/>), marcando
   **"Add python.exe to PATH"**.
2. Dois cliques em **`instalar.bat`** (uma vez por computador).
3. Dois cliques em **`Abrir Newport Cotacoes.bat`** (todo dia). A tela abre no navegador; deixe a
   janela preta aberta enquanto usa.

Para treinar sem o portal: **`Treinar no simulador.bat`** (nada é emitido de verdade).

Cada corretor configura o próprio robô pela **engrenagem** do cartão da SulAmérica: produto, tipo de
contratação, vigência, coparticipação, Cuidado 360°, planos que já vêm marcados, nome dos PDFs e o
resto do que o robô preenche no portal, tela por tela.

## Documentos

- **`PLAYBOOK.md`**: guia completo (autorização e LGPD, instalação, a tela, planilha, calibragem,
  operação, erros, testes, novas operadoras).
- **`CLAUDE.md`**: contexto e regras para o Claude Code (segurança, mapa do código, como adicionar uma
  operadora, calibragem).

## Para quem mantém

```
python -m app                                   # a tela (http://127.0.0.1:8600)
python -m app --config config_simulador.yaml    # a tela contra o simulador
python -m operadoras.sulamerica.simulador       # o simulador do portal
python main.py --ensaio --mapear --linha 2      # calibragem pela linha de comando (não emite)
python -m pytest                                # testes (sobem o simulador sozinhos)
```

No portal real, comece sempre pelo ensaio ("Ensaiar sem emitir" na tela), que para antes de emitir.
