import { faixaRascunhoLigada } from "./faixaRascunho";

export default function FaixaRascunho({ ligada = faixaRascunhoLigada() }) {
  if (!ligada) return null;
  return (
    <div className="faixa-rascunho" role="status">
      <strong>RASCUNHO INTERNO</strong>
      <span> — cálculos ainda não homologados pela Newport.</span>
    </div>
  );
}
