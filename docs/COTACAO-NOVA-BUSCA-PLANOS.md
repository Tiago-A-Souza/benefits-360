# Nova cotação — busca de planos (Fase 1)

A tela **Cotações → Nova cotação** mostra os cards com a lista que já vem de
`GET /api/operadoras` (`planos[]`): união do código da operadora
(`planos_conhecidos`) com o catálogo gravado no `tela.db` (planos vistos no
portal). Essa lista **não muda de ordem nem some plano** nesta fase.

Abaixo dos cards, o campo **Buscar outro plano desta operadora** procura só no
catálogo do portal. Resultado selecionável = plano que o robô já viu (ou que o
código já conhece) e que **ainda não está nos cards**. Digitar um nome que não
está nesse catálogo mostra: *só aparecem planos já vistos no portal; aquele
plano ainda não está disponível*.

O pedido que vai ao robô (`POST /api/trabalhos`) usa o rótulo
`Nome | Acomodação` (na Amil, o próprio nome do select). Nada fora desse
catálogo entra no pedido.

## Por que a matriz SiscorNet não alimenta o pedido

A planilha SiscorNet (`Matriz_Hospital`) é comparativo de **rede hospitalar**:
coluna com acomodação misturada no texto, sem código ANS, sem garantia de ser
o produto PME do cotador.

O robô clica por **nome normalizado** (e acomodação, quando o portal tem).
O rótulo da matriz não é esse nome. Exemplos:

| Card / portal | Coluna de rede |
|---|---|
| Amil `PLATINUM R1 COPART` | `PLATINUM` |
| Porto `Diamante Pro` | `DIAMANTE PRO SP - APTO` |
| Bradesco `Nacional Plus 4x` | `NACIONAL PLUS` |

Mandar a coluna Siscor como plano gera falha no meio (Amil/Porto) ou pulo com
erro (SulAmérica/Bradesco). A busca desta fase **não lê** `/api/simular-rede/opcoes`
nem `planos_rede_aliases.csv`. Esses arquivos continuam só para a tela Simular
rede.

Um mapa `nome de exibição → nome do portal` só entra em fase posterior, e só
com linha confirmada em ensaio.
