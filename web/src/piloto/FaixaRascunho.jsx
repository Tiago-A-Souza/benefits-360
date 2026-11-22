/** Liga a faixa "RASCUNHO INTERNO". Build-time: VITE_FAIXA_RASCUNHO=1. */

export function faixaRascunhoLigada(valor = import.meta.env.VITE_FAIXA_RASCUNHO) {
  const v = String(valor ?? "").trim().toLowerCase();
  return v === "1" || v === "true" || v === "sim" || v === "on";
}

export default function FaixaRascunho({ ligada = faixaRascunhoLigada() }) {
  if (!ligada) return null;
  return (
    <div className="faixa-rascunho" role="status">
      <strong>RASCUNHO INTERNO</strong>
      <span> — cálculos ainda não homologados pela Newport.</span>
    </div>
  );
}
