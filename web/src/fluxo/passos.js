/** Helpers de fluxo do wizard operacional. */

export const PASSOS_FLUXO = [
  { chave: "base", titulo: "Base atual" },
  { chave: "plano", titulo: "Plano atual" },
  { chave: "cotacoes", titulo: "Cotações" },
  {
    chave: "selecionados",
    titulo: "Correspondência com os planos atuais",
    somenteMultiplosPlanosAtuais: true,
  },
  { chave: "comparativo", titulo: "Comparativo" },
  { chave: "apresentacao", titulo: "Apresentação" },
];

export function exigeCorrespondenciaManual(rascunho) {
  return (rascunho?.subgrupos_atuais?.length || 0) > 1;
}

export function passosVisiveis(rascunho) {
  const multi = exigeCorrespondenciaManual(rascunho);
  const filtrados = PASSOS_FLUXO.filter(
    (p) => !p.somenteMultiplosPlanosAtuais || multi
  );
  return filtrados.map((p, i) => ({ ...p, ordem: i + 1 }));
}

export function chavePassoVisivel(rascunho, indicePasso) {
  const passos = passosVisiveis(rascunho);
  if (indicePasso < 1 || indicePasso > passos.length) return null;
  return passos[indicePasso - 1].chave;
}

/** @deprecated use PASSOS_FLUXO / passosVisiveis */
export const PASSOS = PASSOS_FLUXO.map((p, i) => ({
  id: i + 1,
  titulo: p.titulo,
  chave: p.chave,
}));
