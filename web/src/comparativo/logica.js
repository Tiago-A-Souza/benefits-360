/** Filtros e ordenação usando apenas campos numéricos da API. */

/** Igual a MAX_PROPOSTAS_POR_PAGINA do renderer HTML. */
export const MAX_PROPOSTAS_POR_PAGINA = 3;

export function paginarPropostas(propostas, tamanho = MAX_PROPOSTAS_POR_PAGINA) {
  const lista = propostas || [];
  if (!lista.length) return [[]];
  const paginas = [];
  for (let i = 0; i < lista.length; i += tamanho) {
    paginas.push(lista.slice(i, i + tamanho));
  }
  return paginas;
}

export function filtrarPropostas(propostas, filtros) {
  return propostas.filter((p) => {
    if (!p.calculo_realizado) return false;
    if (filtros.grupoRegime && p.grupo_regime !== filtros.grupoRegime) return false;
    if (filtros.acomodacao && (p.acomodacao || "") !== filtros.acomodacao) return false;
    if (filtros.operadora && p.operadora !== filtros.operadora) return false;
    const mensal = p.numerico?.proposta_mensal_centavos;
    if (filtros.precoMin != null && mensal != null && mensal < filtros.precoMin) return false;
    if (filtros.precoMax != null && mensal != null && mensal > filtros.precoMax) return false;
    const diff = p.numerico?.diff_mes_centavos;
    if (filtros.semantica === "economia" && !(diff != null && diff < 0)) return false;
    if (filtros.semantica === "aumento" && !(diff != null && diff > 0)) return false;
    return true;
  });
}

export function ordenarPropostas(propostas, criterio) {
  const copia = [...propostas];
  const num = (p) => p.numerico;
  switch (criterio) {
    case "menor_mensalidade":
      return copia.sort(
        (a, b) =>
          (num(a)?.proposta_mensal_centavos ?? Infinity) -
          (num(b)?.proposta_mensal_centavos ?? Infinity)
      );
    case "menor_aumento":
      return copia.sort((a, b) => {
        const da = num(a)?.diff_mes_centavos ?? 0;
        const db = num(b)?.diff_mes_centavos ?? 0;
        if (da >= 0 && db >= 0) return da - db;
        if (da < 0 && db < 0) return db - da;
        return da - db;
      });
    case "mais_proximo":
      return copia.sort(
        (a, b) =>
          Math.abs(num(a)?.diff_mes_centavos ?? 0) - Math.abs(num(b)?.diff_mes_centavos ?? 0)
      );
    default:
      return copia;
  }
}

export function opcoesUnicas(propostas, campo) {
  return [...new Set(propostas.map((p) => p[campo]).filter(Boolean))].sort();
}

export function ordenarSelecao(propostas, idsSelecionados) {
  const mapa = new Map(propostas.map((p) => [p.opcao_id, p]));
  return idsSelecionados.map((id) => mapa.get(id)).filter(Boolean);
}
