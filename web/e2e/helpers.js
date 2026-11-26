/** Mocks da API Benefits e do robô (8600) — o smoke nunca fala com 8002/8600 reais. */

export const ESTUDO_DEMO = {
  id: "demo-1",
  empresa: "Demo Ltda",
  titulo: "Renovação 2026",
  status: "rascunho",
  status_exibicao: "Em andamento",
  formato_exibicao: "Renovação",
  ultima_alteracao: "2026-01-15T12:00:00Z",
  beneficiarios_incluidos: 12,
  beneficiarios_rotulo: "12 beneficiários",
};

export const RASCUNHO_DEMO = {
  formato: "renovacao",
  subgrupos_atuais: [
    { id: "sg1", nome: "Plano A", plano_nome: "Plano A", reajuste_bps: 1000 },
    { id: "sg2", nome: "Plano B", plano_nome: "Plano B", reajuste_bps: 1000 },
  ],
  opcoes_proposta: [],
  vidas: [],
  escolhas: {
    data_referencia_idade: "2026-01-01",
    baseline_escolhido: { confirmado: false, valor: "vigente" },
    precedencia_atual_vida: { confirmado: false, valor: null },
  },
};

const OP_COMPLETA = {
  id: "amil",
  nome: "Amil",
  produto: "PME",
  conexao: "desconectado",
  login: { guardadas: false },
  textos: { login_livre: "o login da Amil", nome_pdf: "AMIL" },
  campos: [
    { chave: "produto", rotulo: "Produto", tipo: "escolha", robo: true, opcoes: [["pme", "PME"]] },
  ],
  etapas: [{ id: "login", nome: "Login" }, { id: "planos", nome: "Planos" }],
};

const OP_ANTIGA = {
  id: "amil",
  nome: "Amil",
  produto: "PME",
  conexao: "desconectado",
};

const ESTADO_REAL = {
  simulador: false,
  retencao_dias: 90,
  codigo: { commit: "abc1234" },
  robo: { atual: null, na_fila: [] },
};

const ESTADO_TREINO = {
  ...ESTADO_REAL,
  simulador: true,
};

const ESTADO_ANTIGO = {
  simulador: false,
  robo: {},
};

export const CENARIOS_ROBO = {
  off: { modo: "off" },
  real: { modo: "json", operadoras: [OP_COMPLETA], estado: ESTADO_REAL },
  treino: { modo: "json", operadoras: [OP_COMPLETA], estado: ESTADO_TREINO },
  antigo: { modo: "json", operadoras: [OP_ANTIGA], estado: ESTADO_ANTIGO },
};

