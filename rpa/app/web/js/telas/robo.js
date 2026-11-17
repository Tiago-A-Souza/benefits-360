/* Configuração do robô de uma operadora (#/robo/<id>): tudo o que ele preenche no portal, tela por tela.
   O esquema vem da operadora (Operadora.configuracao); esta tela só desenha e grava. */
"use strict";
(function () {
  const { el, fmt } = NP;
  const FAIXAS = ["0 - 18", "19 - 23", "24 - 28", "29 - 33", "34 - 38", "39 - 43", "44 - 48", "49 - 53", "54 - 58", "59+"];
  const igual = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  function textoDoValor(campo, valor) {
    if (campo.tipo === "escolha") return ((campo.opcoes || []).find((o) => String(o[0]) === String(valor)) || [])[1] || String(valor);
    if (campo.tipo === "sim_nao") return valor === "sim" ? "sim" : "não";
    if (campo.tipo === "texto") return valor ? `“${valor}”` : "vazio";
    if (campo.tipo === "faixas" || campo.tipo === "planos") return valor.length ? valor.join(", ") : "nenhum";
    if (campo.tipo === "pares") return Object.keys(valor).length ? fmt.plural(Object.keys(valor).length, "linha", "linhas") : "nenhuma linha";
    return String(valor);
  }

  function segmentos(opcoes, valor, aoMudar, rotulo) {
    const grupo = el("div", { class: "segmentos", role: "group", "aria-label": rotulo });
    for (const [v, texto] of opcoes) {
      grupo.appendChild(el("button", { type: "button", "aria-pressed": String(String(v) === String(valor)), onclick: (ev) => {
        grupo.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(b === ev.currentTarget)));
        aoMudar(String(v));
      } }, texto));
    }
    return grupo;
  }

  function chave(rotulo, marcado, aoMudar) {
    const entrada = el("input", { type: "checkbox", onchange: (e) => aoMudar(e.target.checked) });
    entrada.checked = marcado;
    return el("label", { class: "chave" }, entrada, el("span", { class: "chave-trilho" }), el("span", {}, rotulo));
  }

  function tabelaPares(pares, [rotuloA, rotuloB], [exemploA, exemploB], aoMudar) {
    const corpo = el("tbody");
    const desenhar = () => {
      NP.limpar(corpo);
      pares.forEach((par, i) => NP.anexar(corpo, el("tr", {},
        el("td", {}, el("input", { class: "campo", value: par[0], "aria-label": rotuloA, placeholder: exemploA, oninput: (e) => { par[0] = e.target.value; aoMudar(); } })),
        el("td", {}, el("input", { class: "campo", value: par[1], "aria-label": rotuloB, placeholder: exemploB, oninput: (e) => { par[1] = e.target.value; aoMudar(); } })),
        el("td", {}, el("button", { class: "botao botao-pequeno", type: "button", "aria-label": `Tirar a linha ${par[0] || i + 1}`,
          onclick: () => { pares.splice(i, 1); desenhar(); aoMudar(); } }, "Tirar")))));
      if (!pares.length) NP.anexar(corpo, el("tr", {}, el("td", { colspan: 3, class: "discreto pequeno" }, "Nenhuma linha.")));
    };
    desenhar();
    return el("div", {},
      el("table", { class: "tabela-edicao" }, el("thead", {}, el("tr", {}, el("th", {}, rotuloA), el("th", {}, rotuloB), el("th", {}))), corpo),
      el("button", { class: "botao botao-pequeno", type: "button", style: { marginTop: "6px" },
        onclick: () => { pares.push(["", ""]); desenhar(); aoMudar(); } }, "Adicionar linha"));
  }

  /* Login do portal (tela 1 do robô). Vai para o cofre do Windows pela API, que só aceita escrita: a senha
     nunca volta para a tela. Fica fora do "Salvar configuração" (não é configuração). */
  function cartaoLogin(opId, nomeOp, declarado) {
    // Os campos do login são os que a operadora declara (ex.: CPF, e-mail e senha), com validação e máscara.
    const campos = declarado.campos || [{ chave: "usuario", rotulo: "Usuário", tipo: "texto" }, { chave: "senha", rotulo: "Senha", tipo: "senha" }];
    const senhaMax = declarado.senha_max;
    const situacao = el("p", { class: "login-estado", role: "status" });
    const entradas = {};
    for (const c of campos) {
      const id = `login-${c.chave}`;
      if (c.tipo === "cpf") entradas[c.chave] = el("input", { class: "campo", id, inputmode: "numeric", autocomplete: "off", spellcheck: "false",
        oninput: (e) => { e.target.value = fmt.cpf(e.target.value); } });
      else if (c.tipo === "cpf_cnpj") entradas[c.chave] = el("input", { class: "campo", id, inputmode: "numeric", autocomplete: "off", spellcheck: "false",
        oninput: (e) => { const d = fmt.digitos(e.target.value); e.target.value = d.length > 11 ? fmt.cnpj(d) : fmt.cpf(d); } });
      else if (c.tipo === "email") entradas[c.chave] = el("input", { class: "campo", id, type: "email", autocomplete: "off", spellcheck: "false" });
      else if (c.tipo === "senha") entradas[c.chave] = el("input", { class: "campo", id, type: "password", autocomplete: "new-password" });
      else entradas[c.chave] = el("input", { class: "campo", id, autocomplete: "off", spellcheck: "false" });
    }
    const senhas = campos.filter((c) => c.tipo === "senha");
    const botaoTestar = el("button", { class: "botao", type: "button", onclick: () => NP.testarLogin(opId) }, "Testar login");
    const botaoApagar = el("button", { class: "botao botao-perigo", type: "button", onclick: apagar }, "Apagar credenciais");
    const nomeCampo = (c) => (c.rotulo || c.chave).toLowerCase();
    const artigo = (c) => c.artigo || "o";

    function mostrar(s) {
      for (const c of campos) {
        const e = entradas[c.chave];
        e.value = "";
        if (c.tipo === "senha") e.placeholder = s.guardadas ? `${nomeCampo(c)} guardada` : "";
        else if (c.mascara) e.placeholder = s.guardadas ? s[`${c.chave}_mascarado`] : `${artigo(c)} ${nomeCampo(c)} do portal`;
        else if (c.tipo === "cpf") e.placeholder = s.guardadas ? `${c.rotulo} guardado (digite para trocar)` : "000.000.000-00";
        else if (c.tipo === "cpf_cnpj") e.placeholder = s.guardadas ? `${c.rotulo} guardado (digite para trocar)` : "CPF ou CNPJ";
        else e.placeholder = s.guardadas ? `${c.rotulo} guardado (digite para trocar)` : `${artigo(c)} ${nomeCampo(c)} do portal`;
      }
      const mascarados = campos.filter((c) => c.mascara && s[`${c.chave}_mascarado`]).map((c) => `${nomeCampo(c)} ${s[`${c.chave}_mascarado`]}`);
      situacao.className = `login-estado ${s.recusadas ? "erro" : ""}`;
      situacao.textContent = !s.guardadas
        ? `Nenhum login guardado. Sem ele o robô não entra no portal da ${nomeOp}.`
        : s.recusadas
          ? `O portal recusou este login. O robô não tenta de novo até você guardar a senha outra vez.`
          : `Login guardado ${fmt.quando(s.quando)}${mascarados.length ? ` (${mascarados.join(", ")})` : ""}.`;
      botaoTestar.disabled = !s.guardadas || s.recusadas;
      botaoApagar.disabled = !s.guardadas;
    }

    const senhaGrande = () => senhaMax && senhas.some((c) => entradas[c.chave].value.length > senhaMax);
    async function guardar(ev) {
      ev.preventDefault();
      for (const c of campos.filter((x) => x.tipo === "cpf")) {
        if (!NP.cpfValido(entradas[c.chave].value)) { NP.aviso("CPF inválido: confira os 11 dígitos.", { tipo: "erro" }); entradas[c.chave].focus(); return; }
      }
      for (const c of campos.filter((x) => x.tipo === "cpf_cnpj")) {
        const v = entradas[c.chave].value;
        if (!NP.cpfValido(v) && !NP.cnpjValido(v)) { NP.aviso("CPF/CNPJ inválido: confira os dígitos.", { tipo: "erro" }); entradas[c.chave].focus(); return; }
      }
      if (senhaGrande()) {
        NP.aviso(`A senha do portal tem no máximo ${senhaMax} caracteres (é o limite do campo no portal). Confira se não entrou um espaço a mais.`,
          { tipo: "erro", duracao: 9000 });
        entradas[senhas[0].chave].focus();
        return;
      }
      // Espaço no começo ou no fim (fora o CPF): avisa e pede confirmação; o robô não tira sozinho.
      const comEspaco = campos.filter((c) => c.tipo !== "cpf" && c.tipo !== "cpf_cnpj" && entradas[c.chave].value && entradas[c.chave].value !== entradas[c.chave].value.trim());
      if (comEspaco.length) {
        const nomes = comEspaco.map((c) => `${artigo(c)} ${nomeCampo(c)}`).join(" e ");
        const maiuscula = (t) => t[0].toUpperCase() + t.slice(1);
        const escolha = await NP.confirmar({
          titulo: `${maiuscula(nomes)} ${comEspaco.length > 1 ? "começam ou terminam" : "começa ou termina"} com espaço`,
          texto: ["Espaço no começo ou no fim costuma entrar sem querer (ao copiar e colar). O robô digita no portal "
            + `exatamente o que estiver guardado, e o portal pode recusar o login.`,
            `Confira ${nomes}. O robô não tira os espaços sozinho.`],
          ok: "Guardar assim mesmo", principal: false, alternativa: "Tirar os espaços", cancelar: "Voltar",
        });
        if (!escolha) return;
        if (escolha === "alternativa") for (const c of comEspaco) entradas[c.chave].value = entradas[c.chave].value.trim();
        if (senhaGrande()) {
          NP.aviso(`A senha do portal tem no máximo ${senhaMax} caracteres (é o limite do campo no portal).`, { tipo: "erro", duracao: 9000 });
          entradas[senhas[0].chave].focus();
          return;
        }
      }
      try {
        const corpo = Object.fromEntries(campos.map((c) => [c.chave, entradas[c.chave].value]));
        const r = await NP.api("POST", `/api/credenciais/${opId}`, corpo);
        mostrar(r);
        NP.aviso("Login guardado no cofre do Windows. Use “Testar login” para conferir.");
        NP.atualizarOperadoras();
      } catch (e) { NP.aviso(e.message, { tipo: "erro", duracao: 9000 }); }
    }

    async function apagar() {
      const ok = await NP.confirmar({
        titulo: `Apagar o login da ${nomeOp} deste computador?`,
        texto: ["O robô deixa de entrar no portal até alguém guardar um login de novo.", "Faça isso ao sair da Newport."],
        ok: "Apagar credenciais", principal: false,
      });
      if (!ok) return;
      try {
        mostrar(await NP.api("DELETE", `/api/credenciais/${opId}`));
        NP.aviso("Login apagado do cofre do Windows.");
        NP.atualizarOperadoras();
      } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
    }

    NP.api("GET", `/api/credenciais/${opId}`).then(mostrar).catch((e) => NP.aviso(e.message, { tipo: "erro" }));
    return el("form", { class: "login-portal", autocomplete: "off", onsubmit: guardar },
      situacao,
      el("div", { class: "login-campos" },
        campos.flatMap((c) => [el("label", { for: `login-${c.chave}` }, c.rotulo || c.chave), entradas[c.chave]])),
      senhaMax ? el("p", { class: "ajuda" }, `A senha do portal tem até ${senhaMax} caracteres.`) : null,
      el("div", { class: "acoes-linha" }, el("button", { class: "botao botao-principal", type: "submit" }, "Guardar"), botaoTestar, botaoApagar));
  }

  NP.telas.robo = async function (conteudo, rota) {
    const opId = rota.param || (NP.estado.operadoras[0] || {}).id;
    let dados;
    try {
      dados = await NP.api("GET", `/api/robos/${opId}`);
    } catch (e) {
      NP.anexar(conteudo, el("h1", { class: "titulo" }, "Robô não encontrado"),
        el("a", { class: "botao", href: "#/robos" }, "Ver os robôs"));
      return null;
    }

    let campos = {};          // chave -> campo (do servidor)
    let rascunho = {};        // chave -> valor em edição
    const pares = {};         // chave -> [[a, b], ...] (tabelas em edição)
    const caixaTrilha = el("ol", { class: "trilha" });
    const resumoTopo = el("p", { class: "robo-resumo" });
    const contador = el("div", { class: "resumo" });
    const botaoSalvar = el("button", { class: "botao botao-principal", type: "button", onclick: salvar }, "Salvar configuração");
    const botaoDesfazer = el("button", { class: "botao", type: "button", onclick: () => { carregar(dados.telas); } }, "Desfazer");

    function carregar(telas) {
      dados.telas = telas;
      campos = {};
      rascunho = {};
      for (const t of telas) for (const c of t.campos) if (c.chave) {
        campos[c.chave] = c;
        rascunho[c.chave] = JSON.parse(JSON.stringify(c.valor));
        if (c.tipo === "pares") pares[c.chave] = Object.entries(c.valor || {});
      }
      desenhar();
    }

    const valorDe = (chaveCampo) => {
      const c = campos[chaveCampo];
      if (c && c.tipo === "pares") return Object.fromEntries((pares[chaveCampo] || []).map(([a, b]) => [a.trim(), b.trim()]).filter(([a, b]) => a && b));
      return rascunho[chaveCampo];
    };
    const mudancas = () => Object.keys(campos).filter((k) => !igual(valorDe(k), campos[k].valor));
    const diferencasDoPadrao = () => Object.keys(campos).filter((k) => !igual(valorDe(k), campos[k].padrao));

    function visivel(c) {
      if (!c.visivel_se) return true;
      return Object.entries(c.visivel_se).every(([k, v]) => String(valorDe(k)) === String(v));
    }

    function atualizarBarra() {
      const n = mudancas().length;
      contador.textContent = n ? `${fmt.plural(n, "mudança ainda não salva", "mudanças ainda não salvas")}` : "Tudo salvo.";
      botaoSalvar.disabled = !n;
      botaoDesfazer.disabled = !n;
      const d = diferencasDoPadrao().length;
      botaoPadrao.hidden = !d && !n;
      const op = NP.operadora(opId);
      NP.anexar(NP.limpar(resumoTopo), el("strong", {}, "Hoje o robô cota assim: "),
        NP.resumoDoRobo(op, (k) => valorDe(`padroes.${k}`), { produto: valorDe("padroes.produto") }), ".",
        d ? el("span", { class: "discreto" }, ` ${fmt.plural(d, "escolha diferente", "escolhas diferentes")} dos padrões da Newport.`) : null);
    }

    function aoMudar(redesenhar = false) {
      if (redesenhar) desenhar(); else { atualizarBarra(); marcarDiferencas(); }
    }

    const notas = {};   // chave -> elemento "padrão da Newport: ..."
    function marcarDiferencas() {
      for (const [k, nota] of Object.entries(notas)) {
        const c = campos[k];
        const diferente = !igual(valorDe(k), c.padrao);
        nota.hidden = !diferente;
        if (diferente) {
          NP.anexar(NP.limpar(nota), el("span", { class: "ponto-mudado", "aria-hidden": "true" }),
            `Padrão da Newport: ${textoDoValor(c, c.padrao)}. `,
            el("button", { type: "button", class: "link-pequeno", onclick: () => {
              rascunho[k] = JSON.parse(JSON.stringify(c.padrao));
              if (c.tipo === "pares") pares[k] = Object.entries(c.padrao || {});
              aoMudar(true);
            } }, "Voltar ao padrão"));
        }
      }
    }

    let login = null;   // criado uma vez: redesenhar a página não apaga o que está sendo digitado
    function controle(c) {
      const k = c.chave;
      if (c.tipo === "credenciais") return login || (login = cartaoLogin(opId, dados.nome, c));
      if (c.tipo === "info") return el("div", { class: "discreto", style: { paddingTop: "8px" } }, c.texto);
      if (c.tipo === "sim_nao") return chave(c.rotulo, rascunho[k] === "sim", (v) => { rascunho[k] = v ? "sim" : "nao"; aoMudar(); });
      if (c.tipo === "escolha") return segmentos(c.opcoes, rascunho[k], (v) => { rascunho[k] = v; aoMudar(true); }, c.rotulo);
      if (c.tipo === "numero") {
        const n = el("span", { class: "faixa-qtd num", "aria-live": "polite" }, String(rascunho[k]));
        const mudar = (d) => { rascunho[k] = Math.max(c.minimo || 1, Math.min(c.maximo || 99, Number(rascunho[k]) + d)); n.textContent = String(rascunho[k]); aoMudar(); };
        return el("div", { class: "menor-preco" }, el("div", { class: "passo" },
          el("button", { type: "button", "aria-label": `Menos em ${c.rotulo}`, onclick: () => mudar(-1) }, "−"),
          el("button", { type: "button", "aria-label": `Mais em ${c.rotulo}`, onclick: () => mudar(1) }, "+")), n);
      }
      if (c.tipo === "texto") {
        const lista = c.sugestoes ? `sug-${k.replace(/\W/g, "-")}` : null;
        const exemplo = c.validar === "nome_pdf" ? el("div", { class: "ajuda exemplo-pdf" }) : null;
        // Como o robô monta o nome (nucleo/saidas.py, nome_pdf_destino): com "Com e sem" coparticipação, a versão
        // entra no lugar de {versao} ou logo depois do plano, para um PDF nunca substituir o outro.
        const ex = c.exemplo_pdf || {};    // o plano e as versões do exemplo vêm da operadora
        const nomeExemplo = (modelo, versao = "") => {
          let m = String(modelo || ""); let plano = String(ex.plano || "Plano").toUpperCase();
          if (versao && !m.includes("{versao}")) {
            if (m.includes("{plano_arquivo}")) plano += " " + versao;
            else m = /\.pdf$/i.test(m) ? m.slice(0, -4) + " {versao}.pdf" : m + " {versao}";
          }
          return m.replace(/\{plano_arquivo\}/g, plano).replace(/\{plano\}/g, ex.plano || "Plano").replace(/\{protocolo\}/g, "1234567")
            .replace(/\{cnpj\}/g, "12345678000199").replace(/\{acomodacao\}/g, "Apartamento").replace(/\{versao\}/g, versao)
            .replace(/\s+/g, " ").replace(/ \.pdf$/i, ".pdf");
        };
        const mostrarExemplo = () => {
          if (!exemplo) return;
          const versoes = ex.versoes || [];
          exemplo.textContent = `Exemplo: ${nomeExemplo(rascunho[k])}.` + (versoes.length
            ? ` ${ex.frase_versoes || "Com as versões"}: ${versoes.map((v) => nomeExemplo(rascunho[k], v)).join(" e ")}.` : "");
        };
        mostrarExemplo();
        return el("div", {},
          el("input", { class: "campo", id: `cfg-${k}`, value: rascunho[k] || "", list: lista, placeholder: c.exemplo || "",
            oninput: (e) => { rascunho[k] = e.target.value; mostrarExemplo(); aoMudar(); } }),
          lista ? el("datalist", { id: lista }, c.sugestoes.map((x) => el("option", { value: x }))) : null, exemplo);
      }
      if (c.tipo === "faixas") {
        return el("div", { class: "faixas-escolha", role: "group", "aria-label": c.rotulo }, FAIXAS.map((f) => {
          const caixa = el("input", { type: "checkbox", value: f });
          caixa.checked = (rascunho[k] || []).includes(f);
          caixa.addEventListener("change", () => {
            const atual = new Set(rascunho[k] || []);
            if (caixa.checked) atual.add(f); else atual.delete(f);
            rascunho[k] = FAIXAS.filter((x) => atual.has(x));
            aoMudar();
          });
          return el("label", { class: "faixa-chip" }, caixa, el("span", {}, f));
        }));
      }
      if (c.tipo === "planos") {
        const grupos = {};
        for (const p of dados.planos) (grupos[p.acomodacao] = grupos[p.acomodacao] || []).push(p);
        return el("div", { class: "planos" }, Object.keys(grupos).sort().map((acom) => el("div", {}, el("h3", {}, acom),
          grupos[acom].map((p) => {
            const rotulo = `${p.nome} | ${p.acomodacao}`;
            const caixa = el("input", { type: "checkbox", value: rotulo });
            caixa.checked = (rascunho[k] || []).includes(rotulo);
            const item = el("label", { class: `plano-item ${caixa.checked ? "marcado" : ""}` }, caixa, el("span", {}, p.nome));
            caixa.addEventListener("change", () => {
              const atual = (rascunho[k] || []).filter((x) => x !== rotulo);
              if (caixa.checked) atual.push(rotulo);
              rascunho[k] = atual;
              item.classList.toggle("marcado", caixa.checked);
              aoMudar();
            });
            return item;
          }))));
      }
      if (c.tipo === "pares") return tabelaPares(pares[k], c.colunas || ["De", "Para"], c.exemplos || ["", ""], () => aoMudar());
      return el("span", {}, String(rascunho[k]));
    }

    function desenhar() {
      NP.limpar(caixaTrilha);
      for (const nome of Object.keys(notas)) delete notas[nome];
      for (const t of dados.telas) {
        const linhas = t.campos.filter(visivel).map((c) => {
          const nota = c.chave ? el("div", { class: "nota-padrao", hidden: true }) : null;
          if (c.chave) notas[c.chave] = nota;
          const rotuloEsquerda = c.tipo === "sim_nao" ? "" : c.rotulo;
          return el("div", { class: "form-linha" },
            c.tipo === "texto" ? el("label", { for: `cfg-${c.chave}` }, rotuloEsquerda) : el("div", { class: "rotulo" }, rotuloEsquerda),
            el("div", {}, controle(c), c.ajuda ? el("div", { class: "ajuda" }, c.ajuda) : null, nota));
        });
        NP.anexar(caixaTrilha, el("li", { class: `passo-robo ${linhas.length ? "" : "sem-campos"}`, id: `tela-${t.etapa}` },
          el("div", { class: "passo-cabeca" }, el("h2", { class: "passo-nome" }, t.titulo), el("p", { class: "passo-faz" }, t.faz)),
          linhas.length ? el("div", { class: "passo-campos" }, linhas) : null));
      }
      atualizarBarra();
      marcarDiferencas();
    }

    async function salvar() {
      const valores = Object.fromEntries(mudancas().map((k) => [k, valorDe(k)]));
      botaoSalvar.disabled = true;
      try {
        const r = await NP.api("PUT", `/api/robos/${opId}`, { valores });
        await NP.carregarBase();
        carregar(r.telas);
        NP.aviso("Configuração salva. O robô usa estas escolhas a partir da próxima cotação.");
      } catch (e) {
        NP.aviso(e.message, { tipo: "erro", duracao: 9000 });
        if (e.dados && e.dados.campo) {
          const alvo = document.getElementById(`cfg-${e.dados.campo}`);
          if (alvo) alvo.focus();
        }
        atualizarBarra();
      }
    }

    const botaoPadrao = el("button", { class: "botao", type: "button", onclick: async () => {
      const ok = await NP.confirmar({
        titulo: "Voltar aos padrões da Newport?",
        texto: ["Todas as escolhas deste robô voltam a ser as do padrão da Newport.",
          "Cotações já emitidas não mudam."],
        ok: "Voltar aos padrões", principal: false,
      });
      if (!ok) return;
      try {
        const r = await NP.api("DELETE", `/api/robos/${opId}`);
        await NP.carregarBase();
        carregar(r.telas);
        NP.aviso("O robô voltou aos padrões da Newport.");
      } catch (e) { NP.aviso(e.message, { tipo: "erro" }); }
    } }, "Voltar aos padrões da Newport");

    const op = NP.operadora(opId) || dados;
    const conexao = (NP.estado.robo.conexao || {})[opId] || dados.conexao || "desconectado";
    NP.anexar(conteudo,
      el("div", { class: "robo-cabeca", style: { "--cor-op": dados.cor } },
        el("div", {},
          el("h1", { class: "titulo" }, `Robô da ${dados.nome}`),
          el("p", { class: "subtitulo" }, `${dados.produto}. O robô usa estas escolhas em todas as suas cotações, `
            + "até você mudar de novo. Para uma cotação só, use “Mudar só nesta cotação” na Nova cotação.")),
        el("div", { class: "conexao-status", style: { color: "var(--texto-2)" } }, el("span", { class: `ponto ${conexao}` }), NP.CONEXAO[conexao])),
      el("section", { class: "painel robo-topo", style: { "--cor-op": op.cor || dados.cor } }, resumoTopo),
      el("section", { class: "painel" },
        el("h2", { class: "secao" }, "O caminho do robô no portal"),
        el("p", { class: "secao-ajuda" }, "As telas na ordem em que o robô passa por elas, com o que ele preenche em cada uma."),
        caixaTrilha),
      el("div", { class: "barra-acao" }, contador, el("div", { class: "acoes" }, botaoPadrao, botaoDesfazer, botaoSalvar)));
    carregar(dados.telas);
    if (rota.consulta.get("login")) {
      const passo = document.getElementById("tela-login");
      if (passo) setTimeout(() => { passo.scrollIntoView({ block: "start" }); document.querySelector(".login-campos input").focus(); }, 0);
    }

    NP.antesDeSair = () => (mudancas().length ? "Há mudanças na configuração do robô que ainda não foram salvas." : "");
    return () => { NP.antesDeSair = null; };
  };
})();
