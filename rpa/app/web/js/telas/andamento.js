/* Andamento de um trabalho: o que o robô está fazendo agora e as cotações que já saíram. */
"use strict";
(function () {
  const { el, fmt } = NP;

  function hora(iso) {
    return iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
  }

  function contar(cotacoes) {
    const n = {};
    for (const c of cotacoes) n[c.status] = (n[c.status] || 0) + 1;
    return n;
  }

  const CONFIRMACOES = {
    gerar: { titulo: "Gerar as cotações de verdade?", ok: "Gerar as cotações",
      texto: ["O robô repete o pedido e emite uma cotação por plano no portal da operadora, com protocolo.",
        "O que já foi emitido antes não sai de novo."] },
    continuar: { titulo: "Continuar de onde parou?", ok: "Continuar",
      texto: ["O robô emite as cotações que faltaram.", "As que já saíram não saem de novo."] },
    tentar: { titulo: "Tentar de novo?", ok: "Tentar de novo",
      texto: ["O robô tenta de novo as cotações que não saíram.", "As que já saíram não saem de novo."] },
  };

  async function repetir(t, modo, motivo = "gerar") {
    if (modo === "emitir" && !(await NP.confirmar(CONFIRMACOES[motivo] || CONFIRMACOES.gerar))) return;
    try {
      const r = await NP.api("POST", `/api/trabalhos/${t.id}/repetir`, { modo, confirmado: modo === "emitir" });
      NP.ir(`#/andamento/${r.id}`);
    } catch (e) {
      if (e.dados && e.dados.problemas) {
        NP.aviso("Os dados deste pedido não passam mais na conferência. Abra a Nova cotação e confira.", { tipo: "erro", duracao: 9000 });
      } else NP.aviso(e.message, { tipo: "erro" });
    }
  }

  async function parar(t) {
    const naFila = t.status === "na_fila";
    const ok = await NP.confirmar({
      titulo: naFila ? "Tirar este pedido da fila?" : "Parar o robô?",
      texto: naFila ? ["O robô não vai começar este pedido."]
        : ["O robô para na próxima troca de tela e não emite mais nada.",
          "Se uma cotação já estiver sendo emitida, ela termina antes, com o PDF."],
      ok: naFila ? "Tirar da fila" : "Parar o robô",
      principal: false,
    });
    if (!ok) return;
    try {
      const r = await NP.api("POST", `/api/trabalhos/${t.id}/parar`);
      if (!r.ok) NP.aviso("Este pedido já terminou ou já começou: veja a situação abaixo.", { tipo: "erro" });
      else NP.aviso(naFila ? "Pedido tirado da fila." : "Pedido de parada enviado. O robô para na próxima tela.");
    } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
  }

  NP.telas.andamento = async function (conteudo, rota) {
    const tid = Number(rota.param);
    let t;
    try {
      t = await NP.api("GET", `/api/trabalhos/${tid}`);
    } catch (e) {
      NP.anexar(conteudo, el("h1", { class: "titulo" }, "Pedido não encontrado"),
        el("p", { class: "subtitulo" }, "Ele pode ter sido apagado. As cotações feitas continuam na lista."),
        el("a", { class: "botao", href: "#/cotacoes" }, "Ver as cotações"));
      return null;
    }

    const robo = NP.estado.robo;
    let etapa = robo.atual && robo.atual.id === tid ? robo.ultima_etapa : null;
    let pedidoAtual = null;

    const cabeca = el("div", {});
    const painelRobo = el("section", { class: "painel painel-robo", "aria-live": "polite" });
    const painelCot = el("section", { class: "painel" });
    const registro = el("div", { class: "registro", role: "log" });
    const painelLog = el("section", { class: "painel" },
      el("details", {}, el("summary", {}, "Ver o registro do robô, linha a linha"), registro));

    function opDoTrabalho() {
      const id = (etapa && etapa.operadora) || (t.operadoras || [])[0];
      return NP.operadora(id) || NP.estado.operadoras[0];
    }

    function desenharCabeca() {
      const quando = fmt.quando(t.criado_em);
      const qtd = t.total_cotacoes ? fmt.plural(t.total_cotacoes, "cotação", "cotações") : "";
      const empresas = t.total_pedidos > 1 ? ` em ${t.total_pedidos} empresas` : "";
      let texto = `Pedido ${quando}`;
      if (t.tipo === "conectar") texto = `Teste do login no portal, pedido ${quando}`;
      else if (t.modo === "ensaio") texto = `Ensaio, sem emitir${t.total_pedidos > 1 ? `, de ${t.total_pedidos} empresas` : ""}. Pedido ${quando}.`;
      else texto = `Emissão de ${qtd}${empresas}. Pedida ${quando}.`;
      NP.anexar(NP.limpar(cabeca),
        el("h1", { class: "titulo" }, t.titulo || "Pedido"),
        el("p", { class: "subtitulo" }, texto));
    }

    function etapasEmPilulas(op) {
      const atual = etapa ? op.etapas.findIndex((x) => x.id === etapa.etapa) : -1;
      return el("ol", { class: "etapas", "aria-label": "Telas do portal" },
        op.etapas.map((x, i) => el("li", { class: i < atual ? "feita" : i === atual ? "atual" : "",
          "aria-current": i === atual ? "step" : null }, x.nome)));
    }

    function desenharRobo() {
      NP.limpar(painelRobo);
      const op = opDoTrabalho();
      const n = contar(t.cotacoes);
      const feitas = t.cotacoes.length;
      const botoes = el("div", { class: "acoes-robo" });

      if (t.status === "na_fila") {
        NP.anexar(painelRobo, el("h2", { class: "secao" }, "Na fila"),
          el("p", { class: "discreto" }, "O robô começa assim que terminar o pedido anterior."));
        NP.anexar(botoes, el("button", { class: "botao", type: "button", onclick: () => parar(t) }, "Tirar da fila"));
      } else if (t.status === "rodando") {
        const conexao = op ? (robo.conexao || {})[op.id] : "";
        let titulo = "O robô está no portal";
        let linha = "Abrindo o portal";
        if (conexao === "aguardando_codigo") {
          titulo = "Esperando o código de verificação";
          linha = "Digite na faixa do topo o código que o portal mandou para o seu celular/e-mail.";
        } else if (conexao === "aguardando_portal") {
          titulo = "Esperando o portal liberar o acesso";
          linha = ((op && op.textos) || {}).aguardando_portal
            || "O portal ainda tem uma sessão aberta para este login (outro navegador ou uma janela fechada). "
            + "O robô entra de novo sozinho em instantes; não precisa fazer nada.";
        } else if (conexao === "entrando") {
          titulo = "Entrando no portal";
          linha = `O robô entra sozinho na ${op.nome}, com o login guardado na engrenagem.`;
        } else if (etapa) {
          const nomeTela = NP.nomeEtapa(etapa.operadora, etapa.etapa);
          if (etapa.plano) {
            const [plano, acomod] = etapa.plano.split(" | ");
            titulo = `Cotando ${plano}${acomod ? `, ${acomod}` : ""}`;
            if (etapa.total > 1) titulo += ` (plano ${etapa.indice + 1} de ${etapa.total})`;
          } else if (etapa.etapa === "planos") {
            titulo = "Escolhendo os planos mais baratos";
          }
          linha = `Tela ${nomeTela}${pedidoAtual && t.total_pedidos > 1 ? `, empresa ${pedidoAtual}` : ""}`;
        }
        NP.anexar(painelRobo, 
          el("h2", { class: "secao agora-titulo" }, titulo),
          el("p", { class: "agora discreto" }, linha),
          t.tipo === "cotar" && op ? etapasEmPilulas(op) : null,
          t.tipo === "cotar" && t.total_cotacoes > 1
            ? el("p", { class: "discreto pequeno" }, `${feitas} de ${fmt.plural(t.total_cotacoes, "cotação pronta", "cotações prontas")}`) : null);
        NP.anexar(botoes, el("button", { class: "botao botao-perigo", type: "button", onclick: () => parar(t) }, "Parar o robô"));
      } else if (t.tipo === "conectar") {
        const ok = t.status === "concluido";
        NP.anexar(painelRobo, el("h2", { class: "secao" }, ok ? `Login ok na ${op ? op.nome : "operadora"}` : "O login não deu certo"),
          el("p", { class: "discreto" }, ok ? "O robô entrou no portal e parou na tela de módulos, sem cotar. As próximas cotações usam esta sessão."
            : t.mensagem || "O robô não conseguiu entrar no portal."));
        if (ok) NP.anexar(botoes, el("a", { class: "botao botao-principal", href: "#/nova" }, "Nova cotação"));
        else if (op) NP.anexar(botoes, el("a", { class: "botao botao-escuro", href: `#/robo/${op.id}?login=1` }, "Abrir a engrenagem"));
      } else if (t.status === "concluido") {
        const pendentes = (n.ERRO || 0) + (n.VERIFICAR || 0) + (n.PARADO || 0);
        if (t.modo === "ensaio") {
          const okEnsaio = n.ENSAIO_OK || 0;
          NP.anexar(painelRobo, 
            el("h2", { class: "secao" }, okEnsaio && !pendentes ? "Ensaio concluído" : "O ensaio encontrou problemas"),
            el("p", { class: "discreto" }, okEnsaio && !pendentes
              ? "O robô percorreu as telas com o primeiro plano de cada empresa e parou antes de emitir. Se os valores abaixo batem com o que você espera, gere as cotações."
              : "Veja o motivo em cada linha abaixo. Nada foi emitido."));
          if (okEnsaio) NP.anexar(botoes, el("button", { class: "botao botao-principal", type: "button", onclick: () => repetir(t, "emitir") }, "Gerar as cotações"));
          NP.anexar(botoes, el("button", { class: "botao", type: "button", onclick: () => repetir(t, "ensaio") }, "Ensaiar de novo"));
        } else {
          const emitidas = n.OK || 0;
          const puladas = n.PULADO || 0;
          const pdfs = t.cotacoes.filter((c) => c.tem_pdf).length;
          const naPasta = t.cotacoes.find((c) => c.pdf_destino && c.tem_pdf);
          const soPuladas = !emitidas && !pendentes && puladas > 0 && puladas === t.cotacoes.length;
          let titulo = emitidas ? `Pronto: ${fmt.plural(emitidas, "cotação emitida", "cotações emitidas")}` : "Nenhuma cotação nova";
          if (soPuladas) titulo = puladas === 1 ? "Esta cotação já tinha sido emitida" : "Estas cotações já tinham sido emitidas";
          if (pendentes) titulo = `${fmt.plural(pendentes, "cotação ficou", "cotações ficaram")} sem emitir`;
          let texto = "Veja a situação de cada plano abaixo.";
          if (pendentes) texto = "Veja o motivo em cada linha. Pedir de novo é seguro: o robô não repete o que já foi emitido.";
          else if (soPuladas) texto = "Sozinho, o robô não emite de novo a mesma cotação (mesma empresa, vidas, opções e plano): ele entrou no portal, "
            + "conferiu e terminou. O PDF de antes está abaixo. Para emitir de novo de propósito (teste ou demonstração), "
            + "clique em Cotar de novo, depois em Gerar e, no aviso, em “Emitir de novo mesmo assim”.";
          else if (naPasta) texto = "Os PDFs já estão na pasta do cliente. Também dá para baixar daqui.";
          else if (pdfs) texto = "Baixe os PDFs abaixo.";
          NP.anexar(painelRobo, el("h2", { class: "secao" }, titulo), el("p", { class: "discreto" }, texto));
          if (pendentes) NP.anexar(botoes, el("button", { class: "botao botao-principal", type: "button", onclick: () => repetir(t, "emitir", "tentar") }, "Tentar de novo as que faltaram"));
          const cnpjs = [...new Set(t.cotacoes.map((c) => c.cnpj).filter(Boolean))];
          if (soPuladas && cnpjs.length === 1) NP.anexar(botoes, el("a", { class: "botao botao-principal", href: `#/nova?cnpj=${fmt.digitos(cnpjs[0])}` }, "Cotar de novo"));
          if (naPasta) NP.anexar(botoes, el("button", { class: "botao", type: "button", onclick: () => NP.abrirPasta(naPasta) }, "Abrir a pasta do cliente"));
        }
      } else if (t.status === "erro") {
        NP.anexar(painelRobo, el("h2", { class: "secao" }, "O robô parou"),
          el("div", { class: "problemas" }, t.mensagem || "erro sem descrição"),
          el("p", { class: "discreto" }, "Confira se a janela do portal continua aberta e peça de novo. O que já foi emitido não sai de novo."));
        if (t.tipo === "cotar") NP.anexar(botoes, el("button", { class: "botao botao-principal", type: "button", onclick: () => repetir(t, t.modo, "tentar") }, "Tentar de novo"));
      } else if (t.status === "cancelado") {
        NP.anexar(painelRobo, el("h2", { class: "secao" }, "Parado"),
          el("p", { class: "discreto" }, feitas ? "Você parou o robô. O que ficou pronto até ali está abaixo." : "Você parou o robô antes de ele emitir qualquer cotação."));
        if (t.tipo === "cotar") NP.anexar(botoes, el("button", { class: "botao botao-principal", type: "button", onclick: () => repetir(t, t.modo, "continuar") },
          t.modo === "ensaio" ? "Ensaiar de novo" : "Continuar de onde parou"));
      } else if (t.status === "interrompido") {
        NP.anexar(painelRobo, el("h2", { class: "secao" }, "Interrompido"),
          el("p", { class: "discreto" }, "A janela preta do Newport Cotações foi fechada enquanto o robô trabalhava. Se faltar alguma cotação, peça de novo: o robô não repete o que já foi emitido."));
        if (t.tipo === "cotar") NP.anexar(botoes, el("button", { class: "botao", type: "button", onclick: () => repetir(t, t.modo, "continuar") }, "Pedir de novo"));
      }
      if (botoes.childNodes.length) NP.anexar(painelRobo, botoes);
    }

    function desenharCotacoes() {
      NP.limpar(painelCot);
      if (t.tipo !== "cotar") { painelCot.hidden = true; return; }
      painelCot.hidden = false;
      const comPdf = t.cotacoes.filter((c) => c.tem_pdf);
      const varias = new Set(t.cotacoes.map((c) => c.cnpj)).size > 1 || t.total_pedidos > 1;
      NP.anexar(painelCot, el("div", { class: "painel-cabeca" },
        el("h2", { class: "secao" }, t.modo === "ensaio" ? "Resultado do ensaio" : "Cotações deste pedido"),
        comPdf.length > 1 ? el("button", { class: "botao botao-escuro", type: "button",
          onclick: () => NP.baixar(`/api/pdfs.zip?trabalho=${t.id}`) }, `Baixar os ${comPdf.length} PDFs (.zip)`) : null));
      if (!t.cotacoes.length) {
        NP.anexar(painelCot, el("p", { class: "vazio" }, ["na_fila", "rodando"].includes(t.status)
          ? "Cada cotação aparece aqui assim que fica pronta, com o PDF para baixar."
          : "Nenhuma cotação foi registrada neste pedido."));
        return;
      }
      NP.anexar(painelCot, el("div", { class: "tabela-rolagem" },
        el("table", { class: "tabela" }, NP.cabecaCotacoes({ empresa: varias }),
          el("tbody", {}, NP.agruparVersoes(t.cotacoes.slice().reverse()).map((c) => NP.linhasCotacao(c, { empresa: varias }))))));
    }

    function linhaRegistro(ev) {
      const nivel = (ev.dados && ev.dados.nivel) || ev.nivel || (ev.tipo === "erro" ? "error" : "info");
      return el("p", { class: nivel === "error" ? "erro" : nivel === "warning" ? "warning" : "" },
        el("span", { class: "num" }, hora(ev.em || new Date().toISOString())), "  ", ev.texto);
    }
    function desenharRegistro() {
      NP.limpar(registro);
      const linhas = t.eventos.filter((e) => e.texto);
      if (!linhas.length) NP.anexar(registro, el("p", {}, "Ainda sem registro."));
      else NP.anexar(registro, ...linhas.map(linhaRegistro));
    }

    let timer = null;
    function recarregar() {
      clearTimeout(timer);
      timer = setTimeout(async () => {
        try {
          const novo = await NP.api("GET", `/api/trabalhos/${tid}`);
          t = Object.assign(novo, { eventos: t.eventos });
          desenharCabeca(); desenharRobo(); desenharCotacoes();
        } catch (e) { /* a próxima atualização tenta de novo */ }
      }, 250);
    }

    const desligar = NP.ouvir((ev) => {
      if (ev.tipo === "conexao") { desenharRobo(); return; }
      if (ev.trabalho !== tid) return;
      if (ev.tipo === "etapa") { etapa = ev; desenharRobo(); }
      else if (ev.tipo === "pedido") { pedidoAtual = ev.pedido; desenharRobo(); }
      else if (ev.tipo === "log") {
        const p = linhaRegistro(ev);
        if (!t.eventos.some((x) => x.texto)) NP.limpar(registro);
        t.eventos.push({ tipo: "log", texto: ev.texto, dados: { nivel: ev.nivel }, em: new Date().toISOString() });
        const noFim = registro.scrollTop + registro.clientHeight >= registro.scrollHeight - 20;
        NP.anexar(registro, p);
        if (noFim) registro.scrollTop = registro.scrollHeight;
      } else if (ev.tipo === "trabalho") {
        t.status = ev.status;
        if (ev.mensagem) t.mensagem = ev.mensagem;
        if (ev.status !== "rodando") etapa = null;
        desenharRobo();
        recarregar();
      } else if (ev.tipo === "cotacao") recarregar();
      else if (["login_entrando", "login_aguardando", "login_ok", "codigo_necessario", "login_problema", "conexao"].includes(ev.tipo)) desenharRobo();
    });

    desenharCabeca(); desenharRobo(); desenharCotacoes(); desenharRegistro();
    NP.anexar(conteudo, cabeca, painelRobo, painelCot, painelLog);
    return () => { desligar(); clearTimeout(timer); };
  };
})();
