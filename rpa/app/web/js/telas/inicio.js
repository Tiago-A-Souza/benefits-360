/* Início: o que dá para fazer agora, as empresas de sempre e as últimas cotações. */
"use strict";
(function () {
  const { el, fmt } = NP;

  function saudacao() {
    const h = new Date().getHours();
    return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
  }

  function tarefa({ titulo, texto, acao, destaque = false }) {
    return el("div", { class: `tarefa ${destaque ? "destaque" : ""}` },
      el("div", {}, el("strong", {}, titulo), el("span", { class: "discreto" }, texto)), acao);
  }

  NP.telas.inicio = async function (conteudo) {
    const [cotacoes, pendencias, empresas] = await Promise.all([
      NP.api("GET", "/api/cotacoes?limite=8&status=OK,ERRO,VERIFICAR,PARADO").catch(() => []),
      NP.api("GET", "/api/pendencias").catch(() => []),
      NP.api("GET", "/api/empresas").catch(() => []),
    ]);
    const robo = NP.estado.robo;
    const ops = NP.estado.operadoras;

    const tarefas = el("div", { class: "tarefas" });
    if (robo.atual) {
      NP.anexar(tarefas, tarefa({ destaque: true, titulo: `Robô trabalhando: ${robo.atual.titulo || "pedido"}`,
        texto: robo.atual.modo === "ensaio" ? "Ensaio, sem emitir." : "Emitindo as cotações no portal.",
        acao: el("a", { class: "botao botao-escuro", href: `#/andamento/${robo.atual.id}` }, "Acompanhar") }));
    }
    if (pendencias.length) {
      NP.anexar(tarefas, tarefa({ titulo: pendencias.length === 1 ? "Uma cotação pede conferência no portal" : `${pendencias.length} cotações pedem conferência no portal`,
        texto: "O robô não emite essas de novo até você conferir.",
        acao: el("a", { class: "botao", href: "#/cotacoes" }, "Conferir") }));
    }
    NP.anexar(tarefas, 
      tarefa({ destaque: !robo.atual, titulo: "Cotar uma empresa",
        texto: "CNPJ, vidas por faixa e planos. O robô faz o resto no portal.",
        acao: el("a", { class: "botao botao-principal", href: "#/nova" }, "Nova cotação") }),
      tarefa({ titulo: "Cotar várias empresas de uma vez", texto: "Uma linha por empresa, na planilha modelo.",
        acao: el("a", { class: "botao", href: "#/importar" }, "Importar planilha") }));
    for (const op of ops) {
      const login = op.login || {};
      if (login.guardadas && !login.recusadas) continue;
      NP.anexar(tarefas, tarefa({ destaque: true,
        titulo: login.guardadas ? `O portal da ${op.nome} recusou o login guardado` : `Cadastre o login da ${op.nome}`,
        texto: login.guardadas ? "O robô não tenta de novo até você guardar a senha outra vez, para não bloquear a sua conta."
          : "Uma vez só, na engrenagem do robô. O robô entra no portal sozinho com ele; fica no cofre do Windows deste computador.",
        acao: el("a", { class: "botao botao-escuro", href: `#/robo/${op.id}?login=1` }, login.guardadas ? "Atualizar a senha" : "Cadastrar o login") }));
    }

    const listaEmpresas = empresas.slice(0, 6);
    const painelEmpresas = el("section", { class: "painel" },
      el("h2", { class: "secao" }, "Empresas recentes"),
      listaEmpresas.length
        ? el("ul", { class: "empresas" }, listaEmpresas.map((e) => el("li", {},
          el("div", {}, el("div", { class: "empresa-nome" }, e.apelido || e.razao_social || fmt.cnpj(e.cnpj)),
            el("div", { class: "discreto pequeno num" }, e.apelido && e.razao_social ? `${e.razao_social}, ` : "", fmt.cnpj(e.cnpj))),
          el("a", { class: "botao botao-pequeno", href: `#/nova?cnpj=${fmt.digitos(e.cnpj)}` }, "Cotar de novo"))))
        : el("p", { class: "discreto" }, "As empresas que você cotar aparecem aqui, para repetir a cotação com os mesmos dados."));

    const painelUltimas = el("section", { class: "painel" },
      el("div", { class: "painel-cabeca" }, el("h2", { class: "secao" }, "Últimas cotações"),
        cotacoes.length ? el("a", { href: "#/cotacoes" }, "Ver todas") : null),
      cotacoes.length
        ? el("div", { class: "tabela-rolagem" }, el("table", { class: "tabela" }, NP.cabecaCotacoes({ empresa: true, data: true }),
          el("tbody", {}, NP.agruparVersoes(cotacoes).map((c) => NP.linhasCotacao(c, { empresa: true, data: true })))))
        : el("p", { class: "discreto" }, "Ainda não há cotações. Quando o robô terminar a primeira, o PDF fica aqui para baixar."));

    NP.anexar(conteudo, 
      el("h1", { class: "titulo" }, saudacao()),
      el("p", { class: "subtitulo" }, "O robô preenche o portal, emite uma cotação por plano e guarda os PDFs. Você escolhe a empresa e os planos."),
      el("div", { class: "colunas" }, el("section", { class: "painel" }, el("h2", { class: "secao" }, "O que fazer agora"), tarefas), painelEmpresas),
      painelUltimas);

    const desligar = NP.ouvir((ev) => {
      if (ev.tipo === "cotacao" || ev.tipo === "trabalho" || ev.tipo === "conexao") {
        clearTimeout(NP._inicioTimer);
        NP._inicioTimer = setTimeout(() => {
          if (location.hash === "" || location.hash.startsWith("#/inicio")) NP.recarregar();
        }, 600);
      }
    });
    return () => { desligar(); clearTimeout(NP._inicioTimer); };
  };
})();
