/** Marca visual das operadoras (logo + cor). O id enviado ao robô continua sulamerica | bradesco | amil.
 * Cores principais amostradas dos arquivos em web/public/operadoras/ (pixels saturados opacos).
 * Bradesco SVG não traz fill (no site a marca é pintada de vermelho); usamos o vermelho oficial. */

function rgba(hex, a) {
  const h = hex.replace("#", "");
  const n = parseInt(h, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${a})`;
}

function marca(nome, logo, cor) {
  return { nome, logo, cor, corSuave: rgba(cor, 0.12), corCabeca: rgba(cor, 0.06) };
}

export const MARCA_OPERADORAS = {
  sulamerica: marca("SulAmérica", "/operadoras/sulamerica.png", "#F08810"),
  bradesco: marca("Bradesco", "/operadoras/bradesco.svg", "#CC092F"),
  amil: marca("Amil", "/operadoras/amil.png", "#4018F8"),
};

const FALLBACK = marca("", null, "#0B1F36");

export function marcaOperadora(id) {
  const chave = String(id || "").toLowerCase();
  const m = MARCA_OPERADORAS[chave];
  if (!m) return { ...FALLBACK, nome: id || "" };
  return m;
}

export function estiloMarcaOperadora(id) {
  const m = marcaOperadora(id);
  return { "--cor-op": m.cor, "--cor-op-suave": m.corSuave, "--cor-op-cabeca": m.corCabeca };
}

export function classeCartaoOperadora(ativo) {
  return `nativa-op-cartao${ativo ? " nativa-op-cartao--ativo" : ""}`;
}

export function attrsCartaoOperadora(id, ativo) {
  const m = marcaOperadora(id);
  return {
    className: classeCartaoOperadora(ativo),
    style: estiloMarcaOperadora(id),
    "data-cor-op": m.cor,
  };
}
