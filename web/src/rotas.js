/** Rotas por hash — fonte única da tela visível (Meus estudos, Simular, Cotações, etapas). */

export const HASH_ESTUDOS = "#/estudos";
export const HASH_SIMULAR = "#/simular-rede";
export const HASH_COTACOES_INICIO = "#/inicio";
export const HASH_COTACOES_LISTA = "#/cotacoes";

/** Prefixos das abas/telas do módulo Cotações (nativa + robô). */
export const PREFIXOS_COTACOES = [
  "#/nova",
  "#/andamento/",
  "#/cotacoes",
  "#/conexoes",
  "#/inicio",
  "#/ajuda",
  "#/importar",
  "#/robos",
  "#/robo/",
];

export const HASH_ABA_COTACOES = {
  inicio: "#/inicio",
  nova: "#/nova",
  cotacoes: "#/cotacoes",
  importar: "#/importar",
  conexoes: "#/conexoes",
  robos: "#/robos",
  ajuda: "#/ajuda",
};

function hashBruto(hash) {
  return String(hash || "").trim();
}

export function ehHashCotacoes(hash) {
  const h = hashBruto(hash);
  return PREFIXOS_COTACOES.some((p) => {
    if (p.endsWith("/")) return h.startsWith(p);
    return h === p || h.startsWith(`${p}/`) || h.startsWith(`${p}?`);
  });
}

function queryPedeCotacoes(search) {
  const q = new URLSearchParams(String(search || "").replace(/^\?/, ""));
  return q.get("cotacoes-nativa") === "1";
}

function hashVazio(hash) {
  const h = hashBruto(hash);
  return !h || h === "#" || h === "#/";
}

/**
 * Interpreta o endereço. `search` só vale quando o hash está vazio
 * (`?cotacoes-nativa=1` abre Cotações). Hash explícito de estudo/simular
 * nunca é sobrescrito pela query.
 */
export function parseHash(hash, search = "") {
  const h = hashBruto(hash);

  if (hashVazio(h)) {
    if (queryPedeCotacoes(search)) return { area: "cotacoes" };
    return { area: "estudos" };
  }

  if (h === HASH_ESTUDOS) return { area: "estudos" };
  if (h === HASH_SIMULAR) return { area: "simular" };

  const mEstudo = h.match(/^#\/estudos\/([^/]+)(?:\/etapa\/(\d+))?\/?$/);
  if (mEstudo) {
    let estudoId = mEstudo[1];
    try {
      estudoId = decodeURIComponent(estudoId);
    } catch {
      return { area: "invalida", motivo: "estudo" };
    }
    if (!estudoId) return { area: "invalida", motivo: "estudo" };
    const passo = mEstudo[2] == null ? 1 : Number(mEstudo[2]);
    if (!Number.isInteger(passo) || passo < 1) {
      return { area: "invalida", motivo: "etapa" };
    }
    return { area: "estudo", estudoId, passo };
  }

  if (ehHashCotacoes(h)) return { area: "cotacoes" };

  return { area: "invalida", motivo: "desconhecida" };
}

export function parseHashAtual() {
  if (typeof window === "undefined") return { area: "estudos" };
  return parseHash(window.location.hash, window.location.search);
}

export function hashEstudo(estudoId, passo = 1) {
  const id = encodeURIComponent(String(estudoId || "").trim());
  const n = Number.isInteger(passo) && passo >= 1 ? passo : 1;
  return `#/estudos/${id}/etapa/${n}`;
}

export function hashAtualNavegador() {
  if (typeof window === "undefined") return "";
  return window.location.hash || "";
}

/**
 * Empilha o hash (Voltar/Avançar) ou substitui (normalizar URL vazia, corrigir etapa).
 * Dispara `hashchange` após replaceState para a casca reagir.
 */
export function irPara(hash, { replace = false } = {}) {
  if (typeof window === "undefined") return;
  const alvo = String(hash || "").startsWith("#") ? String(hash) : `#${hash}`;
  const atual = window.location.hash || "";
  if (atual === alvo) return;
  if (replace) {
    const u = new URL(window.location.href);
    u.hash = alvo.slice(1);
    window.history.replaceState({}, "", u);
    window.dispatchEvent(new HashChangeEvent("hashchange"));
    return;
  }
  window.location.hash = alvo;
}

export function normalizarHashInicial() {
  if (typeof window === "undefined") return;
  const h = window.location.hash || "";
  if (!hashVazio(h)) return;
  const rota = parseHashAtual();
  if (rota.area === "estudos") irPara(HASH_ESTUDOS, { replace: true });
}

export function ehErroSemAcesso(err) {
  const status = err && err.status;
  return status === 404 || status === 403;
}
