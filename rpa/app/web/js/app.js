/* Navegação entre as telas (#/inicio, #/nova, #/andamento/12, ...). */
"use strict";
(function () {
  let limparTela = null;

  function rota() {
    const [caminho, consulta] = (location.hash.replace(/^#\/?/, "") || "inicio").split("?");
    const [nome, ...resto] = caminho.split("/");
    return { nome: nome || "inicio", param: resto.join("/"), consulta: new URLSearchParams(consulta || "") };
  }

  const MENU_DA_ROTA = { andamento: "cotacoes", robo: "robos", ajustes: "robos" };
  let vez = 0;
  let hashMostrado = location.hash;
  async function mostrar(opcoes = {}) {
    const minhaVez = ++vez;
    const r = rota();
    if (r.nome === "ajustes") { location.replace("#/robos"); return; }   // nome antigo da tela
    hashMostrado = location.hash;
    const tela = NP.telas[r.nome] || NP.telas.inicio;
    const rolagem = window.scrollY;
    if (typeof limparTela === "function") { try { limparTela(); } catch (e) { console.error(e); } }
    limparTela = null;
    document.querySelectorAll(".menu a").forEach((a) => {
      const ativo = a.dataset.rota === (MENU_DA_ROTA[r.nome] || r.nome);
      a.classList.toggle("ativo", ativo);
      if (ativo) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    const conteudo = document.getElementById("conteudo");
    const nova = NP.el("div", { class: "tela" });
    NP.faixaTrabalho();
    let limpeza = null;
    try {
      limpeza = await tela(nova, r);
    } catch (e) {
      console.error(e);
      nova.appendChild(NP.el("div", { class: "painel" },
        NP.el("h1", { class: "titulo" }, "Não consegui abrir esta tela"),
        NP.el("p", { class: "discreto" }, e.message, ". Confira se a janela preta do Newport Cotações continua aberta e recarregue a página.")));
    }
    if (minhaVez !== vez) {   // a pessoa já foi para outra tela enquanto esta carregava
      if (typeof limpeza === "function") limpeza();
      return;
    }
    limparTela = limpeza;
    NP.limpar(conteudo).appendChild(nova);   // troca de uma vez, sem a tela piscar vazia
    if (opcoes.manterRolagem) { window.scrollTo(0, rolagem); return; }
    const foco = nova.querySelector("[data-foco]");
    if (foco) foco.focus(); else conteudo.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }

  NP.ir = (hash) => { if (location.hash === hash) mostrar(); else location.hash = hash; };
  NP.recarregar = () => mostrar({ manterRolagem: true });

  /* Uma tela com mudanças não salvas (ex.: configuração do robô) define NP.antesDeSair, que devolve
     o aviso. Ao trocar de tela, a pessoa confirma antes de perder as mudanças. */
  NP.antesDeSair = null;
  async function aoTrocarDeTela() {
    const aviso = typeof NP.antesDeSair === "function" ? NP.antesDeSair() : "";
    if (!aviso) { mostrar(); return; }
    const destino = location.hash;
    history.replaceState(null, "", hashMostrado || "#/inicio");   // fica na tela até a pessoa decidir
    const sair = await NP.confirmar({ titulo: "Sair sem salvar?", texto: [aviso], ok: "Sair sem salvar",
      cancelar: "Continuar aqui", principal: false });
    if (sair) { NP.antesDeSair = null; location.hash = destino; }
  }
  window.addEventListener("hashchange", aoTrocarDeTela);
  window.addEventListener("beforeunload", (ev) => {
    if (typeof NP.antesDeSair === "function" && NP.antesDeSair()) { ev.preventDefault(); ev.returnValue = ""; }
  });
  window.addEventListener("DOMContentLoaded", async () => {
    try {
      await NP.carregarBase();
    } catch (e) {
      NP.aviso("Não consegui falar com o robô. A janela do Newport Cotações está aberta?", { tipo: "erro", duracao: 15000 });
    }
    NP.iniciarEventos();
    NP.ouvir((ev) => {
      if (ev.tipo === "catalogo") NP.api("GET", "/api/operadoras").then((ops) => { NP.estado.operadoras = ops; }).catch(() => {});
    });
    mostrar();
  });
})();
