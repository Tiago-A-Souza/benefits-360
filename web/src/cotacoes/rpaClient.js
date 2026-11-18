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
  constructor(codigo, mensagem, status = null) {
    super(mensagem);
    this.codigo = codigo;
    this.status = status;
    this.name = "RpaClienteErro";
  }
}

/**
 * @param {string} metodo
 * @param {string} caminho  ex.: "/api/estado"
 * @param {object} [corpo]
 */
export async function chamarRpa(metodo, caminho, corpo) {
  const base = urlBaseRpa();
  const url = `${base}${caminho.startsWith("/") ? caminho : `/${caminho}`}`;
  const init = { method: metodo, headers: {} };
  if (metodo !== "GET" && metodo !== "HEAD") {
    init.headers["X-Newport-Tela"] = "1";
  }
  if (corpo !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(corpo);
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
  if (!resp.ok) {
    const msg =
      (dados && (dados.erro || dados.mensagem || dados.detail)) ||
      `Falha ao falar com o robô (${resp.status}).`;
    throw new RpaClienteErro("ROBO_HTTP", String(msg), resp.status);
  }
  return dados;
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
