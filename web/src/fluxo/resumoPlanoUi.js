import { centavosParaReaisExibicao } from "../money";

export function formatarPctHint(parte, total) {
  if (!total) return null;
  const pct = (parte / total) * 100;
  return `${pct.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% da base`;
}

export function textoReajusteContrato(resumo) {
  if (!resumo?.planos?.length) return null;
  const exibicoes = resumo.planos
    .map((p) => p.reajuste_percentual_exibicao)
    .filter(Boolean);
  if (!exibicoes.length) return null;
  const primeiro = exibicoes[0];
  if (!exibicoes.every((e) => e === primeiro)) return null;
  const num = primeiro.replace(/%$/, "").replace(/,00$/, "");
  return `contrato reajustado em ${num}%`;
}

function contagemPorSubgrupo(linhas) {
  const mapa = {};
  for (const linha of linhas) {
    if (linha.excluida) continue;
    const key = linha.subgrupo_sugerido_id || linha.plano || "_";
    if (!mapa[key]) {
      mapa[key] = { titulares: 0, dependentes: 0, vidas: 0, vigenteCentavos: 0 };
    }
    const c = mapa[key];
    c.vidas += 1;
    if (linha.parentesco === "titular") c.titulares += 1;
    else if (linha.parentesco) c.dependentes += 1;
    if (linha.valor_centavos != null) c.vigenteCentavos += linha.valor_centavos;
  }
  return mapa;
}

export function montarTabelaPlanosBase(conferencia, resumoPlano) {
  const linhas = conferencia?.linhas || [];
  const contagem = contagemPorSubgrupo(linhas);

  if (resumoPlano?.planos?.length) {
    return resumoPlano.planos.map((p) => {
      const c = contagem[p.subgrupo_id] || {};
      return {
        id: p.subgrupo_id,
        nome: p.plano_nome,
        titulares: c.titulares ?? null,
        dependentes: c.dependentes ?? null,
        vidas: p.quantidade_beneficiarios,
        vigente: p.valor_mensal_vigente_reais,
        reajustado: p.valor_mensal_reajustado_reais,
      };
    });
  }

  const sugeridos = conferencia?.subgrupos_sugeridos || [];
  if (sugeridos.length) {
    return sugeridos.map((sg) => {
      const c = contagem[sg.id] || contagem[sg.plano_nome] || {};
      return {
        id: sg.id,
        nome: sg.plano_nome,
        titulares: c.titulares ?? 0,
        dependentes: c.dependentes ?? 0,
        vidas: sg.quantidade_linhas || c.vidas || 0,
        vigente: c.vigenteCentavos ? centavosParaReaisExibicao(c.vigenteCentavos) : null,
        reajustado: null,
      };
    });
  }

  return [];
}
