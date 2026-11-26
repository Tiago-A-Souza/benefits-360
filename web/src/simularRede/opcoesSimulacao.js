/** Derivações puras das opções do Simular Rede (selects encadeados). */

/** Mínimo para Consultar / Enter: 2 caracteres (vale «A+»). */
export function temTermoConsulta(texto) {
  return (texto || "").trim().length >= 2;
}

export const LEGENDA_COBERTURA = [
  ["H", "Hospital geral"],
  ["HD", "Hospital-dia"],
  ["M", "Maternidade"],
  ["PS", "Pronto-socorro geral"],
];

export function municipiosDaUf(opcoes, uf) {
  if (!uf) return [];
  return opcoes?.ufs?.find((u) => u.uf === uf)?.municipios ?? [];
}

export function zonasDoMunicipio(opcoes, uf, municipio) {
  if (!municipio) return [];
  return municipiosDaUf(opcoes, uf).find((m) => m.chave === municipio)?.zonas ?? [];
}

export function planosDaOperadora(opcoes, operadora) {
  if (!operadora) return [];
  return opcoes?.operadoras?.find((o) => o.nome === operadora)?.planos ?? [];
}

/** Agrupa colunas consecutivas da mesma operadora (cabeçalho em dois níveis). */
export function gruposDeOperadora(colunas) {
  const grupos = [];
  for (const col of colunas || []) {
    const ultimo = grupos[grupos.length - 1];
    if (ultimo && ultimo.operadora === col.operadora) ultimo.colunas.push(col);
    else grupos.push({ operadora: col.operadora, colunas: [col] });
  }
  return grupos;
}

export function haFiltroGeografico({ uf, municipio, zona }) {
  return Boolean(uf || municipio || zona);
}

export function haRedeVerticalizada(blocos) {
  return (blocos || []).some((b) => (b.linhas || []).some((ln) => ln.rede_verticalizada));
}

export function textoContagem(resp) {
  if (!resp) return "";
  const n = resp.total_linhas;
  const base = `${n} ${n === 1 ? "prestador" : "prestadores"}`;
  if (resp.ocultos_nao_principais > 0 && !resp.mostrando_todos) {
    return `${base} · ${resp.ocultos_nao_principais} não principal(is) oculto(s)`;
  }
  return base;
}

export function textoContagemLabs(resp) {
  if (!resp) return "";
  const n = resp.total_linhas;
  const unidade = resp.mostrando_todos
    ? n === 1
      ? "laboratório"
      : "laboratórios"
    : n === 1
      ? "marca"
      : "marcas";
  let s = `${n} ${unidade}`;
  if (resp.total_encontrado > 0 && resp.total_encontrado !== n) {
    s += ` · ${resp.total_encontrado} encontrado(s)`;
  }
  if (resp.ocultos_nao_principais > 0 && !resp.mostrando_todos) {
    s += ` · ${resp.ocultos_nao_principais} não curada(s) oculta(s)`;
  }
  return s;
}
