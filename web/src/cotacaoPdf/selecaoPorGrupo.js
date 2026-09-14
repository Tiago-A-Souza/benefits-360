/** Lógica da seleção de planos por grupo — FASE 1. Sem DOM, testável direto. */

/** A tela nova só existe com mais de um plano vigente. Com um, a etapa 3 é a de hoje. */
export function exibeSelecaoPorGrupo(selecao) {
  return (selecao?.grupos?.length || 0) > 1;
}

/**
 * Abas e atribuição por grupo: a prop do pai OU o resumo SISCOR (o mesmo
 * que já alimentava o dropdown «para simular»).
 * Seguro novo não usa atribuição por subgrupo — permanece desligado.
 */
export function modoSelecaoPorGrupo(exigeProp, nPlanosSiscor, formatoEstudo) {
  if (formatoEstudo === "novo") return false;
  return Boolean(exigeProp) || (nPlanosSiscor || 0) > 1;
}

/**
 * Depois das cotações, a seleção por grupo é a última tela da etapa 3.
 * Se o operador ainda estiver dentro de um PDF, o avanço revela essa tela
 * em vez de pular para a etapa 4. Já na lista, o clique segue — sem exigir
 * seleção própria; grupo sem entrada herda o catálogo.
 */
export function avancoDeveRevelarSelecaoPorGrupo(exigeSelecao, fase) {
  return Boolean(exigeSelecao) && fase !== "lista";
}

/** Último PDF aplicado, dois grupos: volta à lista com as abas e o catálogo. */
export function aposUltimoPdfDeveVoltarLista(exigeSelecao, temProximoPendente) {
  return Boolean(exigeSelecao) && !temProximoPendente;
}

/**
 * O que a seção mostra. GET falho com dois grupos vira erro visível;
 * um plano vigente continua sem tela, mesmo se o GET falhar.
 */
export function visaoSelecaoPorGrupo(selecao, erro, exigeSelecao = false) {
  if (exibeSelecaoPorGrupo(selecao)) return "tela";
  if (erro && exigeSelecao) return "erro";
  return null;
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

/** Próximo grupo desta cotação que ainda não recebeu o OK. */
export function proximoGrupoParaAtribuir(grupoIds, atualId, jaAplicados) {
  const ids = grupoIds || [];
  if (ids.length < 2) return null;
  const feitos = new Set(jaAplicados || []);
  if (atualId) feitos.add(atualId);
  const idx = Math.max(0, ids.indexOf(atualId));
  for (let i = 1; i <= ids.length; i += 1) {
    const cand = ids[(idx + i) % ids.length];
    if (!feitos.has(cand)) return cand;
  }
  return null;
}

/** Com dois grupos, a escolha fica nas abas; um único confirmar grava tudo. */
export function pulaRevisaoPorGrupo(selecaoPorGrupoAtiva) {
  return Boolean(selecaoPorGrupoAtiva);
}

export function marcasAposTrocarGrupo(marcas, grupoDe, idsAtuais) {
  return { ...(marcas || {}), [grupoDe]: [...(idsAtuais || [])] };
}

/** Confirma primeiro os grupos com marca — o vazio do outro não bloqueia a cotação. */
export function ordemGruposParaConfirmar(idsGrupos, marcas) {
  const ids = idsGrupos || [];
  const com = ids.filter((sg) => (marcas?.[sg] || []).length > 0);
  const sem = ids.filter((sg) => !(marcas?.[sg] || []).length);
  return [...com, ...sem];
}

export function uniaoMarcas(marcas) {
  const visto = new Set();
  const ids = [];
  for (const lista of Object.values(marcas || {})) {
    for (const id of lista || []) {
      if (visto.has(id)) continue;
      visto.add(id);
      ids.push(id);
    }
  }
  return ids;
}

/** Última tela da etapa 3: só o que foi atribuído àquele grupo, nunca o catálogo inteiro. */
export function planosAtribuidosDoGrupo(grupo) {
  if (!grupo?.selecao_propria) return [];
  return (grupo.planos || []).filter((p) => p.escolhido);
}

/**
 * Status na grade da cotação. Com dois grupos, «Será removido» só vale se o
 * plano sair da união — estar desmarcado nesta aba não tira o do outro grupo.
 */
export function estadoExibicaoOpcao(op, opcoesComparativo, idsUniao = null) {
  const adicionado = (opcoesComparativo || []).some((o) => o.extracao_opcao_id === op.id);
  const naUniao = idsUniao == null ? Boolean(op.selecionada_para_comparativo) : idsUniao.includes(op.id);
  const naAba = Boolean(op.selecionada_para_comparativo);
  if (adicionado && naUniao && naAba) {
    return { codigo: "adicionado", rotulo: "No comparativo" };
  }
  if (adicionado && naUniao && !naAba) {
    return { codigo: "adicionado", rotulo: "Outro grupo" };
  }
  if (adicionado && !naUniao) {
    return { codigo: "remover", rotulo: "Será removido" };
  }
  if (naAba) {
    return { codigo: "selecionado", rotulo: "Selecionado" };
  }
  return { codigo: "disponivel", rotulo: "Disponível" };
}

/**
 * Marcas desta cotação já gravadas por grupo. Sem entrada própria = nenhuma marca
 * (não herda o catálogo na grade da cotação).
 */
export function marcasDoPdfPorGrupo(selecao, opcoesProposta, extracaoId) {
  const marcas = {};
  for (const g of selecao?.grupos || []) {
    if (!g.selecao_propria) {
      marcas[g.subgrupo_id] = [];
      continue;
    }
    const escolhidos = new Set(
      (g.planos || []).filter((p) => p.escolhido).map((p) => p.opcao_id)
    );
    marcas[g.subgrupo_id] = (opcoesProposta || [])
      .filter((o) => o.extracao_id === extracaoId && escolhidos.has(o.id))
      .map((o) => o.extracao_opcao_id)
      .filter(Boolean);
  }
  return marcas;
}

export function fraseEscolhaGrupo(nome) {
  const n = String(nome || "").trim();
  if (!n) return "";
  const base = `Você está escolhendo os planos que vão competir com o ${n}`;
  return /[.!?…]$/.test(n) ? base : `${base}.`;
}

export function textoResumoGrupo(grupo) {
  if (!grupo) return "";
  const vidas = plural(grupo.quantidade_beneficiarios || 0, "vida", "vidas");
  return `Planos atribuídos ao ${grupo.plano_nome} — valores para as ${vidas} deste grupo.`;
}
