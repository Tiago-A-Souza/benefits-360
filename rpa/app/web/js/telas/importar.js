/* Importar planilha: várias empresas de uma vez, uma linha por empresa. */
"use strict";
(function () {
  const { el, fmt } = NP;

  NP.telas.importar = async function (conteudo) {
    const ops = NP.estado.operadoras;
    // A planilha é de cada operadora (colunas próprias). Com uma só, ela já vem escolhida; com várias, o corretor
    // escolhe antes de enviar, e o modelo baixado é o da operadora escolhida.
    let opId = ops.length === 1 ? ops[0].id : "";
    let resultado = null;
    let nomeArquivo = "";

    const resultadoBox = el("div", { class: "direto" });   // display: contents (a barra de ação desce até o pé da tela)
    const entrada = el("input", { type: "file", accept: ".xlsx", hidden: true, "aria-label": "Planilha .xlsx",
      onchange: (e) => enviar(e.target.files[0]) });
    const textoZona = el("div", {}, el("strong", {}, "Arraste a planilha para cá"),
      el("div", { class: "discreto" }, "ou clique para escolher o arquivo .xlsx"));
    const zona = el("div", { class: "soltar", role: "button", tabindex: "0", "aria-label": "Escolher a planilha",
      onclick: () => entrada.click(),
      onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); entrada.click(); } },
      ondragover: (e) => { e.preventDefault(); zona.classList.add("sobre"); },
      ondragleave: () => zona.classList.remove("sobre"),
      ondrop: (e) => { e.preventDefault(); zona.classList.remove("sobre"); enviar(e.dataTransfer.files[0]); } }, textoZona);

    const modelo = el("a", { href: opId ? `/api/modelo/${opId}` : "#", download: "",
      onclick: (e) => { if (!opId) { e.preventDefault(); NP.aviso("Escolha antes a operadora da planilha.", { tipo: "erro" }); } } },
      "Baixar a planilha modelo");
    const seletorOp = ops.length ? el("div", { class: "segmentos", role: "group", "aria-label": "Operadora" },
      ops.map((o) => el("button", { type: "button", "aria-pressed": String(o.id === opId), onclick: (ev) => {
        opId = o.id;
        modelo.href = `/api/modelo/${opId}`;
        ev.currentTarget.parentNode.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === ev.currentTarget)));
        NP.limpar(resultadoBox); resultado = null;
      } }, o.nome))) : null;

    async function enviar(arquivo) {
      if (!arquivo) return;
      if (!opId) {
        NP.aviso("Escolha antes a operadora da planilha.", { tipo: "erro" });
        return;
      }
      if (!/\.xlsx$/i.test(arquivo.name)) {
        NP.aviso("Escolha uma planilha do Excel (.xlsx).", { tipo: "erro" });
        return;
      }
      const form = new FormData();
      form.append("arquivo", arquivo);
      form.append("operadora", opId);
      zona.setAttribute("aria-busy", "true");
      NP.anexar(NP.limpar(textoZona), el("strong", {}, "Lendo a planilha..."));
      try {
        resultado = await NP.api("POST", "/api/importar", form);
        nomeArquivo = arquivo.name;
        desenhar();
      } catch (e) {
        NP.aviso(e.message, { tipo: "erro", duracao: 10000 });
      } finally {
        entrada.value = "";
        zona.removeAttribute("aria-busy");
        NP.anexar(NP.limpar(textoZona), el("strong", {}, resultado ? "Trocar de planilha" : "Arraste a planilha para cá"),
          el("div", { class: "discreto" }, "ou clique para escolher o arquivo .xlsx"));
      }
    }

    async function gerar(modo) {
      const validos = resultado.validos;
      const n = validos.reduce((a, v) => a + v.cotacoes, 0);
      if (modo === "emitir") {
        const op = NP.operadora(opId);
        const ok = await NP.confirmar({
          titulo: `Gerar ${fmt.plural(n, "cotação", "cotações")} na ${op ? op.nome : "operadora"}?`,
          texto: [`São ${fmt.plural(validos.length, "empresa", "empresas")}. Cada cotação gera um protocolo de verdade no portal.`,
            resultado.erros.length ? `As ${fmt.plural(resultado.erros.length, "linha", "linhas")} com problema ficam de fora.` : "",
            "O robô entra no portal sozinho, com o login guardado na engrenagem."].filter(Boolean),
          ok: `Gerar ${fmt.plural(n, "cotação", "cotações")}`,
        });
        if (!ok) return;
      }
      try {
        const r = await NP.api("POST", "/api/trabalhos", { modo, confirmado: modo === "emitir",
          itens: [{ operadora: opId, pedidos: validos.map((v) => v.dados) }] });
        NP.ir(`#/andamento/${r.id}`);
      } catch (e) {
        if (e.dados && e.dados.problemas) {
          NP.aviso(`Algumas linhas não passaram: ${Object.keys(e.dados.problemas).join(", ")}. Corrija na planilha e importe de novo.`, { tipo: "erro", duracao: 12000 });
        } else NP.aviso(e.message, { tipo: "erro" });
      }
    }

    function desenhar() {
      NP.limpar(resultadoBox);
      const { validos, erros } = resultado;
      const n = validos.reduce((a, v) => a + v.cotacoes, 0);
      const resumo = [fmt.plural(validos.length, "empresa pronta", "empresas prontas")];
      if (erros.length) resumo.push(fmt.plural(erros.length, "linha com problema", "linhas com problema"));
      const painel = el("section", { class: "painel" },
        el("div", { class: "painel-cabeca" }, el("h2", { class: "secao" }, nomeArquivo), el("span", { class: "discreto" }, resumo.join(", "))));
      if (erros.length) {
        NP.anexar(painel, el("div", { class: "problemas" },
          el("strong", {}, "Estas linhas ficam de fora até você corrigir na planilha:"),
          el("ul", {}, erros.map((e) => el("li", {}, `Linha ${e.linha}${e.id && !/^L\d+$/.test(e.id) ? ` (${e.id})` : ""}: ${e.problemas.join("; ")}`)))));
      }
      if (validos.length) {
        const textoPlanos = (t) => String(t || "").replace(/;\s*/g, ", ")
          .replace(/menor[\s_]*preco(:(\d+))?/i, (m, a, q) => `os ${q || 1} mais baratos`);
        const linhaValida = (v) => el("tr", {},
          el("td", { class: "num discreto" }, String(v.linha)),
          el("td", { class: "empresa-nome" }, /^L\d+$/.test(v.id) ? "—" : v.id),
          el("td", { class: "num" }, fmt.cnpj(v.cnpj)),
          el("td", { class: "direita num" }, String(v.vidas)),
          el("td", { class: "direita num" }, String(v.cotacoes)),
          el("td", { class: "discreto pequeno" }, textoPlanos(v.dados.planos)));
        const cabeca = el("thead", {}, el("tr", {}, el("th", {}, "Linha"), el("th", {}, "Empresa"), el("th", {}, "CNPJ"),
          el("th", { class: "direita" }, "Vidas"), el("th", { class: "direita" }, "Cotações"), el("th", {}, "Planos")));
        NP.anexar(painel, el("div", { class: "tabela-rolagem" },
          el("table", { class: "tabela" }, cabeca, el("tbody", {}, validos.map(linhaValida)))));
      } else {
        NP.anexar(painel, el("p", { class: "discreto" }, "Nenhuma linha está pronta para cotar."));
      }
      NP.anexar(resultadoBox, painel);
      if (validos.length) {
        NP.anexar(resultadoBox, el("div", { class: "barra-acao" },
          el("div", { class: "resumo" }, `${fmt.plural(n, "cotação", "cotações")} em ${fmt.plural(validos.length, "empresa", "empresas")}`),
          el("div", { class: "acoes" },
            el("button", { class: "botao", type: "button", onclick: () => gerar("ensaio") }, "Ensaiar sem emitir"),
            el("button", { class: "botao botao-principal", type: "button", onclick: () => gerar("emitir") }, `Gerar ${fmt.plural(n, "cotação", "cotações")}`))));
      }
    }

    NP.anexar(conteudo, 
      el("h1", { class: "titulo" }, "Importar planilha"),
      el("p", { class: "subtitulo" }, "Para cotar várias empresas de uma vez. Uma linha por empresa, no formato da planilha modelo. O robô confere tudo antes de começar."),
      el("section", { class: "painel" },
        seletorOp ? el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "Operadora"), el("div", {}, seletorOp)) : null,
        zona, entrada,
        el("p", { class: "discreto pequeno", style: { marginTop: "12px" } }, modelo, ". A aba “como_preencher” explica cada coluna.")),
      resultadoBox);
  };
})();
