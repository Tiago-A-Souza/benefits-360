# Simular rede — comportamento da tela

Consulta somente leitura da matriz SiscorNet (`#/simular-rede`), fora de qualquer estudo. Nada é gravado.

**Nunca consulta sozinha e nunca assume operadora/plano.** A tela abre vazia, com o aviso verde («Digite um ou mais hospitais/laboratórios» ou «Escolha operadora e plano»). Hospitais e laboratórios, e os modos Por hospital / Por plano / Por laboratório, têm estado próprio: trocar de aba ou de modo limpa busca, filtros e resultado.

**Por hospital / por laboratório:** Enter ou Consultar, mínimo 2 caracteres; vários nomes com `;` ou vírgula. Colunas só dos planos que cobrem o resultado. Busca vazia devolve 422 — não lista a base. Aviso Porto/Medservice só depois de uma consulta que envolva Porto fora de SP/RJ/DF.

**Por plano:** Operadora e plano começam em «Escolha…». Sem os dois, não consulta. Sem filtro geográfico e mais de 100 linhas, pede confirmação.

O card de filtros cresce com o conteúdo (Estado, Município e Zona inteiros). Versão do produto no rodapé: `web/package.json` (não confundir com a versão da API/motor).
