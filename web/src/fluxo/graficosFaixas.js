/** Derivação dos gráficos da etapa 1 a partir da tabela de faixas para cotação.
 *
 * Fonte única: o objeto `tabela` é o retorno de
 * `montar_tabela_faixas_cotacao` (siscor_importer/faixas_cotacao.py). Aqui não
 * há segunda contagem nem segunda regra de faixa — só releitura das mesmas
 * células que a tabela exibe.
 */

export const ROSCA_RAIO = 70;
export const ROSCA_ESPESSURA = 34;
export const ROSCA_CIRCUNFERENCIA = 2 * Math.PI * ROSCA_RAIO;

/** Rótulo curto para o eixo; a forma completa continua no texto alternativo. */
export function rotuloCurto(rotulo) {
  return String(rotulo ?? "").replace(/\s+a\s+/, "\u2013");
}

/** Percentuais inteiros que somam exatamente 100 (maior resto). */
export function percentuaisInteiros(valores) {
  const total = valores.reduce((s, v) => s + v, 0);
  if (total <= 0) return valores.map(() => 0);

  const exatos = valores.map((v) => (v * 100) / total);
  const base = exatos.map((v) => Math.floor(v));
  let resto = 100 - base.reduce((s, v) => s + v, 0);

  const ordem = exatos
    .map((v, i) => ({ i, frac: v - Math.floor(v), valor: valores[i] }))
    .filter((x) => x.valor > 0)
    .sort((a, b) => b.frac - a.frac || b.valor - a.valor || a.i - b.i);

  for (let k = 0; resto > 0 && ordem.length > 0; k += 1) {
    base[ordem[k % ordem.length].i] += 1;
    resto -= 1;
  }
  return base;
}

/** Fatias da rosca: feminino, masculino e — se houver — não informado. */
function montarRosca(linhas, chaves) {
  const contar = (campos) =>
    linhas.reduce(
      (soma, ln) => soma + campos.reduce((s, c) => s + (ln[c] || 0), 0),
      0,
    );

  const brutos = chaves.map((c) => ({ ...c, valor: contar(c.campos) }));
  const total = brutos.reduce((s, f) => s + f.valor, 0);
  const percentuais = percentuaisInteiros(brutos.map((f) => f.valor));

  let offset = 0;
  const fatias = brutos.map((f, i) => {
    const fracao = total > 0 ? f.valor / total : 0;
    const comprimento = fracao * ROSCA_CIRCUNFERENCIA;
    const fatia = {
      chave: f.chave,
      rotulo: f.rotulo,
      valor: f.valor,
      percentual: percentuais[i],
      comprimento,
      offset,
      completa: total > 0 && f.valor === total,
    };
    offset += comprimento;
    return fatia;
  });

  return {
    total,
    // Desenhadas: só as fatias com valor — 0% não vira risco nem buraco.
    fatias: fatias.filter((f) => f.valor > 0),
    // Legenda: feminino e masculino sempre (o zero de um lado é informação);
    // «Não informado» só quando existe.
    todas: fatias.filter((f) => f.chave !== "nao_informado" || f.valor > 0),
  };
}

/** Barras por faixa etária: uma por faixa da ANS, zeros inclusos. */
function montarBarras(linhas) {
  const itens = linhas.map((ln) => ({
    faixa: ln.faixa,
    rotulo: ln.rotulo,
    rotuloCurto: rotuloCurto(ln.rotulo),
    valor: ln.total || 0,
  }));
  const maior = itens.reduce((m, it) => Math.max(m, it.valor), 0);
  const total = itens.reduce((s, it) => s + it.valor, 0);
  return {
    itens: itens.map((it) => ({
      ...it,
      // Fração da barra mais alta: mantém legível a faixa pequena ao lado de
      // uma concentrada (a altura mínima visível fica no CSS).
      fracao: maior > 0 ? it.valor / maior : 0,
    })),
    maior,
    total,
  };
}

/**
 * Deriva os dois gráficos da tabela da etapa 1.
 *
 * Sem coluna SEXO na origem, ou sem vida alguma, não há gráfico — e, portanto,
 * não há botão: a etapa 1 fica como está hoje.
 */
export function derivarGraficos(tabela) {
  const linhas = tabela?.linhas;
  if (!Array.isArray(linhas) || linhas.length === 0) {
    return { disponivel: false };
  }
  if (tabela.modo_sexo === "sem_sexo") {
    return { disponivel: false };
  }

  const barras = montarBarras(linhas);
  if (barras.total === 0) {
    return { disponivel: false };
  }

  const rosca = montarRosca(linhas, [
    { chave: "feminino", rotulo: "Feminino", campos: ["tit_f", "dep_f"] },
    { chave: "masculino", rotulo: "Masculino", campos: ["tit_m", "dep_m"] },
    // Sexo ausente não é distribuído entre F e M nem descartado: vira fatia
    // própria, coerente com a coluna «Não informado» da tabela.
    { chave: "nao_informado", rotulo: "Não informado", campos: ["nao_informado"] },
  ]);

  return { disponivel: true, rosca, barras };
}

/** Alternativa textual da rosca — mesma informação, sem depender da cor. */
export function descricaoRosca(rosca) {
  if (!rosca || rosca.total === 0) return "";
  const partes = rosca.fatias.map(
    (f) => `${f.rotulo}: ${f.valor} (${f.percentual}%)`,
  );
  return `Distribuição por sexo em ${rosca.total} vidas. ${partes.join("; ")}.`;
}

/** Alternativa textual das barras — inclui faixas com zero. */
export function descricaoBarras(barras) {
  if (!barras || barras.total === 0) return "";
  const partes = barras.itens.map((it) => `${it.rotulo}: ${it.valor}`);
  return `Vidas por faixa etária, ${barras.total} no total. ${partes.join("; ")}.`;
}
