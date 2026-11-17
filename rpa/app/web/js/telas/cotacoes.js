/* Cotações: tudo o que o robô já fez, com o PDF a um clique. E as pendências que pedem conferência no portal. */
"use strict";
(function () {
  const { el, fmt } = NP;
  // "Emitidas" é o padrão: é onde o corretor vai buscar o PDF. "Tudo" inclui as repetições ("Já emitida antes").
  const FILTROS = [["OK", "Emitidas"], ["ERRO,VERIFICAR,PARADO", "Não emitidas"], ["ENSAIO_OK", "Ensaios"], ["", "Tudo"]];

  const TEXTO_PENDENCIA = {
    emitindo: "O robô clicou em emitir e não viu o protocolo. Entre no portal, em Cotações emitidas, e veja se esta cotação saiu.",
    emitida: "Saiu no portal, mas o PDF não veio. O robô tenta baixar de novo na próxima vez que você gerar cotações.",
    pdf_manual: "Saiu no portal, mas o robô não conseguiu baixar o PDF. Baixe à mão no portal, em Cotações emitidas.",
  };

  async function resolver(p, acao, aoTerminar) {
    let opcoes;
    if (acao === "liberar") {
      opcoes = {
        titulo: "Liberar para emitir de novo?",
        texto: ["Faça isso só se você conferiu no portal, em Cotações emitidas, que esta cotação não saiu.",
          "Se ela saiu e você liberar, a próxima vez gera uma cotação repetida."],
        ok: "Conferi: não saiu. Liberar", principal: false,
      };
    } else {
      opcoes = {
        titulo: "Marcar como resolvida?",
        texto: ["Use quando a cotação saiu no portal e você já tem o PDF (baixado à mão).",
          "O robô continua sem emitir esta cotação de novo."],
        ok: "Marcar como resolvida",
      };
    }
    if (!(await NP.confirmar(opcoes))) return;
    try {
      await NP.api("POST", acao === "liberar" ? "/api/liberar" : "/api/concluir", { operadora: p.operadora, chave: p.chave });
      NP.aviso(acao === "liberar" ? "Liberada. Peça a cotação de novo quando quiser." : "Pendência resolvida.");
      aoTerminar();
    } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
  }

  NP.telas.cotacoes = async function (conteudo, rota) {
    const estado = { busca: rota.consulta.get("busca") || "", status: rota.consulta.has("status") ? rota.consulta.get("status") : "OK" };
    const selecao = new Set();
    const painelPend = el("section", { class: "painel pendencias", hidden: true });
    const corpo = el("div", {});
    const botaoZip = el("button", { class: "botao botao-escuro", type: "button", hidden: true,
      onclick: () => {
        const ids = [...selecao];
        NP.baixar(ids.length === 1 ? `/api/cotacoes/${ids[0]}/pdf` : `/api/pdfs.zip?ids=${ids.join(",")}`);
      } });
    selecao.aoMudar = () => {
      botaoZip.hidden = selecao.size < 1;
      botaoZip.textContent = selecao.size === 1 ? "Baixar 1 PDF" : `Baixar ${selecao.size} PDFs (.zip)`;
    };

    const busca = el("input", { class: "campo", type: "search", value: estado.busca, "aria-label": "Buscar",
      placeholder: "Buscar por empresa, CNPJ, plano ou protocolo" });
    let atraso = null;
    busca.addEventListener("input", () => { clearTimeout(atraso); atraso = setTimeout(() => { estado.busca = busca.value.trim(); carregar(); }, 250); });
    const segmentos = el("div", { class: "segmentos", role: "group", "aria-label": "Mostrar" },
      FILTROS.map(([v, texto]) => el("button", { type: "button", "aria-pressed": String(v === estado.status),
        onclick: (ev) => {
          estado.status = v;
          segmentos.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === ev.currentTarget)));
          carregar();
        } }, texto)));

    async function carregarPendencias() {
      let lista = [];
      try { lista = await NP.api("GET", "/api/pendencias"); } catch (e) { /* sem pendências visíveis */ }
      NP.limpar(painelPend);
      painelPend.hidden = !lista.length;
      if (!lista.length) return;
      NP.anexar(painelPend, 
        el("h2", { class: "secao" }, lista.length === 1 ? "Uma cotação pede conferência no portal" : `${lista.length} cotações pedem conferência no portal`),
        el("p", { class: "secao-ajuda" }, "Enquanto estiverem aqui, o robô não emite estas cotações de novo. Assim não sai cotação repetida."),
        el("div", { class: "tarefas" }, lista.map((p) => el("div", { class: "tarefa" },
          el("div", {},
            el("strong", {}, `${p.razao_social || fmt.cnpj(p.cnpj)}: ${p.plano}${p.acomodacao ? `, ${p.acomodacao}` : ""}`),
            el("span", { class: "discreto" }, TEXTO_PENDENCIA[p.status] || p.status,
              p.protocolo ? ` Protocolo ${p.protocolo}.` : "")),
          el("div", { class: "acoes-linha" },
            p.status === "emitindo"
              ? el("button", { class: "botao botao-pequeno", type: "button", onclick: () => resolver(p, "liberar", tudo) }, "Não saiu: liberar")
              : null,
            el("button", { class: "botao botao-pequeno", type: "button", onclick: () => resolver(p, "concluir", tudo) },
              p.status === "emitindo" ? "Saiu: já tenho o PDF" : "Já tenho o PDF"))))));
    }

    async function carregar() {
      const q = new URLSearchParams();
      if (estado.busca) q.set("busca", estado.busca);
      if (estado.status) q.set("status", estado.status);
      let lista = [];
      try { lista = await NP.api("GET", `/api/cotacoes?${q}`); } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
      for (const id of [...selecao]) if (!lista.some((c) => c.id === id && c.tem_pdf)) selecao.delete(id);
      selecao.aoMudar();
      NP.limpar(corpo);
      if (!lista.length) {
        const nada = !estado.busca && (!estado.status || estado.status === "OK");
        NP.anexar(corpo, el("div", { class: "vazio" },
          el("p", {}, nada ? "Nenhuma cotação ainda. As cotações que o robô fizer aparecem aqui, com o PDF para baixar."
            : "Nada encontrado com esse filtro."),
          nada ? el("a", { class: "botao botao-principal", href: "#/nova" }, "Fazer a primeira cotação") : null));
        return;
      }
      NP.anexar(corpo, el("div", { class: "tabela-rolagem" }, el("table", { class: "tabela" },
        NP.cabecaCotacoes({ empresa: true, data: true, selecao }),
        el("tbody", {}, NP.agruparVersoes(lista).map((c) => NP.linhasCotacao(c, { empresa: true, data: true, selecao, cotarDeNovo: true }))))),
      lista.length >= 300 ? el("p", { class: "discreto pequeno" }, "Mostrando as 300 mais recentes. Use a busca para achar as mais antigas.") : null);
    }

    function tudo() { carregarPendencias(); carregar(); }

    let timer = null;
    const desligar = NP.ouvir((ev) => {
      if (ev.tipo === "cotacao" || (ev.tipo === "trabalho" && ev.status !== "rodando")) {
        clearTimeout(timer);
        timer = setTimeout(tudo, 400);
      }
    });

    NP.anexar(conteudo, 
      el("h1", { class: "titulo" }, "Cotações"),
      el("p", { class: "subtitulo" }, "Tudo o que o robô já cotou. Baixe o PDF daqui, sem entrar no portal."),
      painelPend,
      el("section", { class: "painel" },
        el("div", { class: "filtros" }, busca, segmentos, el("span", { class: "espaco" }), botaoZip),
        corpo));
    tudo();
    return () => { desligar(); clearTimeout(timer); clearTimeout(atraso); };
  };
})();
