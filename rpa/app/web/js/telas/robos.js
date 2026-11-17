/* Robôs: um cartão por operadora, com a engrenagem que abre a configuração dele, e os ajustes gerais. */
"use strict";
(function () {
  const { el } = NP;

  function chave(rotulo, marcado, aoMudar) {
    const entrada = el("input", { type: "checkbox", onchange: (e) => aoMudar(e.target.checked) });
    entrada.checked = marcado;
    return el("label", { class: "chave" }, entrada, el("span", { class: "chave-trilho" }), el("span", {}, rotulo));
  }

  NP.telas.robos = async function (conteudo) {
    const geral = await NP.api("GET", "/api/geral").catch(() => ({ geral: {}, pasta_saida: "", retencao_dias: 90 }));
    const conexao = NP.estado.robo.conexao || {};

    const cartoes = NP.estado.operadoras.map((op) => {
      const st = conexao[op.id] || "desconectado";
      const padrao = (c) => (op.campos.find((x) => x.chave === c) || {}).padrao;
      return el("article", { class: "robo-cartao", style: { "--cor-op": op.cor } },
        el("div", { class: "robo-cartao-topo" },
          el("div", {}, el("h2", { class: "operadora-nome" }, op.nome), el("div", { class: "operadora-produto" }, op.produto)),
          el("a", { class: "botao-icone", href: `#/robo/${op.id}`, "aria-label": `Configurar o robô da ${op.nome}`, title: "Configurar o robô" },
            NP.iconeEngrenagem(20))),
        el("p", { class: "robo-cartao-resumo" }, NP.resumoDoRobo(op, padrao, { produto: op.produto_portal }), "."),
        el("div", { class: "robo-cartao-pe" },
          el("span", { class: "conexao-status", style: { color: "var(--texto-2)", margin: 0 } }, el("span", { class: `ponto ${st}` }), NP.CONEXAO[st]),
          el("div", { class: "acoes-linha" },
            NP.acaoLogin(op, st),
            el("a", { class: "botao botao-pequeno botao-escuro", href: `#/robo/${op.id}` }, "Configurar"))));
    });

    for (const op of NP.estado.indisponiveis || []) {
      cartoes.push(el("article", { class: "robo-cartao indisponivel" },
        el("div", { class: "robo-cartao-topo" }, el("div", {}, el("h2", { class: "operadora-nome" }, op.nome),
          el("div", { class: "operadora-produto" }, "Indisponível"))),
        el("p", { class: "robo-cartao-resumo" }, "O robô desta operadora não carregou. As outras operadoras funcionam normalmente. ",
          el("span", { class: "discreto pequeno" }, `Motivo: ${op.motivo}`))));
    }

    const painelGeral = el("section", { class: "painel" },
      el("h2", { class: "secao" }, "Para todos os robôs"),
      el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "Prints das telas"),
        el("div", {}, chave("Guardar print de cada tela do portal", !!geral.geral.mapear, async (v) => {
          try { await NP.api("PUT", "/api/geral", { geral: { mapear: v } }); NP.aviso(v ? "Prints ligados." : "Prints desligados."); }
          catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
        }), el("div", { class: "ajuda" }, "Só para ajustar o robô quando o portal muda. Deixe desligado no dia a dia."))),
      el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "Janela do portal"),
        el("div", {}, chave("Mostrar a janela do portal (para calibrar)", !!geral.geral.modo_visual, async (v) => {
          try {
            await NP.api("PUT", "/api/geral", { geral: { modo_visual: v } });
            NP.aviso(v ? "A janela do portal aparece a partir da próxima vez que o robô abrir o portal."
              : "A janela do portal fica escondida a partir da próxima vez que o robô abrir o portal.");
          } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
        }), el("div", { class: "ajuda" }, "Opção técnica. No dia a dia fica desligada: o robô entra e trabalha no portal sem "
          + "aparecer. Se o portal já estiver aberto, feche a tela (janela preta) e abra de novo para valer."))),
      el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "Pasta do robô"),
        el("div", {}, el("div", { class: "num pequeno", style: { paddingTop: "9px", wordBreak: "break-all" } }, geral.pasta_saida),
          el("div", { class: "ajuda" }, "Guarda a sessão do portal, os PDFs, o histórico e o registro que impede cotação repetida. "
            + `Arquivos do robô com mais de ${geral.retencao_dias || 90} dias são apagados sozinhos.`))));

    NP.anexar(conteudo,
      el("h1", { class: "titulo" }, "Robôs"),
      el("p", { class: "subtitulo" }, "Cada operadora tem o seu robô. A engrenagem mostra tudo o que ele preenche no portal, "
        + "tela por tela, e deixa você mudar. A configuração fica neste computador: é a do seu robô."),
      el("div", { class: "robos" }, cartoes),
      painelGeral);
  };
})();
