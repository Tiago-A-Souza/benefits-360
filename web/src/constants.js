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
  {
    value: "operadora",
    label: "Operadora - Sem IOF",
  },
  {
    value: "seguradora",
    label: "Seguradora - Com IOF",
  },
];

export const MODALIDADES = [
  { value: "adesao", label: "Adesão" },
  { value: "compulsorio", label: "Compulsório" },
];

export const REGIMES_COPART = [
  { value: "sem", label: "Sem coparticipação" },
  { value: "parcial", label: "Parcial (terapias)" },
  { value: "percentual", label: "Percentual" },
];

export const ACOMODACOES = [
  { value: "enfermaria", label: "Enfermaria" },
  { value: "apartamento", label: "Apartamento" },
];

/** Opções selecionáveis de price_basis na UI. desconhecido/nao_aplica
 *  permanecem no modelo (extração / operadora), mas não são escolhas do analista. */
export const BASES_IOF = [
  { value: "inclui_iof", label: "Inclui IOF" },
  { value: "exclui_iof", label: "Exclui IOF" },
];

export function novoId(prefixo) {
  return `${prefixo}-${crypto.randomUUID().slice(0, 8)}`;
}

export function faixaVazia(faixa) {
  return {
    faixa,
    valor_centavos: null,
    // Mesmo default do caminho PDF→rascunho (_quantidade_cotada_faixa → 0).
    // null continua inválido (APP-QTD-001) se vier de outro caminho.
    quantidade_cotada: 0,
    price_basis: "desconhecido",
    proveniencia: { origem: "manual", extrator_versao: "manual", confirmado: false },
  };
}

/** Sugestões de tipo fiscal / base IOF por operadora (piloto IVTEC). Não são regra do motor. */
export const SUGESTOES_FISCAIS_OPERADORA = [
  {
    match: /^amil$/i,
    tipo_fiscal: "operadora",
    price_basis: "exclui_iof",
    evidencia: "Amil opera como operadora (sem IOF de seguradora) — padrão visto no IVTEC.",
  },
  {
    match: /bradesco/i,
    tipo_fiscal: "seguradora",
    price_basis: "exclui_iof",
    evidencia: "Bradesco imprime faixas sem IOF e IOF à parte no total — padrão IVTEC.",
  },
  {
    match: /sul\s*am[eé]rica|sulamerica/i,
    tipo_fiscal: "seguradora",
    price_basis: "exclui_iof",
    evidencia: "SulAmérica tratada como seguradora no piloto; confira se o PDF já inclui impostos.",
  },
  {
    match: /porto/i,
    tipo_fiscal: "seguradora",
    price_basis: "exclui_iof",
    evidencia: "Porto costuma cotar como seguradora; revise a base de IOF no PDF.",
  },
];

export function sugestaoFiscalPorOperadora(operadora) {
  const nome = String(operadora || "").trim();
  if (!nome) return null;
  for (const s of SUGESTOES_FISCAIS_OPERADORA) {
    if (s.match.test(nome)) {
      return {
        tipo_fiscal: s.tipo_fiscal,
        price_basis: s.price_basis,
        evidencia: s.evidencia,
      };
    }
  }
  return null;
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
