/* Ajuda: como o robô trabalha e o que fazer quando algo sai do normal. */
"use strict";
(function () {
  const { el } = NP;

  const PASSOS = [
    { vaga: "passo_login", titulo: "Guarde o login uma vez", generico: "Na engrenagem do robô (tela Login), guarde o login do portal. Ele fica no cofre do Windows, só neste computador e no seu usuário do Windows. O robô entra no portal sozinho quando precisa." },
    { vaga: "passo_nova", titulo: "Preencha a Nova cotação", generico: "CNPJ, vidas por faixa etária e os planos. As opções do portal vêm da configuração do seu robô." },
    ["Ensaie, se quiser conferir", "No ensaio o robô passa por todas as telas com o primeiro plano e para antes de emitir. Serve para conferir valores sem gerar protocolo."],
    ["Gere as cotações", "O robô emite uma cotação por plano, baixa o PDF de cada uma e copia para a pasta do cliente com o nome de sempre."],
    ["Baixe os PDFs aqui", "Em Cotações ficam todas as cotações feitas, com o PDF a um clique. Não precisa entrar no portal para buscar."],
  ];

  const PERGUNTAS = [
    ["O robô pode emitir a mesma cotação duas vezes?",
      "Sozinho, não. Ele guarda cada cotação emitida (CNPJ, vidas, opções e plano) e pula o que já saiu, mesmo que você peça de novo ou clique em Tentar de novo. Se você quiser emitir de novo de propósito (para testar ou mostrar o robô), clique em Gerar: a tela avisa que a cotação já foi emitida, com o protocolo, e oferece “Emitir de novo mesmo assim”. Sai um protocolo novo e o PDF de antes continua em Cotações. Se o robô clicou em emitir e não viu o protocolo, a cotação fica em “Conferir no portal” e ele não tenta de novo até você conferir."],
    ["Uma cotação ficou em “Conferir no portal”. O que eu faço?",
      "Entre no portal, em Cotações emitidas, e procure pela empresa. Se a cotação saiu, baixe o PDF lá e marque “Saiu: já tenho o PDF” na tela Cotações. Se não saiu, marque “Não saiu: liberar” e peça de novo."],
    ["O robô parou numa tela. E agora?",
      "Abra o pedido (em Cotações ou na faixa escura do topo) e veja o motivo em cada plano. Na maioria das vezes basta clicar em Tentar de novo. Se o mesmo erro se repetir, o portal pode ter mudado: avise quem cuida do robô e mande o registro do pedido."],
    ["Posso usar o computador enquanto o robô trabalha?",
      "Pode. A janela do portal fica escondida e o robô entra sozinho, inclusive se o portal pedir login de novo no meio do caminho. Só não feche a janela preta do Newport Cotações. Se o portal pedir um código de verificação, a faixa dourada no topo pede para você digitar o código que chegou."],
    ["Onde fica a minha senha do portal?",
      "No cofre do Windows (Gerenciador de Credenciais), no seu usuário do Windows. Não vai para planilha, configuração, histórico, registros nem prints, e a tela nunca mostra a senha de volta. Em computador compartilhado, cada corretor entra com o próprio usuário do Windows. Ao sair da Newport, use “Apagar credenciais” na engrenagem do robô."],
    ["O portal recusou a senha. E agora?",
      "O robô para na primeira recusa e não tenta de novo, para não bloquear a sua conta. Confira a senha entrando no portal pelo seu navegador e guarde de novo na engrenagem do robô (tela Login). Se o portal pedir para trocar a senha ou mostrar um captcha, o robô também para e avisa: resolva no seu navegador e tente de novo."],
    { vaga: "sair_do_portal" },
    { vaga: "acesso_ativo" },
    { vaga: "pdfs", generico: ["Onde ficam os PDFs?", "Se você informou a pasta do cliente, uma cópia vai para lá com o nome que a operadora usa. O robô também guarda uma cópia na pasta dele, que é a que você baixa por aqui."] },
    ["Por quanto tempo as coisas ficam guardadas?",
      `Os arquivos que o robô guarda para si (PDFs, prints e registros) são apagados depois de ${NP.estado.retencao_dias || 90} dias. A pasta do cliente nunca é tocada.`],
    ["O robô fecha negócio ou inicia a contratação?",
      "Nunca. Ele só emite a cotação e baixa o PDF. O botão de iniciar a contratação fica sempre com o corretor."],
    { vaga: "configurar", generico: ["Como mudo o que o robô preenche no portal?", "Clique na engrenagem do cartão da operadora (no pé do menu ou em Robôs). Lá estão as telas do portal na ordem em que o robô passa, com o que dá para mudar em cada uma. Mude e clique em Salvar configuração: vale para as próximas cotações. Para uma cotação só, use “Mudar só nesta cotação” na Nova cotação."] },
    { vaga: "versoes" },
  ];

  /* Vagas que cada operadora preenche com o texto dela (Operadora.textos_tela). Sem texto da operadora: o
     genérico, se houver; senão a vaga some. Com mais de uma operadora, cada pergunta leva o nome dela. */
  function passos() {
    return PASSOS.map((p) => {
      if (Array.isArray(p)) return p;
      const textos = NP.estado.operadoras.map((op) => ((op.textos || {})[p.vaga])).filter(Boolean);
      return [p.titulo, textos.length === 1 ? textos[0] : (textos.length ? textos.join(" ") : p.generico)];
    });
  }
  function perguntas() {
    const lista = [];
    for (const p of PERGUNTAS) {
      if (Array.isArray(p)) { lista.push(p); continue; }
      const das = NP.estado.operadoras.map((op) => [op, (((op.textos || {}).perguntas) || {})[p.vaga]]).filter(([, t]) => t);
      if (!das.length && p.generico) lista.push(p.generico);
      for (const [op, [q, r]] of das) lista.push([das.length > 1 || NP.estado.operadoras.length > 1 ? `${op.nome}: ${q}` : q, r]);
    }
    return lista;
  }

  NP.telas.ajuda = async function (conteudo) {
    NP.anexar(conteudo, 
      el("h1", { class: "titulo" }, "Ajuda"),
      el("p", { class: "subtitulo" }, "Como o robô trabalha e o que fazer quando algo sai do normal."),
      el("section", { class: "painel" },
        el("h2", { class: "secao" }, "Do pedido ao PDF"),
        el("ol", { class: "passos" }, passos().map(([t, d]) => el("li", {}, el("strong", {}, t), el("span", { class: "discreto" }, d))))),
      el("section", { class: "painel" },
        el("h2", { class: "secao" }, "Perguntas frequentes"),
        el("div", { class: "perguntas" }, perguntas().map(([p, r]) => el("details", {}, el("summary", {}, p), el("p", {}, r))))),
      NP.estado.simulador ? el("section", { class: "painel" },
        el("h2", { class: "secao" }, "Simulador local"),
        el("p", { class: "discreto" }, "Esta tela está ligada a uma imitação do portal, para treino e testes. Nada é emitido de verdade. O login de treino (falso) já vem guardado, só na memória: o simulador não aceita o login de verdade.")) : null);
  };
})();
