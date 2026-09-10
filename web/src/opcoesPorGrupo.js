/** Quais cotações o dropdown da etapa 4 oferece a cada plano vigente — FASE 2. */

/**
 * A lista vem da matriz de estimativa, que o servidor já entrega restrita à
 * seleção de cada grupo. Derivar daí evita uma segunda cópia da regra no front:
 * o plano que aparece no dropdown é exatamente o que tem valor calculado ali.
 *
 * Sem matriz (falha de carga), devolve o catálogo inteiro — degradar para a
 * etapa 4 de antes é preferível a mostrar um dropdown vazio.
 */
export function opcoesDoSubgrupo(opcoes, matriz, subgrupoId) {
  const celulas = matriz?.celulas;
  if (!celulas) return opcoes || [];
  const permitidos = new Set(
    celulas.filter((c) => c.subgrupo_id === subgrupoId).map((c) => c.opcao_id)
  );
  return (opcoes || []).filter((o) => permitidos.has(o.id));
}

/**
 * A lista restrita, mais a cotação já atribuída caso ela tenha ficado de fora
 * por mudança posterior na etapa 3.
 *
 * Sem isso o dropdown mostraria o placeholder e a atribuição existente sumiria
 * da tela sem ter sido desfeita — o cenário continuaria gravado com ela. Fazer
 * o plano desaparecer da vista é a forma silenciosa do mesmo problema que estas
 * fases existem para eliminar.
 */
export function opcoesParaDropdown(opcoes, matriz, subgrupoId, opcaoAtualId) {
  const lista = opcoesDoSubgrupo(opcoes, matriz, subgrupoId);
  if (!opcaoAtualId || lista.some((o) => o.id === opcaoAtualId)) return lista;
  const atual = (opcoes || []).find((o) => o.id === opcaoAtualId);
  return atual ? [...lista, atual] : lista;
}

/**
 * Atribuição que sobrou fora da seleção do grupo, por mudança posterior na
 * etapa 3. O front avisa; quem bloqueia é o compilador (APP-GRP-001). Nada é
 * podado nem substituído aqui.
 */
export function atribuicaoForaDaSelecao(opcoes, matriz, subgrupoId, opcaoId) {
  if (!opcaoId || !matriz?.celulas) return null;
  const permitidos = opcoesDoSubgrupo(opcoes, matriz, subgrupoId).map((o) => o.id);
  if (permitidos.includes(opcaoId)) return null;
  const opcao = (opcoes || []).find((o) => o.id === opcaoId);
  return opcao?.plano_nome || opcaoId;
}
