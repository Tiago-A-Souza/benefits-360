export const OPERADORAS = [
  "Amil",
  "Bradesco Saúde",
  "SulAmérica",
  "Porto Seguro",
  "Unimed",
  "Omint",
  "Hapvida",
  "Outra",
];

export const TIPOS_FISCAIS = [
  { value: "seguradora", label: "Seguradora (contrato)" },
  { value: "operadora", label: "Operadora (administrado)" },
];

export const MODALIDADES = [
  { value: "adesao", label: "Adesão" },
  { value: "compulsorio", label: "Compulsório" },
  { value: "desconhecido", label: "Desconhecido" },
];

export const REGIMES_COPART = [
  { value: "sem", label: "Sem coparticipação" },
  { value: "parcial", label: "Parcial" },
  { value: "percentual", label: "Percentual" },
  { value: "customizada", label: "Customizada" },
];

export const BASES_IOF = [
  { value: "inclui_iof", label: "Inclui IOF" },
  { value: "exclui_iof", label: "Exclui IOF" },
  { value: "desconhecido", label: "Desconhecido" },
  { value: "nao_aplica", label: "Não se aplica" },
];

export const PASSOS = [
  { id: 1, titulo: "Base atual", chave: "base" },
  { id: 2, titulo: "Plano atual", chave: "plano" },
  { id: 3, titulo: "Cotações", chave: "cotacoes" },
  { id: 4, titulo: "Planos selecionados", chave: "selecionados" },
  { id: 5, titulo: "Comparativo financeiro", chave: "comparativo" },
  { id: 6, titulo: "Apresentação", chave: "apresentacao" },
];

export function novoId(prefixo) {
  return `${prefixo}-${crypto.randomUUID().slice(0, 8)}`;
}

export function faixaVazia(faixa) {
  return {
    faixa,
    valor_centavos: null,
    quantidade_cotada: null,
    price_basis: "desconhecido",
    proveniencia: { origem: "manual", extrator_versao: "manual", confirmado: false },
  };
}

export function tabelaVazia() {
  return Array.from({ length: 10 }, (_, i) => faixaVazia(i));
}

export function ensureRegime(rascunho, tipo) {
  const id = `regime-${tipo}`;
  if (!rascunho.regimes_copart.some((r) => r.id === id)) {
    rascunho.regimes_copart.push({ id, tipo });
  }
  return id;
}
