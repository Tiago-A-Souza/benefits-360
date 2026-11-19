/** Liga a faixa "RASCUNHO INTERNO". Build-time: VITE_FAIXA_RASCUNHO=1. */

export function faixaRascunhoLigada(valor = import.meta.env.VITE_FAIXA_RASCUNHO) {
  const v = String(valor ?? "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "sim" || v === "on";
}
