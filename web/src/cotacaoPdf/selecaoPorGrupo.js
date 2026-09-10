/** Lógica da seleção de planos por grupo — FASE 1. Sem DOM, testável direto. */

/** A tela nova só existe com mais de um plano vigente. Com um, a etapa 3 é a de hoje. */
export function exibeSelecaoPorGrupo(selecao) {
  return (selecao?.grupos?.length || 0) > 1;
}

function plural(n, singular, formaPlural) {
  return `${n} ${n === 1 ? singular : formaPlural}`;
}

/** Subtítulo da aba: vidas e valor de referência. Sem papel — não existe no modelo. */
export function subtituloGrupo(grupo) {
  const partes = [plural(grupo?.quantidade_beneficiarios || 0, "vida", "vidas")];
  if (grupo?.referencia_reais) {
    const rotulo = grupo.referencia_rotulo === "reajustada" ? "reajustado" : "vigente";
    partes.push(`${grupo.referencia_reais} ${rotulo}`);
  }
  return partes.join(" · ");
}

/** Selo da aba. Grupo sem entrada própria herda o catálogo, e isso precisa ficar dito. */
export function seloGrupo(grupo) {
  const n = grupo?.escolhidos || 0;
  if (!grupo?.selecao_propria) {
    return { texto: `${plural(n, "plano", "planos")} — todos`, herdado: true };
  }
  if (n === 0) {
    return { texto: "nenhum plano escolhido", herdado: false, vazio: true };
  }
  return { texto: `${plural(n, "plano escolhido", "planos escolhidos")}`, herdado: false };
}

/** Faixa de contexto: para qual grupo a escolha está sendo feita. */
export function textoContexto(grupo) {
  if (!grupo) return "";
  const vidas = plural(grupo.quantidade_beneficiarios || 0, "vida", "vidas");
  // Travessão, não ponto: nome de plano costuma terminar em "Apto." e ficaria "Apto..".
  return `Você está escolhendo os planos que vão competir com o ${grupo.plano_nome} — os valores abaixo são calculados para as ${vidas} deste grupo.`;
}

/** Marca ou desmarca um plano na seleção do grupo ativo, preservando a ordem. */
export function alternarPlano(grupo, opcaoId) {
  const atuais = (grupo?.planos || []).filter((p) => p.escolhido).map((p) => p.opcao_id);
  if (atuais.includes(opcaoId)) {
    return atuais.filter((id) => id !== opcaoId);
  }
  return (grupo?.planos || [])
    .map((p) => p.opcao_id)
    .filter((id) => atuais.includes(id) || id === opcaoId);
}

/** Aviso quando a escolha deixaria o grupo sem nenhum plano para comparar. */
export function avisoSelecaoVazia(opcaoIds) {
  if (opcaoIds.length > 0) return null;
  return "Este grupo ficaria sem nenhum plano para comparar. A etapa 4 não terá o que atribuir a ele.";
}
