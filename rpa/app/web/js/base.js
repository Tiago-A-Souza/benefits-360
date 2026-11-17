/* Base da tela: chamadas à API, montagem de elementos, formatos, avisos, modal e eventos ao vivo. */
"use strict";
const NP = (window.NP = { telas: {}, estado: { operadoras: [], robo: {}, simulador: false } });

/* ------------------------------------------------------------------ API */
NP.api = async function (metodo, url, corpo, opcoes = {}) {
  const init = { method: metodo, headers: {} };
  if (metodo !== "GET") init.headers["X-Newport-Tela"] = "1";
  if (corpo instanceof FormData) init.body = corpo;
  else if (corpo !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(corpo);
  }
  const resp = await fetch(url, init);
  let dados = null;
  try { dados = await resp.json(); } catch (e) { dados = null; }
  if (!resp.ok && dados && dados.motivo && dados.operadora) NP.faixaProblemaLogin(dados.operadora, dados.motivo, dados.erro);
  if (!resp.ok && !opcoes.aceitarErro) {
    const erro = new Error((dados && dados.erro) || `falha ao falar com a tela (${resp.status})`);
    erro.dados = dados;
    erro.status = resp.status;
    throw erro;
  }
  return dados;
};

/* ------------------------------------------------------------------ DOM */
NP.el = function (tag, attrs, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === undefined || v === null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "style" && typeof v === "object") {
      for (const [p, valor] of Object.entries(v)) {
        if (p.startsWith("--")) e.style.setProperty(p, valor);   // variáveis CSS só entram assim
        else e.style[p] = valor;
      }
    }
    else if (k.startsWith("on") && typeof v === "function") e.addEventListener(k.slice(2), v);
    else if (k === "html") e.innerHTML = v;
    else if (v === true) e.setAttribute(k, "");
    else e.setAttribute(k, v);
  }
  for (const f of filhos.flat(Infinity)) {
    if (f === undefined || f === null || f === false) continue;
    e.appendChild(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return e;
};
NP.limpar = (e) => { while (e.firstChild) e.removeChild(e.firstChild); return e; };
/* Como append, mas ignora null/false (o append do navegador escreveria "null" na tela). */
NP.anexar = (alvo, ...filhos) => {
  for (const f of filhos.flat(Infinity)) {
    if (f === undefined || f === null || f === false) continue;
    alvo.appendChild(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return alvo;
};

/* ------------------------------------------------------------------ formatos */
const _moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
NP.fmt = {
  moeda: (v) => (v === null || v === undefined || v === "" ? "—" : _moeda.format(Number(v))),
  digitos: (t) => String(t || "").replace(/\D/g, ""),
  cpf(t) {
    const d = NP.fmt.digitos(t).slice(0, 11);
    let r = d.slice(0, 3);
    if (d.length > 3) r += "." + d.slice(3, 6);
    if (d.length > 6) r += "." + d.slice(6, 9);
    if (d.length > 9) r += "-" + d.slice(9);
    return r;
  },
  cnpj(t) {
    const d = NP.fmt.digitos(t).slice(0, 14);
    let r = d.slice(0, 2);
    if (d.length > 2) r += "." + d.slice(2, 5);
    if (d.length > 5) r += "." + d.slice(5, 8);
    if (d.length > 8) r += "/" + d.slice(8, 12);
    if (d.length > 12) r += "-" + d.slice(12);
    return r;
  },
  data(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const hoje = new Date();
    const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    if (d.toDateString() === hoje.toDateString()) return `hoje, ${hora}`;
    return `${d.toLocaleDateString("pt-BR")} ${hora}`;
  },
  plural: (n, um, varios) => `${n} ${n === 1 ? um : varios}`,
  quando(iso) {
    if (!iso) return "";
    const d = new Date(iso);
    const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const ontem = new Date(); ontem.setDate(ontem.getDate() - 1);
    if (d.toDateString() === new Date().toDateString()) return `hoje às ${hora}`;
    if (d.toDateString() === ontem.toDateString()) return `ontem às ${hora}`;
    return `${d.toLocaleDateString("pt-BR")} às ${hora}`;
  },
};
NP.cpfValido = function (t) {
  const d = NP.fmt.digitos(t);
  if (d.length !== 11 || /^(\d)\1+$/.test(d)) return false;
  for (const n of [9, 10]) {
    let soma = 0;
    for (let i = 0; i < n; i++) soma += Number(d[i]) * (n + 1 - i);
    if ((soma * 10 % 11) % 10 !== Number(d[n])) return false;
  }
  return true;
};
NP.cnpjValido = function (t) {
  const d = NP.fmt.digitos(t);
  if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
  const calc = (base, pesos) => {
    const r = base.split("").reduce((s, n, i) => s + Number(n) * pesos[i], 0) % 11;
    return r < 2 ? "0" : String(11 - r);
  };
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const d1 = calc(d.slice(0, 12), p1);
  const d2 = calc(d.slice(0, 12) + d1, [6, ...p1]);
  return d.slice(12) === d1 + d2;
};

NP.STATUS = {
  OK: "Emitida", ENSAIO_OK: "Ensaio ok", ERRO: "Não emitida", VERIFICAR: "Conferir no portal", PULADO: "Já emitida antes",
  PARADO: "Parada",
};
NP.selo = (status) => NP.el("span", { class: `selo ${status}` }, NP.STATUS[status] || status);
NP.CONEXAO = {
  desconectado: "Desconectado", abrindo: "Abrindo o portal", entrando: "Entrando no portal",
  aguardando_portal: "Esperando o portal liberar", aguardando_codigo: "Esperando o código", conectado: "Conectado",
  ocupado: "Robô trabalhando", saindo: "Saindo do portal",
};
NP.TRABALHO = {
  na_fila: "Na fila", rodando: "Em andamento", concluido: "Concluído", erro: "Parou com erro",
  cancelado: "Parado", interrompido: "Interrompido (a tela foi fechada)",
};

/* ------------------------------------------------------------------ avisos e modal */
NP.aviso = function (texto, opcoes = {}) {
  const caixa = NP.el("div", { class: `aviso ${opcoes.tipo || ""}`, role: "status" }, NP.el("div", {}, texto));
  if (opcoes.acao) {
    caixa.appendChild(NP.el("button", { class: "botao", type: "button", onclick: () => { opcoes.acao.fazer(); caixa.remove(); } },
      opcoes.acao.texto));
  }
  document.getElementById("avisos").appendChild(caixa);
  setTimeout(() => caixa.remove(), opcoes.duracao || (opcoes.acao ? 12000 : 5000));
};

NP.confirmar = function ({ titulo, texto, ok = "Confirmar", cancelar = "Voltar", principal = true, extra, alternativa }) {
  /* O foco começa em "Voltar" e o botão de confirmar só vale depois de meio segundo: Enter apertado
     duas vezes (ou segurado) ou um clique duplo no botão de origem nunca confirmam uma emissão.
     alternativa: rótulo de um terceiro botão; quem chama recebe "alternativa" (confira com ===). */
  return new Promise((resolver) => {
    const modal = document.getElementById("modal");
    const anterior = document.activeElement;
    const fechar = (valor) => {
      modal.hidden = true; NP.limpar(modal); document.removeEventListener("keydown", tecla, true); resolver(valor);
      if (anterior && anterior.focus) anterior.focus();
    };
    const tecla = (ev) => {
      if (ev.key === "Escape") fechar(false);
      if (ev.repeat) { ev.preventDefault(); ev.stopPropagation(); }
    };
    const botaoOk = NP.el("button", { class: principal ? "botao botao-principal" : "botao botao-escuro", type: "button",
      disabled: true, onclick: () => fechar(true) }, ok);
    const botaoVoltar = NP.el("button", { class: "botao", type: "button", onclick: () => fechar(false) }, cancelar);
    const botaoAlt = alternativa ? NP.el("button", { class: "botao", type: "button", disabled: true,
      onclick: () => fechar("alternativa") }, alternativa) : null;
    NP.anexar(NP.limpar(modal),
      NP.el("div", { class: "modal-caixa", role: "dialog", "aria-modal": "true", "aria-labelledby": "modal-titulo" },
        NP.el("h2", { id: "modal-titulo" }, titulo),
        ...[].concat(texto).map((t) => NP.el("p", {}, t)),
        extra || null,
        NP.el("div", { class: "modal-acoes" }, botaoVoltar, botaoAlt, botaoOk)));
    modal.hidden = false;
    document.addEventListener("keydown", tecla, true);
    botaoVoltar.focus();
    setTimeout(() => { botaoOk.disabled = false; if (botaoAlt) botaoAlt.disabled = false; }, 500);
  });
};

/* ------------------------------------------------------------------ robô: ícone e resumo */
NP.iconeEngrenagem = function (tamanho = 16) {
  const dentes = [0, 45, 90, 135, 180, 225, 270, 315]
    .map((a) => `<rect x="10.3" y="1.4" width="3.4" height="5" rx="1" transform="rotate(${a} 12 12)"/>`).join("");
  return NP.el("span", { class: "icone", "aria-hidden": "true", html:
    `<svg viewBox="0 0 24 24" width="${tamanho}" height="${tamanho}" focusable="false"><g fill="currentColor">`
    + `<path fill-rule="evenodd" d="M12 4.6a7.4 7.4 0 1 0 0 14.8a7.4 7.4 0 1 0 0-14.8zM12 9a3 3 0 1 0 0 6a3 3 0 1 0 0-6z"/>`
    + `${dentes}</g></svg>` });
};

/* "Compulsória, 24 meses, com coparticipação, com Cuidado 360°": como o robô vai preencher o portal.
   valor(chave) devolve o valor de cada campo de cotação marcado "robo" pela operadora. */
NP.resumoDoRobo = function (op, valor, extras = {}) {
  const ordem = { escolha: 0, sim_nao: 1, texto: 2 };
  const campos = ((op && op.campos) || []).filter((c) => c.robo).sort((a, b) => (ordem[a.tipo] ?? 3) - (ordem[b.tipo] ?? 3));
  const partes = [];
  for (const c of campos) {
    const v = valor(c.chave);
    if (c.tipo === "escolha") {
      // O 3º item da opção, quando existe, é a frase do resumo ("com e sem coparticipação (2 cotações por plano)").
      const o = (c.opcoes || []).find((x) => String(x[0]) === String(v)) || [];
      const t = o[2] || o[1];
      if (t) partes.push(t);
    } else if (c.tipo === "sim_nao") partes.push(`${v === "sim" ? "com" : "sem"} ${c.titulo || c.rotulo}`);
    else if (c.tipo === "texto" && v) partes.push(`${c.rotulo.toLowerCase()} ${v}`);
  }
  if (extras.produto) partes.push(`produto ${extras.produto}`);
  const minuscula = (t) => (t.length > 1 && t[1] === t[1].toLowerCase() ? t[0].toLowerCase() + t.slice(1) : t);
  return partes.map((p, i) => (i === 0 ? p : minuscula(p))).join(", ");
};

/* ------------------------------------------------------------------ cotações (peças de várias telas) */
NP.baixar = function (url) {
  const a = NP.el("a", { href: url, download: "", hidden: true });
  document.body.appendChild(a);
  a.click();
  a.remove();
};
NP.baixarPdf = (c) => NP.baixar(`/api/cotacoes/${c.id}/pdf`);
NP.abrirPasta = async function (c) {
  try { await NP.api("POST", `/api/cotacoes/${c.id}/abrir-pasta`); }
  catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
};
NP.empresaDe = (c) => c.razao_social || NP.fmt.cnpj(c.cnpj);
NP.nomeEtapa = function (opId, etapa) {
  const op = NP.operadora(opId);
  const achada = op && op.etapas.find((x) => x.id === etapa);
  return achada ? achada.nome : etapa;
};
NP.FAIXAS = ["0 - 18", "19 - 23", "24 - 28", "29 - 33", "34 - 38", "39 - 43", "44 - 48", "49 - 53", "54 - 58", "59+"];

/* Frase que explica a situação de uma cotação, quando ela precisa de explicação. */
NP.motivo = function (c) {
  const etapa = c.etapa_erro ? NP.nomeEtapa(c.operadora, c.etapa_erro) : "";
  const detalhe = (c.erro || "").split(" | ")[0];
  switch (c.status) {
    case "ERRO":
      return `O robô parou${etapa ? ` na tela ${etapa}` : ""}: ${detalhe}. Pedir de novo é seguro: nada foi emitido.`;
    case "VERIFICAR": {
      const erro = c.erro || "";
      const prot = c.protocolo ? ` (protocolo ${c.protocolo})` : "";
      if (erro.includes("clicou em emitir") || erro.includes("durante a emissão"))
        return "O robô clicou em emitir e não viu o protocolo. Confira no portal, em Cotações emitidas, se esta cotação saiu; a pendência fica no topo de Cotações.";
      if (erro.includes("à mão"))
        return `A cotação saiu no portal${prot}, mas o robô não conseguiu baixar o PDF. Baixe à mão no portal, em Cotações emitidas, e marque como resolvida em Cotações.`;
      return `A cotação saiu no portal${prot}, mas o PDF não veio. O robô tenta baixar de novo na próxima vez que gerar cotações.`;
    }
    case "PULADO":
      return `Esta cotação já tinha sido emitida antes${c.protocolo ? ` (protocolo ${c.protocolo})` : ""}. O robô não emite de novo o que já saiu.`;
    case "PARADO":
      return "Você parou o robô antes desta cotação. Nada foi emitido para ela.";
    default:
      return c.erro ? c.erro : null;
  }
};

/* Versões da cotação de um mesmo plano (a operadora define; ex.: com e sem coparticipação): ficam juntas, na
   ordem que a operadora declara. A segunda leva _mesmoPlano (a tabela desenha as duas como um grupo). */
NP.textoVersao = (c) => ((NP.operadora(c.operadora) || {}).versoes || {})[c.versao] || c.versao || "";
NP.agruparVersoes = function (lista) {
  const grupos = new Map();
  for (const c of lista) {
    const k = [c.trabalho_id, c.cnpj, c.pedido_id, c.plano, c.acomodacao].join("|");
    if (!grupos.has(k)) grupos.set(k, []);
    grupos.get(k).push(c);
  }
  const posicao = (c) => {
    const i = Object.keys((NP.operadora(c.operadora) || {}).versoes || {}).indexOf(c.versao);
    return i < 0 ? 99 : i;
  };
  const saida = [];
  for (const g of grupos.values()) {
    g.sort((a, b) => posicao(a) - posicao(b));
    g.forEach((c, i) => {
      c._mesmoPlano = i > 0 && !!c.versao && !!g[i - 1].versao && c.versao !== g[i - 1].versao;
      saida.push(c);
    });
  }
  return saida;
};

/* Linha da tabela de cotações + linha de detalhes (valores por faixa), que abre e fecha. */
NP.linhasCotacao = function (c, { empresa = false, data = false, selecao = null, cotarDeNovo = false } = {}) {
  const { el, fmt } = NP;
  const valores = c.valores_por_vida || {};
  const temValores = Object.keys(valores).length > 0;
  const motivo = NP.motivo(c);
  const colunas = 5 + (empresa ? 1 : 0) + (data ? 1 : 0) + (selecao ? 1 : 0);
  const detalhe = el("tr", { class: "detalhe", hidden: true },
    el("td", { colspan: colunas },
      el("div", { class: "faixas-detalhe" },
        NP.FAIXAS.filter((f) => valores[f] !== undefined).map((f) =>
          el("div", {}, el("span", {}, `${f} anos `), el("span", { class: "num" }, fmt.moeda(valores[f]))))),
      el("p", { class: "discreto pequeno" }, "Valor mensal por vida em cada faixa.",
        c.total_sem_iof ? ` Total sem IOF ${fmt.moeda(c.total_sem_iof)}, IOF ${fmt.moeda(c.iof)}.` : "")));
  // O valor por faixa abre clicando em "por faixa", embaixo do total: a linha fica com só duas ações.
  const abrirDetalhe = temValores
    ? el("button", { class: "link-pequeno", type: "button", "aria-expanded": "false",
        onclick: (ev) => {
          detalhe.hidden = !detalhe.hidden;
          ev.currentTarget.setAttribute("aria-expanded", String(!detalhe.hidden));
          ev.currentTarget.textContent = detalhe.hidden ? "ver por faixa" : "fechar";
        } }, "ver por faixa")
    : null;
  const acoes = el("div", { class: "acoes-linha" },
    c.tem_pdf ? el("button", { class: "botao botao-pequeno botao-escuro", type: "button", onclick: () => NP.baixarPdf(c) }, "Baixar PDF") : null,
    c.tem_pdf ? el("button", { class: "botao botao-pequeno", type: "button", onclick: () => NP.abrirPasta(c) }, "Abrir pasta") : null);
  let caixa = null;
  if (selecao) {
    caixa = el("input", { type: "checkbox", "aria-label": `Selecionar ${c.plano}`, disabled: !c.tem_pdf });
    caixa.checked = selecao.has(c.id);
    caixa.addEventListener("change", () => { if (caixa.checked) selecao.add(c.id); else selecao.delete(c.id); selecao.aoMudar(); });
  }
  const linha = el("tr", { class: c._mesmoPlano ? "mesmo-plano" : null },
    selecao ? el("td", {}, caixa) : null,
    data ? el("td", { class: "discreto num sem-quebra" }, fmt.data(c.criado_em)) : null,
    empresa ? el("td", { class: "col-empresa" }, el("div", { class: "empresa-nome" }, NP.empresaDe(c)),
      el("div", { class: "discreto pequeno num sem-quebra" }, fmt.cnpj(c.cnpj),
        cotarDeNovo ? el("a", { class: "cotar-de-novo", href: `#/nova?cnpj=${fmt.digitos(c.cnpj)}` }, "cotar de novo") : null)) : null,
    el("td", {}, el("div", { class: "empresa-nome sem-quebra" }, c.plano || "—"),
      el("div", { class: "discreto pequeno" }, c.acomodacao || "",
        c.versao ? el("span", { class: `versao ${c.versao}` }, NP.textoVersao(c)) : null)),
    el("td", { class: "direita num sem-quebra" }, c.total_com_iof ? fmt.moeda(c.total_com_iof) : "—", abrirDetalhe ? el("div", {}, abrirDetalhe) : null),
    el("td", { class: "num" }, c.protocolo || el("span", { class: "discreto" }, "—")),
    el("td", {}, NP.selo(c.status)),
    el("td", {}, acoes));
  const linhas = [linha];
  if (motivo) linhas.push(el("tr", { class: `motivo ${c.status}` }, el("td", { colspan: colunas }, motivo)));
  linhas.push(detalhe);
  return linhas;
};

NP.cabecaCotacoes = function ({ empresa = false, data = false, selecao = null } = {}) {
  const { el } = NP;
  return el("thead", {}, el("tr", {},
    selecao ? el("th", {}, "") : null,
    data ? el("th", {}, "Quando") : null,
    empresa ? el("th", {}, "Empresa") : null,
    el("th", {}, "Plano"), el("th", { class: "direita" }, "Total com IOF"), el("th", {}, "Protocolo"),
    el("th", {}, "Situação"), el("th", {}, el("span", { class: "visualmente-oculto" }, "Ações"))));
};

/* ------------------------------------------------------------------ eventos ao vivo */
NP._ouvintes = new Set();
NP.ouvir = (fn) => { NP._ouvintes.add(fn); return () => NP._ouvintes.delete(fn); };
/* A tela foi atualizada (o servidor reiniciou com código novo): a página aberta ainda tem o JavaScript antigo.
   05/11: "Cotar de novo" mandou a coparticipação antiga porque a aba não tinha sido recarregada. Recarrega sozinha;
   com algo não salvo (ou no meio de uma Nova cotação), só avisa. */
NP.conferirVersao = async function () {
  try {
    const e = await NP.api("GET", "/api/estado");
    if (!NP.estado.versao || !e.versao || e.versao === NP.estado.versao) return;
    const naoSalvo = typeof NP.antesDeSair === "function" && NP.antesDeSair();
    if (naoSalvo || location.hash.startsWith("#/nova")) {
      NP.aviso("O Newport Cotações foi atualizado. Recarregue a página (F5) antes de gerar cotações.", { tipo: "erro", duracao: 60000 });
      return;
    }
    location.reload();
  } catch (erro) { /* tenta de novo na próxima conexão */ }
};

NP.iniciarEventos = function () {
  const fonte = new EventSource("/api/eventos");
  fonte.onopen = () => NP.conferirVersao();   // reconectou (ex.: a tela foi reiniciada)
  fonte.onmessage = (msg) => {
    let ev;
    try { ev = JSON.parse(msg.data); } catch (e) { return; }
    NP._tratarGlobal(ev);
    for (const fn of NP._ouvintes) { try { fn(ev); } catch (e) { console.error(e); } }
  };
};

NP._tratarGlobal = function (ev) {
  const robo = NP.estado.robo;
  if (ev.tipo === "conexao") {
    robo.conexao = robo.conexao || {};
    robo.conexao[ev.operadora] = ev.status;
    NP.desenharConexoes();
    NP._conferirFaixaCodigo();
  }
  if (ev.tipo === "codigo_necessario") {
    robo.conexao = robo.conexao || {};
    robo.conexao[ev.operadora] = "aguardando_codigo";
    if (NP._faixa() === "problema") NP._esconderFaixa();   // o código é o que trava um robô agora
    NP._conferirFaixaCodigo();
  }
  if (ev.tipo === "saiu_do_portal") {
    const op = NP.operadora(ev.operadora);
    NP.aviso(ev.ok ? `O robô saiu do portal${op ? ` da ${op.nome}` : ""} (${ev.motivo}). Na próxima cotação ele entra sozinho.`
      : `O robô fechou a janela do portal (${ev.motivo}), mas não conseguiu sair antes; a sessão expira sozinha no portal.`,
      { tipo: ev.ok ? undefined : "erro" });
  }
  if (ev.tipo === "login_ok" && NP._faixa() !== "problema") {
    NP._conferirFaixaCodigo();                       // o login de uma operadora não esconde o código que outra espera
    if (NP._faixa() !== "codigo") NP._esconderFaixa();
  }
  if (ev.tipo === "login_problema") {
    NP._problemaNoTrabalho = ev.trabalho;
    NP.faixaProblemaLogin(ev.operadora, ev.motivo, ev.mensagem);
    NP.atualizarOperadoras();
  }
  if (ev.tipo === "etapa") { robo.ultima_etapa = ev; NP.faixaTrabalho(); }
  if (ev.tipo === "trabalho") {
    if (ev.status === "rodando") robo.atual = { id: ev.trabalho, titulo: ev.titulo, modo: ev.modo, tipo: ev.tipo_trabalho };
    if (["concluido", "erro", "cancelado"].includes(ev.status)) {
      if (robo.atual && robo.atual.id === ev.trabalho) robo.atual = null;
      NP._conferirFaixaCodigo();
      if (ev.status === "erro" && NP._problemaNoTrabalho !== ev.trabalho)
        NP.aviso(`O robô parou: ${ev.mensagem || "erro"}`, { tipo: "erro", duracao: 9000 });
    }
    NP.faixaTrabalho();
  }
};

NP.operadora = (id) => NP.estado.operadoras.find((o) => o.id === id);

/* Faixa dourada do topo: só para o que é do login do portal (código de verificação ou problema). O robô
   entra sozinho; o corretor nunca mexe na janela do portal. */
NP._faixa = () => { const f = document.getElementById("faixa-login"); return f.hidden ? "" : f.dataset.tipo || ""; };
NP._esconderFaixa = function () {
  const faixa = document.getElementById("faixa-login");
  faixa.hidden = true; faixa.dataset.tipo = ""; faixa.dataset.op = "";
};
NP.faixaLogin = function (conteudo, tipo = "", opId = "") {
  const faixa = document.getElementById("faixa-login");
  if (!conteudo) {
    NP._esconderFaixa();
    NP._conferirFaixaCodigo();      // fechou outra faixa: se algum portal ainda espera o código, o campo volta
    return;
  }
  NP.anexar(NP.limpar(faixa), conteudo);
  faixa.dataset.tipo = tipo;
  faixa.dataset.op = opId;
  faixa.hidden = false;
};

/* A faixa é uma só, mas vários robôs podem rodar juntos. 15/11: com a Amil, a SulAmérica e a Bradesco no mesmo pedido, o
   campo do código da Amil sumia no instante em que o robô de OUTRA operadora mudava de estado (conexao/login_ok), e a
   Amil ficava esperando um código que não havia onde digitar. Agora a faixa do código só some quando a operadora dela
   deixa de esperar o código, e volta se outra ainda espera. */
NP._codigoPendentes = () => Object.entries((NP.estado.robo || {}).conexao || {})
  .filter(([, st]) => st === "aguardando_codigo").map(([opId]) => opId);
NP._conferirFaixaCodigo = function () {
  const faixa = document.getElementById("faixa-login");
  const tipo = NP._faixa();
  if (tipo === "problema") return;                       // o aviso de problema fica até o corretor fechar
  const pendentes = NP._codigoPendentes();
  const mostrando = tipo === "codigo" ? faixa.dataset.op : "";
  if (pendentes.includes(mostrando)) return;             // já mostra o campo de quem espera (não refaz: o corretor pode estar digitando)
  if (pendentes.length) NP.faixaCodigo(pendentes[0]);
  else if (tipo === "codigo") NP._esconderFaixa();
};

NP.faixaCodigo = function (opId) {
  const { el } = NP;
  const op = NP.operadora(opId);
  const campo = el("input", { class: "campo campo-codigo", id: "codigo-verificacao", inputmode: "numeric",
    autocomplete: "one-time-code", maxlength: "12", spellcheck: "false" });
  const botao = el("button", { class: "botao botao-principal", type: "submit" }, "Enviar código");
  const enviar = async (ev) => {
    ev.preventDefault();
    botao.disabled = true;
    try {
      await NP.api("POST", `/api/codigo/${opId}`, { codigo: campo.value });
      NP.faixaLogin(el("div", {}, el("strong", {}, "Código enviado"),
        el("span", { class: "discreto" }, "O robô está entrando no portal com ele.")), "codigo", opId);
    } catch (e) { botao.disabled = false; NP.aviso(e.message, { tipo: "erro" }); campo.focus(); }
  };
  NP.faixaLogin(el("form", { class: "form-codigo", onsubmit: enviar },
    el("div", {},
      el("label", { for: "codigo-verificacao" }, el("strong", {}, "Digite o código que chegou no seu celular/e-mail")),
      el("span", { class: "discreto" }, `O portal da ${op ? op.nome : opId} pediu um código de verificação. O robô digita no portal para você.`)),
    el("div", { class: "acoes-linha" }, campo, botao)), "codigo", opId);
  campo.focus();
};

NP.faixaProblemaLogin = function (opId, motivo, mensagem) {
  const { el } = NP;
  const op = NP.operadora(opId);
  const nome = op ? op.nome : opId;
  const naEngrenagem = ["sem_credenciais", "recusadas", "troca_senha", "senha_comprida"].includes(motivo);
  const titulo = motivo === "sem_credenciais" ? `Cadastre o login da ${nome} na engrenagem do robô`
    : motivo === "recusadas" ? `O portal da ${nome} recusou o login guardado`
    : motivo === "senha_comprida" ? "A senha guardada é maior do que o portal aceita"
    : `O robô não conseguiu entrar no portal da ${nome}`;
  const texto = motivo === "sem_credenciais"
    ? "O robô entra no portal sozinho com o login guardado na engrenagem. Sem ele, nem abre o portal."
    : mensagem || "";
  NP.faixaLogin([
    el("div", {}, el("strong", {}, titulo), el("span", { class: "discreto" }, texto)),
    el("div", { class: "acoes-linha" },
      naEngrenagem ? el("a", { class: "botao botao-escuro", href: `#/robo/${opId}?login=1`, onclick: () => NP.faixaLogin(null) },
        "Abrir a engrenagem") : null,
      el("button", { class: "botao", type: "button", onclick: () => NP.faixaLogin(null) }, "Fechar"))], "problema");
};

NP.faixaTrabalho = function () {
  const faixa = document.getElementById("faixa-trabalho");
  const robo = NP.estado.robo;
  const rotaAtual = location.hash.split("?")[0];
  if (!robo.atual || rotaAtual === `#/andamento/${robo.atual.id}`) { faixa.hidden = true; return; }
  const et = robo.ultima_etapa;
  const op = et ? NP.operadora(et.operadora) : null;
  const nomeEtapa = et && op ? (op.etapas.find((x) => x.id === et.etapa) || {}).nome : null;
  NP.anexar(NP.limpar(faixa), 
    NP.el("span", {}, "Robô trabalhando", et && et.plano ? `: ${et.plano}` : "", nomeEtapa ? ` (tela ${nomeEtapa})` : ""),
    NP.el("a", { href: `#/andamento/${robo.atual.id}` }, "Acompanhar"));
  faixa.hidden = false;
};

/* ------------------------------------------------------------------ trilho: conexões */
/* Testar login: o robô entra no portal sozinho (com o login do cofre) e para na tela de módulos. */
NP.testarLogin = async function (opId) {
  try {
    const r = await NP.api("POST", `/api/conectar/${opId}`);
    NP.aviso("Testando o login: o robô entra no portal sozinho e para na tela de módulos.",
      { acao: { texto: "Acompanhar", fazer: () => NP.ir(`#/andamento/${r.id}`) } });
  } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
};

NP.atualizarOperadoras = async function () {
  try { NP.estado.operadoras = await NP.api("GET", "/api/operadoras"); NP.desenharConexoes(); } catch (e) { /* tenta na próxima */ }
};

/* Botão do cartão: cadastrar o login, atualizar a senha recusada ou testar o login. */
NP.acaoLogin = function (op, st, classe = "botao botao-pequeno") {
  const login = op.login || {};
  if (!login.guardadas) return NP.el("a", { class: classe, href: `#/robo/${op.id}?login=1` }, "Cadastrar o login");
  if (login.recusadas) return NP.el("a", { class: classe, href: `#/robo/${op.id}?login=1` }, "Atualizar a senha");
  if (st === "desconectado") return NP.el("button", { class: classe, type: "button", onclick: () => NP.testarLogin(op.id) }, "Testar login");
  // Logado no portal: libera o login na hora (para usar o portal no navegador). Só com o robô parado.
  if (st === "conectado" || st === "ocupado") {
    const robo = NP.estado.robo || {};
    const livre = st === "conectado" && !robo.atual && !(robo.na_fila || []).length;
    return NP.el("button", { class: classe, type: "button", disabled: !livre,
      title: livre ? "O robô sai do portal e fecha a janela; na próxima cotação ele entra sozinho de novo."
        : "Dá para sair do portal quando o robô parar.",
      onclick: () => NP.sairDoPortal(op.id) }, "Sair do portal agora");
  }
  return null;
};

NP.sairDoPortal = async function (opId) {
  try {
    const r = await NP.api("POST", `/api/sair/${opId}`);
    const quem = ((NP.operadora(opId) || {}).textos || {}).login_livre || "o seu login";
    NP.aviso(r.ja_fora ? "O robô já estava fora do portal."
      : `Saindo do portal: ${quem} fica livre para usar o portal no navegador. Na próxima cotação o robô entra sozinho de novo.`);
  } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
};

NP.desenharConexoes = function () {
  const area = NP.limpar(document.getElementById("conexoes"));
  const conexao = NP.estado.robo.conexao || {};
  for (const op of NP.estado.operadoras) {
    const st = conexao[op.id] || "desconectado";
    area.appendChild(NP.el("div", { class: "conexao" },
      NP.el("div", { class: "conexao-topo" },
        NP.el("span", { class: "conexao-marca", style: { background: op.cor } }), op.nome,
        NP.el("a", { class: "conexao-engrenagem", href: `#/robo/${op.id}`, title: "Configurar o robô",
          "aria-label": `Configurar o robô da ${op.nome}` }, NP.iconeEngrenagem(16))),
      NP.el("div", { class: "conexao-status" }, NP.el("span", { class: `ponto ${st}` }), NP.CONEXAO[st] || st),
      NP.acaoLogin(op, st)));
  }
  // Operadora cujo módulo não carregou: aparece, mas só como indisponível (as outras seguem normais).
  for (const op of NP.estado.indisponiveis || []) {
    area.appendChild(NP.el("div", { class: "conexao indisponivel", title: op.motivo },
      NP.el("div", { class: "conexao-topo" }, NP.el("span", { class: "conexao-marca" }), op.nome),
      NP.el("div", { class: "conexao-status" }, NP.el("span", { class: "ponto" }), "Indisponível")));
  }
};

// Rodapé: o commit que a tela está rodando e, se o código no disco ficou mais novo, o aviso para reiniciar.
NP.desenharVersaoCodigo = function (codigo) {
  const area = NP.limpar(document.getElementById("versao-codigo"));
  if (!codigo) return;
  if (codigo.commit) area.append(NP.el("div", { class: "versao-commit", title: "Versão do código que esta tela está rodando" },
    `Versão ${codigo.commit}` + (codigo.quando ? ` · ${codigo.quando}` : "")));
  if (codigo.mais_novo_no_disco) area.append(NP.el("div", { class: "versao-nova", role: "alert" },
    "Há uma versão mais nova; reinicie a tela"));
};

NP.carregarBase = async function () {
  const [ops, estado] = await Promise.all([NP.api("GET", "/api/operadoras"), NP.api("GET", "/api/estado")]);
  NP.estado.operadoras = ops;
  NP.estado.robo = estado.robo || {};
  NP.estado.simulador = !!estado.simulador;
  NP.estado.pasta_saida = estado.pasta_saida;
  NP.estado.retencao_dias = estado.retencao_dias;
  NP.estado.versao = estado.versao;
  NP.estado.indisponiveis = estado.operadoras_indisponiveis || [];
  document.getElementById("selo-simulador").hidden = !NP.estado.simulador;
  NP.desenharVersaoCodigo(estado.codigo);
  if (!NP._conferirCodigo) NP._conferirCodigo = setInterval(async () => {
    try { NP.desenharVersaoCodigo((await NP.api("GET", "/api/estado")).codigo); } catch (e) { /* tela fora do ar */ }
  }, 60000);
  NP.desenharConexoes();
  NP.faixaTrabalho();
  NP._conferirFaixaCodigo();
};
