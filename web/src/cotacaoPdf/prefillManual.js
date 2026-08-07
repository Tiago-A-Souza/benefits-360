/** Pré-preenche cotação manual a partir de extração PDF sem opções. */

/**
 * @param {object|null} detalhe ExtracaoCotacaoCandidata
 * @param {object|null} doc DocumentoCotacaoPDF
 */
export function buildPrefillManualFromExtracao(detalhe, doc) {
  const operadora =
    doc?.operadora_detectada ||
    detalhe?.opcoes?.[0]?.operadora?.texto ||
    "";

  const numeroCotacao = detalhe?.numero_cotacao?.texto || null;
  const validade = detalhe?.validade_oficial?.data || null;
  const templateId = doc?.template_id || null;

  const observacoes = [
    templateId ? `Template: ${templateId}` : null,
    numeroCotacao ? `Cotação nº ${numeroCotacao}` : null,
    detalhe?.estado ? `Estado da extração: ${detalhe.estado}` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  return {
    operadora,
    plano_nome: "",
    documento_cotacao_id: doc?.id || null,
    validade_oficial: validade,
    observacoes: observacoes || null,
    extracao_id: detalhe?.id || null,
  };
}
