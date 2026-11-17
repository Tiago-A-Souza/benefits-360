/* Nova cotação: empresa, vidas por faixa (o "censo"), opções e planos de cada operadora. */
"use strict";
(function () {
  const FAIXAS = [["0_18", "0 - 18"], ["19_23", "19 - 23"], ["24_28", "24 - 28"], ["29_33", "29 - 33"], ["34_38", "34 - 38"],
    ["39_43", "39 - 43"], ["44_48", "44 - 48"], ["49_53", "49 - 53"], ["54_58", "54 - 58"], ["59_mais", "59+"]];
  const LIMITES = { "0_18": [0, 18], "19_23": [19, 23], "24_28": [24, 28], "29_33": [29, 33], "34_38": [34, 38],
    "39_43": [39, 43], "44_48": [44, 48], "49_53": [49, 53], "54_58": [54, 58], "59_mais": [59, 130] };
  const { el, fmt } = NP;

  function estadoInicial() {
    const ops = {};
    for (const op of NP.estado.operadoras) {
      const campos = {};
      for (const c of op.campos) campos[c.chave] = c.padrao === undefined || c.padrao === null ? "" : String(c.padrao);
      // Os planos e o "como escolher" já vêm como o corretor configurou o robô (Robôs > operadora).
      ops[op.id] = { ativa: op.marcada !== false || NP.estado.operadoras.length === 1, campos, planos: new Set(op.planos_padrao || []), menor: op.planos_modo_padrao === "menor_preco",
        qtdMenor: op.menor_preco_padrao || 1, ajustar: false };
    }
    return { cnpj: "", apelido: "", pasta: "", vidas: Object.fromEntries(FAIXAS.map(([k]) => [k, 0])),
      idades: Object.fromEntries(FAIXAS.map(([k]) => [k, ""])), ops };
  }

  function aplicarDados(f, dados) {
    if (!dados) return;
    f.cnpj = fmt.digitos(dados.cnpj);
    f.apelido = dados.apelido || "";
    f.pasta = dados.pasta_destino || "";
    for (const [k] of FAIXAS) {
      f.vidas[k] = Number(dados[`vidas_${k}`] || 0);
      f.idades[k] = dados[`idades_${k}`] ? String(dados[`idades_${k}`]) : "";
    }
    const opId = dados.operadora || Object.keys(f.ops)[0];
    const o = f.ops[opId];
    if (!o) return;
    const op = NP.operadora(opId);
    const doRobo = new Set(((op && op.campos) || []).filter((c) => c.robo).map((c) => c.chave));
    for (const chave of Object.keys(o.campos)) {
      if (doRobo.has(chave)) continue;   // vem da configuração atual do robô, não da cotação antiga
      if (dados[chave] !== undefined && dados[chave] !== null) o.campos[chave] = String(dados[chave]);
    }
    const planos = String(dados.planos || "");
    const m = planos.match(/^menor[\s_]*preco(?::(\d+))?$/i);
    o.menor = !!m;
    if (m) o.qtdMenor = Number(m[1] || o.qtdMenor);
    o.planos = new Set(m ? [] : planos.split(";").map((p) => p.trim()).filter(Boolean)
      .map((p) => (p.includes("|") ? p.split("|").map((x) => x.trim()).join(" | ") : p)));
  }

  const listaIdades = (t) => String(t || "").split(/[;,\s]+/).filter(Boolean);
  const faixasExatas = () => new Set(NP.estado.operadoras.flatMap((o) => o.faixas_idade_exata || []));
  const totalVidas = (f) => Object.values(f.vidas).reduce((a, b) => a + b, 0);
  const opsAtivas = (f) => NP.estado.operadoras.filter((o) => f.ops[o.id] && f.ops[o.id].ativa);
  // Campo que multiplica as cotações (a operadora declara; ex.: duas versões da cotação por plano).
  const multiplicador = (f, op) => op.campos.reduce((m, c) =>
    m * ((c.multiplica && c.multiplica[f.ops[op.id].campos[c.chave]]) || 1), 1);
  const cotacoesDe = (f, op) => { const o = f.ops[op.id]; return (o.menor ? Number(o.qtdMenor) : o.planos.size) * multiplicador(f, op); };

  function visivel(campo, valores) {
    if (!campo.visivel_se) return true;
    return Object.entries(campo.visivel_se).every(([k, v]) => String(valores[k]) === String(v));
  }

  function problemasLocais(f) {
    const p = [];
    if (!NP.cnpjValido(f.cnpj)) p.push("Digite um CNPJ válido para a empresa.");
    const total = totalVidas(f);
    const exatas = faixasExatas();
    for (const [k, rotulo] of FAIXAS) {
      const qtd = f.vidas[k];
      const idades = listaIdades(f.idades[k]);
      if (exatas.has(rotulo) && qtd > 0) {
        if (idades.length !== qtd) p.push(`Informe ${fmt.plural(qtd, "idade", "idades")} na faixa ${rotulo} (você informou ${idades.length}).`);
        const [min, max] = LIMITES[k];
        const fora = idades.filter((i) => !/^\d+$/.test(i) || Number(i) < min || Number(i) > max);
        if (fora.length) p.push(`As idades ${fora.join(", ")} não cabem na faixa ${rotulo}.`);
      }
    }
    for (const op of opsAtivas(f)) {
      const o = f.ops[op.id];
      if (total < op.min_vidas || total > op.max_vidas)
        p.push(`A ${op.nome} cota de ${op.min_vidas} a ${op.max_vidas} vidas neste produto; você distribuiu ${total}.`);
      if (!o.menor && o.planos.size === 0) p.push(`Escolha pelo menos um plano da ${op.nome}.`);
      for (const c of op.campos) {
        if (c.chave === "congenere_atual" && visivel(c, o.campos) && !String(o.campos[c.chave] || "").trim())
          p.push(`Informe a operadora atual da empresa ou marque que ela não tem plano hoje (${op.nome}).`);
      }
    }
    if (!opsAtivas(f).length) p.push("Escolha pelo menos uma operadora.");
    return p;
  }

  function montarItens(f) {
    return opsAtivas(f).map((op) => {
      const o = f.ops[op.id];
      const dados = { id: f.apelido.trim() || fmt.cnpj(f.cnpj), apelido: f.apelido.trim(), cnpj: fmt.cnpj(f.cnpj),
        pasta_destino: f.pasta.trim(), operadora: op.id };
      for (const [k] of FAIXAS) {
        dados[`vidas_${k}`] = f.vidas[k];
        if (f.vidas[k] > 0 && f.idades[k].trim()) dados[`idades_${k}`] = listaIdades(f.idades[k]).join("; ");
      }
      for (const c of op.campos) if (visivel(c, o.campos)) dados[c.chave] = o.campos[c.chave];
      dados.planos = o.menor ? `menor_preco:${o.qtdMenor}` : [...o.planos].join("; ");
      return { operadora: op.id, pedidos: [dados] };
    });
  }

  /* ------------------------------------------------------------------ peças visuais */
  function segmentos(opcoes, valor, aoMudar, rotulo) {
    const grupo = el("div", { class: "segmentos", role: "group", "aria-label": rotulo });
    const desenhar = (v) => grupo.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.v === String(v))));
    for (const [v, texto] of opcoes) {
      grupo.appendChild(el("button", { type: "button", "data-v": v, onclick: () => { desenhar(v); aoMudar(v); } }, texto));
    }
    desenhar(valor);
    return grupo;
  }

  function chave(rotulo, marcado, aoMudar) {
    const entrada = el("input", { type: "checkbox", onchange: (e) => aoMudar(e.target.checked) });
    entrada.checked = marcado;
    return el("label", { class: "chave" }, entrada, el("span", { class: "chave-trilho" }), el("span", {}, rotulo));
  }

  NP.telas.nova = async function (conteudo, rota) {
    const f = estadoInicial();
    let carregado = null;
    const cnpjParam = rota.consulta.get("cnpj");
    if (cnpjParam) {
      try {
        carregado = await NP.api("GET", `/api/empresas/${fmt.digitos(cnpjParam)}`);
        aplicarDados(f, carregado.ultimo_pedido || { cnpj: cnpjParam });
      } catch (e) { f.cnpj = fmt.digitos(cnpjParam); }
    }

    const problemasBox = el("div", { class: "problemas", hidden: true });

    /* --- empresa --- */
    const cnpjCampo = el("input", { class: "campo", id: "cnpj", inputmode: "numeric", autocomplete: "off",
      placeholder: "00.000.000/0000-00", value: fmt.cnpj(f.cnpj) });
    const cnpjAjuda = el("div", { class: "ajuda" });
    const apelidoCampo = el("input", { class: "campo", id: "apelido", value: f.apelido, placeholder: "Ex.: Padaria do Centro",
      oninput: (e) => { f.apelido = e.target.value; } });
    const pastaCampo = el("input", { class: "campo", id: "pasta", value: f.pasta, placeholder: "C:\\...\\SAÚDE\\IMPLANTAÇÃO\\ESTUDO\\COTAÇÕES",
      oninput: (e) => { f.pasta = e.target.value; } });
    const botaoPasta = el("button", { class: "botao", type: "button", onclick: async () => {
      botaoPasta.disabled = true;
      try {
        const r = await NP.api("POST", "/api/escolher-pasta");
        if (r.pasta) { f.pasta = r.pasta; pastaCampo.value = r.pasta; }
      } catch (e) { NP.aviso(e.message, { tipo: "erro" }); } finally { botaoPasta.disabled = false; }
    } }, "Escolher pasta");

    async function aoMudarCnpj() {
      const d = fmt.digitos(cnpjCampo.value).slice(0, 14);
      f.cnpj = d;
      cnpjCampo.value = fmt.cnpj(d);
      cnpjCampo.classList.toggle("invalido", d.length === 14 && !NP.cnpjValido(d));
      NP.limpar(cnpjAjuda);
      if (d.length === 14 && !NP.cnpjValido(d)) { cnpjAjuda.textContent = "Este CNPJ não é válido. Confira os números."; return; }
      if (d.length === 14) {
        try {
          const emp = await NP.api("GET", `/api/empresas/${d}`, undefined, { aceitarErro: true });
          if (emp && emp.cnpj) {
            const nome = emp.razao_social || emp.apelido || "esta empresa";
            NP.anexar(cnpjAjuda, `${nome} já foi cotada aqui. `);
            if (emp.ultimo_pedido) {
              NP.anexar(cnpjAjuda, el("a", { href: "#", onclick: (ev) => { ev.preventDefault(); NP.ir(`#/nova?cnpj=${d}`); } },
                "Usar os mesmos dados da última cotação"));
            }
          }
        } catch (e) { /* sem histórico */ }
      }
      atualizar();
    }
    cnpjCampo.addEventListener("input", aoMudarCnpj);

    const painelEmpresa = el("section", { class: "painel", "aria-labelledby": "t-empresa" },
      el("h2", { class: "secao", id: "t-empresa" }, "Empresa"),
      el("p", { class: "secao-ajuda" }, "O robô busca a razão social no portal pelo CNPJ."),
      el("div", { class: "form-linha" }, el("label", { for: "cnpj" }, "CNPJ"), el("div", {}, cnpjCampo, cnpjAjuda)),
      el("div", { class: "form-linha" }, el("label", { for: "apelido" }, "Nome para achar depois"),
        el("div", {}, apelidoCampo, el("div", { class: "ajuda" }, "Opcional. Aparece na lista de cotações."))),
      el("div", { class: "form-linha" }, el("label", { for: "pasta" }, "Pasta do cliente"),
        el("div", {}, el("div", { class: "campo-grupo" }, pastaCampo, botaoPasta),
          el("div", { class: "ajuda" }, (() => {
            const nomes = NP.estado.operadoras.map((op) => (op.textos || {}).nome_pdf).filter(Boolean);
            return `Opcional. Os PDFs são copiados para cá com o nome de sempre${nomes.length ? ` (${nomes.join(" / ")})` : ""}.`;
          })()))));

    /* --- censo --- */
    const colunas = {};
    const censo = el("div", { class: "censo" });
    const exatas = faixasExatas();
    for (const [k, rotulo] of FAIXAS) {
      const qtd = el("div", { class: "faixa-qtd" });
      const barra = el("div", { class: "faixa-barra" });
      const mudar = (delta) => { f.vidas[k] = Math.max(0, Math.min(99, f.vidas[k] + delta)); atualizar(); };
      const col = el("div", { class: "faixa-col" },
        qtd,
        el("div", { class: "faixa-barra-area", title: `Somar uma vida na faixa ${rotulo}`, onclick: () => mudar(1) }, barra),
        el("div", { class: "faixa-rotulo" }, rotulo, exatas.has(rotulo) ? el("span", { class: "exata", title: "Pede idade exata" }, " *") : null),
        el("div", { class: "passo" },
          el("button", { type: "button", "aria-label": `Tirar uma vida da faixa ${rotulo}`, onclick: () => mudar(-1) }, "−"),
          el("button", { type: "button", "aria-label": `Somar uma vida na faixa ${rotulo}`, onclick: () => mudar(1) }, "+")));
      colunas[k] = { qtd, barra };
      censo.appendChild(col);
    }
    const totalBox = el("div", { class: "censo-total" });
    const idadesBox = el("div", { class: "idades" });
    const painelVidas = el("section", { class: "painel", "aria-labelledby": "t-vidas" },
      el("h2", { class: "secao", id: "t-vidas" }, "Vidas por faixa etária"),
      el("p", { class: "secao-ajuda" }, "Clique na coluna ou use + e − para distribuir as vidas da empresa (titulares e dependentes). ",
        exatas.size ? "Nas faixas com * o portal pede a idade de cada vida." : ""),
      censo, totalBox, idadesBox);

    function desenharIdades() {
      NP.limpar(idadesBox);
      for (const [k, rotulo] of FAIXAS) {
        if (!exatas.has(rotulo) || f.vidas[k] === 0) continue;
        const campo = el("input", { class: "campo", id: `idades_${k}`, value: f.idades[k], inputmode: "numeric",
          placeholder: f.vidas[k] === 1 ? "Ex.: 7" : "Ex.: 3, 7, 12", oninput: (e) => { f.idades[k] = e.target.value; atualizarResumo(); } });
        idadesBox.appendChild(el("div", { class: "idade-linha" },
          el("label", { for: `idades_${k}` }, `Idades na faixa ${rotulo}`),
          el("div", {}, campo, el("div", { class: "ajuda" },
            f.vidas[k] === 1 ? "A idade da vida nesta faixa." : `As ${f.vidas[k]} idades, separadas por vírgula.`))));
      }
    }

    /* --- operadoras --- */
    const paineisOps = NP.estado.operadoras.map((op) => {
      const o = f.ops[op.id];
      const corpo = el("div", {});
      corpo.hidden = !o.ativa;       // operadora que começa desmarcada (ex.: em calibragem) começa fechada
      const linhasCampos = el("div", {});
      const padraoDe = (chaveCampo) => {
        const c = op.campos.find((x) => x.chave === chaveCampo);
        return c && c.padrao !== undefined && c.padrao !== null ? String(c.padrao) : "";
      };
      const mudadoNestaCotacao = () => op.campos.some((c) => c.robo && o.campos[c.chave] !== padraoDe(c.chave));

      function linhaCampo(c) {
        let controle;
        if (c.tipo === "sim_nao") controle = chave(c.rotulo, o.campos[c.chave] === "sim", (v) => { o.campos[c.chave] = v ? "sim" : "nao"; desenharCampos(); });
        else if (c.tipo === "escolha") controle = segmentos(c.opcoes, o.campos[c.chave], (v) => { o.campos[c.chave] = v; desenharCampos(); atualizarResumo(); }, c.rotulo);
        else {
          const lista = c.tipo === "sugestoes" ? `sug-${op.id}-${c.chave}` : null;
          controle = el("div", {},
            el("input", { class: "campo", id: `${op.id}-${c.chave}`, value: o.campos[c.chave] || "", list: lista,
              oninput: (e) => { o.campos[c.chave] = e.target.value; if (c.robo) atualizarFrase(); } }),
            lista ? el("datalist", { id: lista }, (c.opcoes || []).map((x) => el("option", { value: x }))) : null);
        }
        // Chaves (sim/não) mostram o título curto à esquerda e a frase completa ao lado da chave.
        const titulo = c.tipo === "sim_nao" ? (c.titulo || "") : c.rotulo;
        return el("div", { class: "form-linha" },
          el(c.tipo === "sim_nao" ? "div" : "label", { class: "rotulo", for: c.tipo === "sim_nao" ? null : `${op.id}-${c.chave}` }, titulo),
          el("div", {}, controle, c.ajuda ? el("div", { class: "ajuda" }, c.ajuda) : null));
      }

      /* O que é da empresa fica sempre à vista. O que é do robô (contratação, vigência, coparticipação...)
         aparece numa frase: o corretor só abre para mudar nesta cotação. A configuração fixa fica em Robôs. */
      const frase = el("span", {});
      const atualizarFrase = () => {
        NP.anexar(NP.limpar(frase), NP.resumoDoRobo(op, (k) => o.campos[k], { produto: op.produto_portal }), ".",
          mudadoNestaCotacao() ? el("span", { class: "selo-mudado" }, "mudado só nesta cotação") : null);
      };
      const desenharCampos = () => {
        NP.limpar(linhasCampos);
        for (const c of op.campos) if (!c.robo && visivel(c, o.campos)) linhasCampos.appendChild(linhaCampo(c));
        atualizarFrase();
        const robo = el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "O robô vai cotar"),
          el("div", {},
            el("div", { class: "frase-robo" }, frase),
            el("div", { class: "acoes-frase" },
              el("button", { class: "link-pequeno", type: "button", "aria-expanded": String(o.ajustar),
                onclick: () => { o.ajustar = !o.ajustar; desenharCampos(); } }, o.ajustar ? "Fechar" : "Mudar só nesta cotação"),
              mudadoNestaCotacao() ? el("button", { class: "link-pequeno", type: "button", onclick: () => {
                for (const c of op.campos) if (c.robo) o.campos[c.chave] = padraoDe(c.chave);
                desenharCampos();
              } }, "Voltar à configuração do robô") : null,
              el("a", { class: "link-pequeno com-icone", href: `#/robo/${op.id}` }, NP.iconeEngrenagem(14), "Configurar o robô"))));
        linhasCampos.appendChild(robo);
        if (o.ajustar) {
          linhasCampos.appendChild(el("div", { class: "ajuste-cotacao" },
            op.campos.filter((c) => c.robo && visivel(c, o.campos)).map(linhaCampo)));
        }
      };
      desenharCampos();

      const listaPlanos = el("div", { class: "planos" });
      const menorBox = el("div", { class: "menor-preco" });
      const desenharPlanos = () => {
        NP.limpar(listaPlanos); NP.limpar(menorBox);
        if (o.menor) {
          const qtd = el("span", { class: "faixa-qtd num" }, String(o.qtdMenor));
          NP.anexar(menorBox, 
            el("span", {}, "Cotar os"),
            el("div", { class: "passo" },
              el("button", { type: "button", "aria-label": "Menos um plano", onclick: () => { o.qtdMenor = Math.max(1, o.qtdMenor - 1); desenharPlanos(); atualizarResumo(); } }, "−"),
              el("button", { type: "button", "aria-label": "Mais um plano", onclick: () => { o.qtdMenor = Math.min(10, o.qtdMenor + 1); desenharPlanos(); atualizarResumo(); } }, "+")),
            qtd, el("span", {}, o.qtdMenor === 1 ? "plano mais barato da lista do portal" : "planos mais baratos da lista do portal"));
          return;
        }
        const grupos = {};
        for (const p of op.planos) (grupos[p.acomodacao || "Outros"] = grupos[p.acomodacao || "Outros"] || []).push(p);
        for (const acom of Object.keys(grupos).sort()) {
          const coluna = el("div", {}, el("h3", {}, acom));
          for (const p of grupos[acom]) {
            const rotulo = `${p.nome} | ${p.acomodacao}`;
            const caixa = el("input", { type: "checkbox", value: rotulo });
            caixa.checked = o.planos.has(rotulo);
            const item = el("label", { class: `plano-item ${caixa.checked ? "marcado" : ""}` }, caixa, el("span", {}, p.nome),
              p.visto_no_portal ? null : null);
            caixa.addEventListener("change", () => {
              if (caixa.checked) o.planos.add(rotulo); else o.planos.delete(rotulo);
              item.classList.toggle("marcado", caixa.checked);
              atualizarResumo();
            });
            coluna.appendChild(item);
          }
          listaPlanos.appendChild(coluna);
        }
      };
      desenharPlanos();

      const conexao = (NP.estado.robo.conexao || {})[op.id] || "desconectado";
      NP.anexar(corpo, 
        linhasCampos,
        el("div", { class: "form-linha" }, el("div", { class: "rotulo" }, "Planos"),
          el("div", {},
            el("div", { style: { marginBottom: "10px" } }, segmentos([["lista", "Escolher na lista"], ["menor", "Os mais baratos"]],
              o.menor ? "menor" : "lista", (v) => { o.menor = v === "menor"; desenharPlanos(); atualizarResumo(); }, "Como escolher os planos")),
            menorBox, listaPlanos,
            el("div", { class: "ajuda" }, (op.textos || {}).planos
              || "Cada plano vira uma cotação e um PDF. A lista cresce sozinha com os planos que o robô encontrar no portal."))));

      const ativa = NP.estado.operadoras.length > 1
        ? chave("Cotar nesta operadora", o.ativa, (v) => { o.ativa = v; corpo.hidden = !v; atualizarResumo(); }) : null;
      return el("section", { class: "painel operadora", style: { "--cor-op": op.cor }, "aria-labelledby": `t-${op.id}` },
        el("div", { class: "operadora-cabeca" },
          el("div", {}, el("div", { class: "operadora-nome", id: `t-${op.id}` }, op.nome), el("div", { class: "operadora-produto" }, op.produto)),
          el("div", { class: "operadora-lado" },
            el("div", { class: "conexao-status", style: { color: "var(--texto-2)", margin: 0 } }, el("span", { class: `ponto ${conexao}` }), NP.CONEXAO[conexao]),
            el("a", { class: "botao-icone", href: `#/robo/${op.id}`, title: "Configurar o robô", "aria-label": `Configurar o robô da ${op.nome}` },
              NP.iconeEngrenagem(18))),
          ativa),
        corpo);
    });

    /* --- barra de ação --- */
    const resumo = el("div", { class: "resumo" });
    const botaoEnsaio = el("button", { class: "botao", type: "button", onclick: () => enviar("ensaio") }, "Ensaiar sem emitir");
    const botaoGerar = el("button", { class: "botao botao-principal", type: "button", onclick: () => enviar("emitir") }, "Gerar cotações");
    const barra = el("div", { class: "barra-acao" }, resumo, el("div", { class: "acoes" }, botaoEnsaio, botaoGerar));

    function atualizarResumo() {
      const total = totalVidas(f);
      const partes = opsAtivas(f).map((op) => `${fmt.plural(cotacoesDe(f, op), "cotação", "cotações")} na ${op.nome}`);
      resumo.textContent = `${fmt.plural(total, "vida", "vidas")}${partes.length ? ", " + partes.join(" e ") : ""}`;
      const n = opsAtivas(f).reduce((a, op) => a + cotacoesDe(f, op), 0);
      botaoGerar.textContent = n ? `Gerar ${fmt.plural(n, "cotação", "cotações")}` : "Gerar cotações";
    }

    function atualizar() {
      const total = totalVidas(f);
      const escala = Math.max(5, ...Object.values(f.vidas));
      for (const [k] of FAIXAS) {
        const q = f.vidas[k];
        colunas[k].qtd.textContent = q;
        colunas[k].qtd.classList.toggle("zero", q === 0);
        colunas[k].barra.style.height = `${(q / escala) * 100}%`;
      }
      const op = opsAtivas(f)[0];
      NP.anexar(NP.limpar(totalBox), 
        el("strong", { class: op && (total < op.min_vidas || total > op.max_vidas) && total > 0 ? "fora" : "" }, String(total)),
        el("span", { class: "discreto" }, total === 1 ? "vida" : "vidas", op ? ` (a ${op.nome} cota de ${op.min_vidas} a ${op.max_vidas})` : ""));
      desenharIdades();
      atualizarResumo();
    }

    async function enviar(modo) {
      problemasBox.hidden = true;
      const locais = problemasLocais(f);
      if (locais.length) return mostrarProblemas(locais);
      const itens = montarItens(f);
      let validacao;
      try { validacao = await NP.api("POST", "/api/validar", { itens }); } catch (e) { return NP.aviso(e.message, { tipo: "erro" }); }
      if (!validacao.ok) return mostrarProblemas(Object.values(validacao.problemas).flat());
      const ja = (modo === "emitir" && validacao.ja_emitidas) || [];
      const linhasJa = ja.map((j) => `${j.plano}: protocolo ${j.protocolo || "—"}${j.quando ? `, emitida ${fmt.quando(j.quando)}` : ""}.`);
      let reemitir = [];
      if (ja.length && ja.length >= validacao.cotacoes) {
        // Tudo já emitido: o robô só pularia. Avisa em vez de mandar o robô ao portal à toa.
        const reemitiveis = ja.filter((j) => j.protocolo);
        const escolha = await NP.confirmar({
          titulo: ja.length === 1 ? "Esta cotação já foi emitida" : "Estas cotações já foram emitidas",
          texto: [...linhasJa, "Sozinho, o robô não emite de novo a mesma cotação (mesma empresa, vidas, opções e plano): é o que evita "
            + "protocolo duplicado quando um pedido é repetido sem querer. O PDF já está em Cotações.",
            reemitiveis.length ? "Para testar ou mostrar o robô, você pode emitir de novo de propósito: sai um protocolo novo."
              : "Para uma cotação nova, mude o plano, as vidas ou as opções."],
          ok: "Ver em Cotações", cancelar: "Voltar", principal: false,
          alternativa: reemitiveis.length ? "Emitir de novo mesmo assim" : null,
        });
        if (escolha !== "alternativa") {
          if (escolha) NP.ir("#/cotacoes");
          return;
        }
        const n = reemitiveis.length;
        const certeza = await NP.confirmar({
          titulo: n === 1 ? "Emitir de novo esta cotação?" : `Emitir de novo estas ${n} cotações?`,
          texto: ["O robô emite de novo no portal e cada cotação ganha um protocolo novo. Os protocolos de antes continuam no portal "
            + "e os PDFs de antes continuam em Cotações.",
            "Use para testar e mostrar o robô. Com cliente de verdade, evite repetir a mesma cotação."],
          ok: n === 1 ? "Emitir de novo" : `Emitir de novo as ${n}`,
        });
        if (!certeza) return;
        reemitir = reemitiveis.map((j) => j.protocolo);
      } else if (modo === "emitir") {
        const ops = opsAtivas(f).map((o) => o.nome).join(" e ");
        const novas = validacao.cotacoes - ja.length;
        const reemitiveis = ja.filter((j) => j.protocolo);
        const ok = await NP.confirmar({
          titulo: `Gerar ${fmt.plural(novas, "cotação", "cotações")} na ${ops}?`,
          texto: ["Cada cotação gera um protocolo de verdade no portal da operadora.",
            "O robô entra no portal sozinho, com o login guardado na engrenagem.",
            ja.length ? `Já emitidas antes (o robô pula, não sai de novo): ${ja.map((j) => j.plano).join("; ")}.` : null].filter(Boolean),
          ok: `Gerar ${fmt.plural(novas, "cotação", "cotações")}`,
          // Testes e demonstrações: emitir de novo também as que já saíram (com uma segunda confirmação).
          alternativa: reemitiveis.length ? `Emitir todas (${validacao.cotacoes})` : null,
        });
        if (!ok) return;
        if (ok === "alternativa") {
          const n = reemitiveis.length;
          const certeza = await NP.confirmar({
            titulo: n === 1 ? "Emitir de novo também a que já saiu?" : `Emitir de novo também as ${n} que já saíram?`,
            texto: [...reemitiveis.map((j) => `${j.plano}: protocolo ${j.protocolo}.`),
              "Elas ganham um protocolo novo; os de antes continuam no portal e os PDFs de antes continuam em Cotações.",
              "Use para testar e mostrar o robô. Com cliente de verdade, evite repetir a mesma cotação."],
            ok: `Emitir as ${validacao.cotacoes}`,
          });
          if (!certeza) return;
          reemitir = reemitiveis.map((j) => j.protocolo);
        }
      }
      botaoGerar.disabled = botaoEnsaio.disabled = true;
      try {
        const r = await NP.api("POST", "/api/trabalhos", { modo, confirmado: modo === "emitir", itens, ...(reemitir.length ? { reemitir } : {}) });
        NP.aviso(modo === "ensaio" ? "Ensaio na fila. O robô percorre as telas com o primeiro plano e para antes de emitir."
          : reemitir.length ? "Pedido na fila. O robô vai emitir de novo, com protocolo novo." : "Pedido na fila. Acompanhe o robô por aqui.");
        NP.ir(`#/andamento/${r.id}`);
      } catch (e) {
        if (e.dados && e.dados.problemas) mostrarProblemas(Object.values(e.dados.problemas).flat());
        else NP.aviso(e.message, { tipo: "erro" });
      } finally { botaoGerar.disabled = botaoEnsaio.disabled = false; }
    }

    function mostrarProblemas(lista) {
      NP.anexar(NP.limpar(problemasBox), el("strong", {}, "Antes de continuar, ajuste:"), el("ul", {}, lista.map((p) => el("li", {}, p))));
      problemasBox.hidden = false;
      problemasBox.scrollIntoView({ behavior: "smooth", block: "center" });
    }

    NP.anexar(conteudo, 
      el("h1", { class: "titulo" }, "Nova cotação"),
      el("p", { class: "subtitulo" }, "Preencha a empresa e as vidas, escolha os planos e o robô faz o resto no portal."),
      carregado && carregado.ultimo_pedido ? el("p", { class: "discreto" }, `Dados da última cotação de ${carregado.razao_social || carregado.apelido || fmt.cnpj(carregado.cnpj)} carregados. Confira antes de gerar.`) : null,
      painelEmpresa, painelVidas, ...paineisOps, problemasBox, barra);
    atualizar();
    if (!f.cnpj) cnpjCampo.setAttribute("data-foco", "");
  };
})();
