/** Avanço do wizard: etapas 1, 2 e 4 gravam a confirmação no «Próxima etapa». */

import { formatarDiffCentavos } from "../money";

export const ETAPAS_CONFIRMA_NO_AVANCO = new Set(["base", "plano", "selecionados", "rede"]);

export function proximaEtapaClicavel(chave, passoAtual, ctx, proximaDisponivel) {
  if (ETAPAS_CONFIRMA_NO_AVANCO.has(chave)) return true;
  return proximaDisponivel(passoAtual, ctx);
}

export function mensagemExcecaoBase(excecoes) {
  return `${excecoes} exceção(ões) na base`;
}

export function mensagemLacunasAtribuicao(lacunasPorCenario) {
  const partes = (lacunasPorCenario || [])
    .map((faltando, i) =>
      faltando.length
        ? `Cenário ${i + 1}: falta escolher cotação para ${faltando.join(", ")}`
        : null
    )
    .filter(Boolean);
  return partes.length
    ? partes.join(" · ")
    : "Complete todas as escolhas antes de confirmar.";
}

export function rotuloOpcaoNome(nome, acomodacaoRotulo) {
  let texto = nome || "";
  if (acomodacaoRotulo) texto += ` (${acomodacaoRotulo})`;
  return texto;
}

export function rotuloOpcaoComDiff(nome, acomodacaoRotulo, diffCentavos) {
  const texto = rotuloOpcaoNome(nome, acomodacaoRotulo);
  if (diffCentavos == null) return texto;
  return `${texto} — ${formatarDiffCentavos(diffCentavos)}`;
}
