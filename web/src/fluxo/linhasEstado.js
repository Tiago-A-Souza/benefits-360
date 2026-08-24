/** Linhas de estado da coluna de etapas — só dados já presentes no contexto. */

function vidasIncluidas(rascunho) {
  return (rascunho?.vidas || []).filter((v) => v.incluida !== false).length;
}

function formatarReajusteBps(bps) {
  if (bps == null || Number.isNaN(Number(bps))) return null;
  const pct = Number(bps) / 100;
  const txt = Number.isInteger(pct)
    ? String(pct)
    : pct.toLocaleString("pt-BR", { maximumFractionDigits: 2 });
  return `${txt}%`;
}

function reajusteUnico(subgrupos) {
  const valores = (subgrupos || [])
    .map((sg) => sg.reajuste_bps)
    .filter((v) => v != null);
  if (!valores.length) return null;
  const primeiro = valores[0];
  if (!valores.every((v) => v === primeiro)) return null;
  return formatarReajusteBps(primeiro);
}

export function linhaEstadoPasso(chave, ctx) {
  const { conferencia, rascunho, extracoes, resumo } = ctx || {};

  if (chave === "base") {
    const partes = [];
    const n =
      resumo?.beneficiarios_incluidos ??
      (rascunho ? vidasIncluidas(rascunho) : null);
    if (n != null && (resumo || rascunho || conferencia)) {
      partes.push(`${n} ${n === 1 ? "vida" : "vidas"}`);
    }
    if (conferencia?.estatisticas && conferencia.estatisticas.linhas_com_excecao != null) {
      const exc = conferencia.estatisticas.linhas_com_excecao;
      partes.push(`${exc} ${exc === 1 ? "exceção" : "exceções"}`);
    }
    return partes.length ? partes.join(" · ") : null;
  }

  if (chave === "plano") {
    const n = rascunho?.subgrupos_atuais?.length || 0;
    if (!n) return null;
    const planoTxt = `${n} ${n === 1 ? "plano" : "planos"}`;
    const reaj = reajusteUnico(rascunho.subgrupos_atuais);
    return reaj ? `${planoTxt} · reajuste ${reaj}` : planoTxt;
  }

  if (chave === "cotacoes") {
    const pdfs = (extracoes || []).length || (rascunho?.documentos_cotacao || []).length;
    const planos = (rascunho?.opcoes_proposta || []).length;
    const partes = [];
    if (pdfs) partes.push(`${pdfs} ${pdfs === 1 ? "PDF" : "PDFs"}`);
    if (planos) partes.push(`${planos} ${planos === 1 ? "plano" : "planos"}`);
    return partes.length ? partes.join(" · ") : null;
  }

  if (chave === "selecionados") {
    const n = (rascunho?.cenarios || []).length;
    if (!n) return null;
    return `${n} ${n === 1 ? "cenário" : "cenários"}`;
  }

  if (chave === "comparativo") {
    const n = (rascunho?.opcoes_proposta || []).length;
    if (!n) return null;
    return `${n} ${n === 1 ? "proposta" : "propostas"}`;
  }

  return null;
}
