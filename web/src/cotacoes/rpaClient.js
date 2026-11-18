/**
 * Cliente do navegador → robô local (127.0.0.1:8600), sem passar pelo Benefits.
 * Base: VITE_RPA_URL (padrão http://127.0.0.1:8600).
 */

export const RPA_URL_PADRAO = "http://127.0.0.1:8600";

export function urlBaseRpa() {
  const bruto = import.meta.env.VITE_RPA_URL;
  if (typeof bruto === "string" && bruto.trim()) return bruto.trim().replace(/\/$/, "");
  return RPA_URL_PADRAO;
}

export class RpaClienteErro extends Error {
  constructor(codigo, mensagem, status = null, dados = null) {
    super(mensagem);
    this.codigo = codigo;
    this.status = status;
    this.dados = dados;
    this.name = "RpaClienteErro";
  }
}

/**
 * @param {string} metodo
 * @param {string} caminho  ex.: "/api/estado"
 * @param {object} [corpo]
 * @param {{ aceitarErro?: boolean }} [opcoes]
 */
export async function chamarRpa(metodo, caminho, corpo, opcoes = {}) {
  const base = urlBaseRpa();
  const url = `${base}${caminho.startsWith("/") ? caminho : `/${caminho}`}`;
  const init = { method: metodo, headers: {} };
  if (metodo !== "GET" && metodo !== "HEAD") {
    init.headers["X-Newport-Tela"] = "1";
  }
  if (corpo !== undefined && !(corpo instanceof FormData)) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(corpo);
  } else if (corpo instanceof FormData) {
    init.body = corpo;
  }
  let resp;
  try {
    resp = await fetch(url, init);
  } catch {
    throw new RpaClienteErro(
      "ROBO_DESLIGADO",
      `O robô de cotações não está no ar em ${base}.`,
    );
  }
  let dados = null;
  const tipo = resp.headers.get("content-type") || "";
  if (tipo.includes("application/json")) {
    try {
      dados = await resp.json();
    } catch {
      dados = null;
    }
  }
  if (!resp.ok && !opcoes.aceitarErro) {
    const msg =
      (dados && (dados.erro || dados.mensagem || dados.detail)) ||
      `Falha ao falar com o robô (${resp.status}).`;
    throw new RpaClienteErro("ROBO_HTTP", String(msg), resp.status, dados);
  }
  return dados;
}

export async function baixarUrlRpa(caminho, nomeSugerido) {
  const base = urlBaseRpa();
  const url = `${base}${caminho.startsWith("/") ? caminho : `/${caminho}`}`;
  let resp;
  try {
    resp = await fetch(url);
  } catch {
    throw new RpaClienteErro("ROBO_DESLIGADO", `O robô de cotações não está no ar em ${base}.`);
  }
  if (!resp.ok) {
    throw new RpaClienteErro("ROBO_HTTP", `Não deu para baixar (${resp.status}).`, resp.status);
  }
  const blob = await resp.blob();
  const disp = resp.headers.get("content-disposition") || "";
  const m = disp.match(/filename\*?=(?:UTF-8'')?"?([^";]+)"?/i);
  const nome = nomeSugerido || (m ? decodeURIComponent(m[1]) : "arquivo");
  const href = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = href;
  a.download = nome;
  a.hidden = true;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(href);
}

/**
 * SSE /api/eventos. Devolve { fechar }.
 * onErro recebe RpaClienteErro (rede) ou Error.
 */
export function ouvirEventosRpa(onEvento, onErro) {
  const base = urlBaseRpa();
  let fonte;
  try {
    fonte = new EventSource(`${base}/api/eventos`);
  } catch (e) {
    onErro?.(
      new RpaClienteErro("ROBO_DESLIGADO", `O robô de cotações não está no ar em ${base}.`),
    );
    return { fechar() {} };
  }
  fonte.onmessage = (msg) => {
    try {
      onEvento?.(JSON.parse(msg.data));
    } catch {
      /* ignore linha malformada */
    }
  };
  fonte.onerror = () => {
    onErro?.(
      new RpaClienteErro("ROBO_DESLIGADO", `O robô de cotações não está no ar em ${base}.`),
    );
  };
  return {
    fechar() {
      fonte.close();
    },
  };
}
