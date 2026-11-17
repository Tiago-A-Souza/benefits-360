# Amil (vendasmil): status do trabalho

Atualizado em 11/11. Branch `amil-em-andamento`. Retomado depois da pausa de 10/11: robô rodado contra o simulador, testes
escritos e suíte completa executada (resultado no fim deste arquivo). **Nada foi executado no portal real.**

## Pronto

- Pré-requisitos (na `main`, `e461320`): tag `bradesco-v1-aprovado`, regra 11 do `CLAUDE.md` congelando SulAmérica e Bradesco,
  `.gitignore` do material da Amil, mapa do vídeo versionado.
- `operadoras/amil/` completo: `pedido`, `planilha`, `extracao`, `seletores` (tudo VALIDAR), `telas`, `login` (código de 8 dígitos pedido
  na tela do Newport; mede a duração da sessão), `etapas`, `fluxo`, a classe `Amil` (engrenagem, textos da tela, nome do PDF) e o
  `simulador/` (porta 8785). Registrada em `operadoras/__init__.py`, `config.yaml` e `config_simulador.yaml`.
- Regras do mapa (Seções 2 e 5): uma OPP por empresa e uma COT por plano; OPP e COT gravadas assim que aparecem; "emitindo" antes de
  Concluir Cotação; caiu depois, reabre a COT e baixa o PDF sem criar outra; o ensaio para em Revisar Cotação e a tela avisa que ele
  já cria a oportunidade; nunca Criar Proposta / Enviar por E-mail / Incluir Plano Médico (o simulador conta os cliques e os testes
  exigem 0).
- Valores: só depois de preencher todas as faixas; conferências de grade (subtotal, soma = Valor Total) e de revisão (50% com o selo,
  após 12 meses = total + dental). Os três planos do vídeo batem com a Seção 3.
- Testes em `tests/amil/`: 29 de unidades, 13 do robô contra o simulador (ensaio; 3 planos na mesma oportunidade; queda depois de
  Concluir recuperando o PDF; pedir de novo sem duplicar e "emitir de novo"; código de login pedido pela tela e sessão no perfil; parar e
  continuar; parar durante "Gerando PDF"; plano fora da lista; valor que não confere; sem emissão liberada; dental) e 2 da tela.
- `CLAUDE.md`: seção "Amil (vendasmil): o que é diferente", comandos e mapa do código.

## Bugs que os testes acharam e foram corrigidos

- JavaScript do simulador com uma chave sobrando; layout da grade que deixava os campos de vidas sob o painel lateral.
- Cotação continuada direto na tela de Revisar julgava o dental pela tela dos planos (que não foi vista); agora vale o pedido.
- Parar também vale enquanto o portal gera o PDF (a COT já está "emitida" no registro; a próxima execução baixa).

## Falta

1. **Portal real, só ensaio** (pedido do Tiago): calibrar com `python main.py --operadora amil --ensaio --mapear --linha 2` ou pela tela
   ("Ensaiar sem emitir"). Primeiro a 1ª etapa do login (mapa `NN_login.*`, antes de digitar), depois cada tela. O ensaio cria uma
   OPP e uma COT "Em Digitação" de verdade (vencem em 1 dia). `emissao_liberada` continua `false` até o Tiago pedir; "Concluir Cotação"
   só quando ele clicar em Gerar.
2. Decidir o merge na `main` (ver abaixo).

## Decisões e dúvidas abertas

- `emissao_liberada: false` por padrão e a Nova cotação começa com a Amil desmarcada (como a Bradesco em calibragem). Confirmar.
- O vídeo `AMIL.mp4` não está em `codegen/docs/vídeos/` (só `BRADESCO.mp4`); trabalhei pelo mapa e pelos 31 quadros.
- Mínimo de vidas = 2 (o mapa não diz). Confirmar.
- A tela mostra um valor por cotação: o valor por mês a partir da 3ª parcela. O Total Geral da 1ª e 2ª parcelas (50% com o selo) e o
  total após 12 meses vão para o log (não há coluna para eles na tela). Dizer se quer outra coisa na tela.
- A lista de planos da Nova cotação é parcial (Seção 4 do mapa) e agrupada pela família do plano (Platinum, Black, S2500...).
- `digitando` é um status novo do registro (não bloqueia, serve para continuar a mesma cotação). Os testes da tela passaram com ele; falta
  ver as Pendências e Cotações da tela com um item assim no portal real.
- A tela pede a idade em 0 - 18 e 59+ quando a SulAmérica está na mesma tela (a lista de faixas é a união de todas as operadoras); a Amil
  ignora essas idades. É comportamento da tela, não da Amil.
- Reabrir a oportunidade pelo endereço `/oportunidades/<id>` pode falhar no portal real (na Bradesco o endereço direto deu 403); o caminho
  pelo menu Andamentos não está calibrado.
- O que o portal faz com um CNPJ que já tem oportunidade criada fora do robô não se sabe.
- Código por e-mail: caminho A (digitado na nossa tela). O B (ler o e-mail pelo Microsoft Graph) fica para depois da autorização da TI.
