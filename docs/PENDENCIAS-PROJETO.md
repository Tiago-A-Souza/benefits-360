# Pendências do projeto

Registro operacional de itens abertos (testes intermitentes, decisões adiadas, dívidas conhecidas). Uma linha por item.

- `tests/bradesco/test_bradesco_simulador.py::test_parar_so_entre_telas_e_nunca_durante_o_calculo` falhou 1 vez em 192 na suíte cheia (17/11), 20/20 isolado; intermitente, causa não provada, sem relação com a aba (zero diff no Bradesco).
- Cotações nativa: Início, Ajuda, Importar planilha e Robôs/engrenagem (configuração tela a tela, prints, janela, pasta) ainda abrem o robô antigo (`127.0.0.1:8600/#/...`) em outra aba.
- Proposta (não implementada): conferir versão do robô no SSE (banner pedindo F5 se o JS da nativa ficou atrás) e, quando o Benefits for hospedado, faixa de versões do robô local compatíveis com aquele Benefits.