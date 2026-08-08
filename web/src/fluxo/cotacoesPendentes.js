/** Documentos de cotação PDF sem plano no comparativo e sem descarte. */

export function rotuloDocumentoExtracao(ex) {
  const operadora = ex?.documento?.operadora_detectada || "Cotação";
  const numero =
    ex?.numero_cotacao?.texto ||
    (ex?.documento?.nome_arquivo || "").replace(/\.pdf$/i, "") ||
    null;
  return numero ? `${operadora} (${numero})` : operadora;
}

export function planosNoComparativo(ex, opcoesComparativo = []) {
  return (opcoesComparativo || []).filter((o) => o.extracao_id === ex.id).length;
}

export function planosMarcados(ex) {
  return (ex.opcoes || []).filter((o) => !o.excluida && o.selecionada_para_comparativo).length;
}

export function totalPlanosAtivos(ex) {
  return (ex.opcoes || []).filter((o) => !o.excluida).length;
}

/** Texto curto para o card da lista de PDFs. */
export function resumoSelecaoDocumento(ex, opcoesComparativo = []) {
  if (ex.descartada) {
    return `Descartada — ${ex.motivo_descarte || "sem motivo"}`;
  }
  const total = totalPlanosAtivos(ex);
  const noComp = planosNoComparativo(ex, opcoesComparativo);
  const marcados = planosMarcados(ex);
  const sel = noComp > 0 ? noComp : marcados;
  if (sel === 0) return "nenhum plano selecionado";
  if (noComp > 0) return `${noComp} de ${total} selecionados`;
  return `${marcados} de ${total} marcados (ainda não no comparativo)`;
}

export function documentosPendentesRevisao(extracoes = [], opcoesComparativo = []) {
  return (extracoes || []).filter((ex) => {
    if (ex.descartada) return false;
    return planosNoComparativo(ex, opcoesComparativo) === 0 && planosMarcados(ex) === 0;
  });
}

/**
 * Mensagem de confirmação ao avançar a etapa.
 * @returns {string|null}
 */
export function avisoAvancoCotacoesPendentes(extracoes = [], opcoesComparativo = []) {
  const pendentes = documentosPendentesRevisao(extracoes, opcoesComparativo);
  if (!pendentes.length) return null;
  const lista = pendentes.map(rotuloDocumentoExtracao).join(", ");
  const n = pendentes.length;
  return (
    `${n} cotação(ões) importada(s) não têm plano no comparativo: ${lista}. ` +
    "Deseja continuar mesmo assim?"
  );
}

/** Próxima extração ainda sem resolução (plano ou descarte), excluindo a atual. */
export function proximaExtracaoPendente(extracoes = [], opcoesComparativo = [], atualId = null) {
  const pendentes = documentosPendentesRevisao(extracoes, opcoesComparativo).filter(
    (ex) => ex.id !== atualId
  );
  return pendentes[0] || null;
}
