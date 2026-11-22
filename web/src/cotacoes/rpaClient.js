/**
 * Cliente do navegador → robô local (127.0.0.1:8600), sem passar pelo Benefits.
 * Base: VITE_RPA_URL (padrão http://127.0.0.1:8600).
 */

export const RPA_URL_PADRAO = "http://127.0.0.1:8600";

/** Chrome 142+: isenta mixed content no loopback. Navegador antigo ignora a chave. */
export function opcoesChamadaRpa(init = {}) {
  return { ...init, targetAddressSpace: "loopback" };
}

export function urlBaseRpa() {
  const bruto = import.meta.env.VITE_RPA_URL;
  if (typeof bruto === "string" && bruto.trim()) return bruto.trim().replace(/\/$/, "");
  return RPA_URL_PADRAO;
}

const CHAVES_SEGREDO = ["senha", "password", "codigo"];

/** Tira valores secretos de um texto (erro, log). Nunca use o retorno para reenviar. */
export function ocultarSegredosNoTexto(texto, corpo) {
  let t = String(texto ?? "");
  if (!corpo || typeof corpo !== "object" || Array.isArray(corpo)) return t;
  for (const k of CHAVES_SEGREDO) {
    const v = corpo[k];
    if (typeof v === "string" && v.length >= 2) t = t.split(v).join("•••");
  }
  return t;
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
    resp = await fetch(url, opcoesChamadaRpa(init));
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
    const bruto =
      (dados && (dados.erro || dados.mensagem || dados.detail)) ||
      `Falha ao falar com o robô (${resp.status}).`;
    const msg = ocultarSegredosNoTexto(String(bruto), corpo);
    throw new RpaClienteErro("ROBO_HTTP", msg, resp.status, dados);
  }
  return dados;
}

export async function baixarUrlRpa(caminho, nomeSugerido) {
  const base = urlBaseRpa();
  const url = `${base}${caminho.startsWith("/") ? caminho : `/${caminho}`}`;
  let resp;
  try {
    resp = await fetch(url, opcoesChamadaRpa());
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
    // EventSource não aceita targetAddressSpace; 127.0.0.1 já é loopback confiável no Chromium.
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

/** Texto discreto da versão do robô. Aviso se faltar codigo.commit — não bloqueia. */
export function resumoVersaoRobo(estado) {
  const commit = estado && estado.codigo && estado.codigo.commit;
  if (!commit) {
    return {
      texto: "Versão do robô indisponível — atualize o robô se as telas não baterem.",
      antigo: true,
    };
  }
  return { texto: `Robô ${commit}`, antigo: false };
}