function json(route, body, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export async function interceptarApi(page) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.port === "8600") return route.fallback();
    const path = url.pathname;
    if (path === "/api/estudos") return json(route, [ESTUDO_DEMO]);
    if (path === `/api/estudos/${ESTUDO_DEMO.id}`) return json(route, ESTUDO_DEMO);
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/rascunho`) return json(route, RASCUNHO_DEMO);
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/pendencias`) return json(route, []);
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/conferencia-siscor`) return json(route, { linhas: [], estatisticas: null });
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/resumo-plano-atual`) return json(route, null);
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/extracao-cotacao`) return json(route, { extracoes: [] });
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/rede-selecao`) {
      return json(route, { secoes: [], colunas: [], excluidos: [], revisada: false });
    }
    if (path === `/api/estudos/${ESTUDO_DEMO.id}/snapshot-aprovado`) return json(route, null);
    if (path === "/api/simular-rede/opcoes") {
      return json(route, {
        data_base_rede: "26/11/2026",
        total_prestadores: 1071,
        total_principais: 395,
        operadoras: [
          { nome: "Alice", planos: [{ chave: "1", rotulo: "Alice Smart" }] },
          { nome: "Amil", planos: [{ chave: "20", rotulo: "S750" }] },
        ],
        ufs: [
          {
            uf: "SP",
            municipios: [{ chave: "SP.SAO PAULO", rotulo: "Sao Paulo", zonas: ["OESTE"] }],
          },
          {
            uf: "RJ",
            municipios: [
              { chave: "RJ.RIO DE JANEIRO", rotulo: "Rio De Janeiro", zonas: ["BARRA", "ZONA SUL"] },
            ],
          },
        ],
      });
    }
    if (path === "/api/simular-rede/laboratorios/opcoes") {
      return json(route, {
        data_base_rede: "26/11/2026",
        total_prestadores: 2683,
        total_principais: 10,
        operadoras: [
          { nome: "Alice", planos: [{ chave: "1", rotulo: "Alice Smart" }] },
          { nome: "Amil", planos: [{ chave: "10", rotulo: "S750" }] },
        ],
        ufs: [
          {
            uf: "SP",
            municipios: [{ chave: "SP.SAO PAULO", rotulo: "Sao Paulo", zonas: [] }],
          },
        ],
      });
    }
    if (path === "/api/simular-rede/por-hospital") {
      const q = url.searchParams.getAll("q").join(" ").trim();
      if (!q || q === ";") {
        return json(route, { detail: "Digite o nome de ao menos um hospital." }, 422);
      }
      const linhas = [];
      if (/einstein/i.test(q)) {
        linhas.push({
          linha_id: "l-einstein",
          prestador: "HOSPITAL ALBERT EINSTEIN",
          prestador_nome: "HOSPITAL ALBERT EINSTEIN",
          bairro: "MORUMBI",
          principal: true,
          celulas: { 20: "H" },
        });
      }
      if (/samaritano/i.test(q)) {
        linhas.push(
          {
            linha_id: "l-sam-barra",
            prestador: "HOSP SAMARITANO",
            prestador_nome: "HOSP SAMARITANO",
            bairro: "BARRA DA TIJUCA",
            principal: true,
            celulas: { 20: "H" },
          },
          {
            linha_id: "l-sam-bot",
            prestador: "HOSP SAMARITANO",
            prestador_nome: "HOSP SAMARITANO",
            bairro: "BOTAFOGO",
            principal: true,
            celulas: { 20: "H" },
          }
        );
      }
      if (!linhas.length) {
        return json(route, {
          modo: "hospital",
          colunas: [],
          blocos: [],
          total_linhas: 0,
          total_encontrado: 0,
          ocultos_nao_principais: 0,
          aviso: "Nenhum prestador da base corresponde à busca e aos filtros.",
        });
      }
      return json(route, {
        modo: "hospital",
        colunas: [{ chave: "20", operadora: "Amil", plano: "S750" }],
        blocos: [{ municipio: "SP.SAO PAULO", titulo: "Sao Paulo · SP", linhas }],
        total_linhas: linhas.length,
        total_encontrado: linhas.length,
        ocultos_nao_principais: 0,
        mostrando_todos: false,
      });
    }
    if (path === "/api/simular-rede/laboratorios/por-laboratorio") {
      const q = url.searchParams.getAll("q").join(" ").trim();
      if (!q || q === ";") {
        return json(route, { detail: "Digite o nome de ao menos um laboratório." }, 422);
      }
      const linhas = [];
      if (/delboni/i.test(q)) {
        linhas.push({
          linha_id: "marca:DELBONI",
          prestador: "Delboni",
          prestador_nome: "Delboni",
          principal: true,
          municipios: ["Sao Paulo"],
          celulas: { 10: "✓" },
        });
      }
      if (/lavoisier/i.test(q)) {
        linhas.push({
          linha_id: "marca:LAVOISIER",
          prestador: "Lavoisier",
          prestador_nome: "Lavoisier",
          principal: true,
          municipios: ["Sao Paulo"],
          celulas: { 10: "✓" },
        });
      }
      return json(route, {
        modo: "laboratorio",
        colunas: linhas.length ? [{ chave: "10", operadora: "Amil", plano: "S750" }] : [],
        blocos: linhas.length ? [{ titulo: "Laboratórios", municipio: "", linhas }] : [],
        total_linhas: linhas.length,
        total_encontrado: linhas.length,
        ocultos_nao_principais: 0,
        aviso: linhas.length ? null : "Nenhuma marca da lista corresponde à busca e aos filtros.",
      });
    }
    if (path === "/api/simular-rede/por-plano" || path === "/api/simular-rede/laboratorios/por-plano") {
      const plano = url.searchParams.get("plano") || "";
      if (!plano) {
        return json(route, { detail: "Plano não encontrado na base de rede." }, 422);
      }
      return json(route, {
        modo: "plano",
        colunas: [{ chave: plano, operadora: "Amil", plano: "S750" }],
        blocos: [],
        total_linhas: 0,
        total_encontrado: 0,
        ocultos_nao_principais: 0,
        requer_confirmacao: false,
      });
    }
    if (path === "/api/config") return json(route, { modo: "demo" });
    if (path === "/api/rpa-cotacoes/estado") return json(route, { ligado: false });
    if (path.startsWith("/api/estudos/") && !path.includes(`/estudos/${ESTUDO_DEMO.id}`)) {
      return json(route, { detail: "Estudo não encontrado" }, 404);
    }
    return json(route, {});
  });
}

export async function interceptarRobo(page, cenario) {
  await page.route("http://127.0.0.1:8600/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (path === "/api/eventos") {
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "data: {\"tipo\":\"ping\"}\n\n",
      });
    }
    if (cenario.modo === "off") {
      return json(route, { erro: "O robô de cotações não está no ar." }, 503);
    }
    if (path === "/api/operadoras") return json(route, cenario.operadoras);
    if (path === "/api/estado") return json(route, cenario.estado);
    if (path === "/api/cotacoes" || path.startsWith("/api/cotacoes")) return json(route, []);
    if (path === "/api/pendencias") return json(route, []);
    if (path === "/api/empresas") return json(route, []);
    if (path === "/api/geral") return json(route, { geral: {} });
    if (path.startsWith("/api/telas/")) return json(route, { telas: [] });
    return json(route, {});
  });
}

export function instalarSessaoDemo(page) {
  return page.addInitScript(() => {
    sessionStorage.setItem("benefits_demo_logado", "1");
  });
}

export function coletarFalhas(page) {
  const errosConsole = [];
  const excecoes = [];
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const texto = msg.text();
    if (/Download the React DevTools/i.test(texto)) return;
    if (/favicon/i.test(texto)) return;
    if (/127\.0\.0\.1:8600/i.test(texto)) return;
    if (/Failed to load resource/i.test(texto) && /8600|ERR_CONNECTION|503|404/i.test(texto)) return;
    errosConsole.push(texto);
  });
  page.on("pageerror", (err) => {
    excecoes.push(String(err && err.message ? err.message : err));
  });
  return { errosConsole, excecoes };
}

export async function assertTelaViva(page, dica) {
  const alerta = page.getByRole("alert").filter({ hasText: /não carregou/i });
  if (await alerta.count()) {
    throw new Error(`Tela de erro do Error Boundary em ${dica}`);
  }
  const root = page.locator("#root");
  const texto = ((await root.innerText()) || "").trim();
  if (texto.length < 12) {
    throw new Error(`Tela vazia em ${dica} (texto=${texto.length} chars)`);
  }
  const fundo = await page.evaluate(() => {
    const r = document.getElementById("root");
    return r ? r.getBoundingClientRect().height : 0;
  });
  if (fundo < 40) {
    throw new Error(`Tela branca em ${dica} (root height=${fundo})`);
  }
}
