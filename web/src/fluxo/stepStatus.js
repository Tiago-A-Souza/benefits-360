/** Heurísticas de conclusão por etapa do fluxo operacional. */

import { documentosPendentesRevisao } from "./cotacoesPendentes";
import { chavePassoVisivel, exigeCorrespondenciaManual, passosVisiveis } from "./passos";

function subgruposComVidas(rascunho) {
  const comVidas = new Set();
  for (const v of rascunho?.vidas || []) {
    if (v.incluida && v.subgrupo_atual_id) comVidas.add(v.subgrupo_atual_id);
  }
  return (rascunho?.subgrupos_atuais || []).filter((sg) => comVidas.has(sg.id));
}

function vidasIncluidasIds(rascunho) {
  return (rascunho?.vidas || []).filter((v) => v.incluida).map((v) => v.id);
}

export function cenariosSincronizados(rascunho) {
  const ops = rascunho?.opcoes_proposta || [];
  if (!ops.length) return false;

  const cenarios = rascunho?.cenarios || [];
  const opIds = new Set(ops.map((op) => op.id));

  if (rascunho?.formato === "novo") {
    const vidasObrigatorias = new Set(vidasIncluidasIds(rascunho));
    if (!vidasObrigatorias.size) return false;
    if (cenarios.length !== ops.length) return false;
    return cenarios.every((cenario) => {
      const atribPorVida = new Map();
      for (const atr of cenario.atribuicoes || []) {
        if (atr.alvo_tipo !== "vida") return false;
        if (!atr.opcao_plano_id || !opIds.has(atr.opcao_plano_id)) return false;
        atribPorVida.set(atr.alvo_id, atr.opcao_plano_id);
      }
      if (atribPorVida.size !== vidasObrigatorias.size) return false;
      for (const vidaId of vidasObrigatorias) {
        if (!atribPorVida.has(vidaId)) return false;
      }
      return true;
    });
  }

  const sgs = subgruposComVidas(rascunho);
  if (!sgs.length) return false;
  const sgObrigatorios = new Set(sgs.map((sg) => sg.id));

  if ((rascunho?.subgrupos_atuais?.length || 0) === 1) {
    const sgId = sgs[0].id;
    if (cenarios.length !== ops.length) return false;
    return cenarios.every(
      (c) =>
        c.atribuicoes?.length === 1 &&
        c.atribuicoes[0].alvo_tipo === "subgrupo" &&
        c.atribuicoes[0].alvo_id === sgId &&
        opIds.has(c.atribuicoes[0].opcao_plano_id)
    );
  }

  if (cenarios.length !== ops.length) return false;

  return cenarios.every((cenario) => {
    const atribPorSg = new Map();
    for (const atr of cenario.atribuicoes || []) {
      if (atr.alvo_tipo !== "subgrupo") return false;
      if (!atr.opcao_plano_id || !opIds.has(atr.opcao_plano_id)) return false;
      atribPorSg.set(atr.alvo_id, atr.opcao_plano_id);
    }
    if (atribPorSg.size !== sgObrigatorios.size) return false;
    for (const sgId of sgObrigatorios) {
      if (!atribPorSg.has(sgId)) return false;
    }
    return true;
  });
}

export function comparativoConfirmado(rascunho) {
  const conf = rascunho?.confirmacao_comparativo;
  return Boolean(
    conf?.hash_comparativo && conf?.ordem?.length && conf?.confirmado_em && conf?.rascunho_fingerprint
  );
}

export function statusEtapaPorChave(chave, ctx) {
  const { conferencia, rascunho, extracoes, pendencias } = ctx;

  switch (chave) {
    case "base": {
      if (!conferencia?.linhas?.length) {
        return { concluida: false, pendencia: "Importe a planilha SISCOR" };
      }
      const exc = conferencia.estatisticas?.linhas_com_excecao || 0;
      const conf = conferencia.estatisticas?.confirmadas || 0;
      if (exc > 0) return { concluida: false, pendencia: `${exc} exceção(ões) na base` };
      if (conf === 0) return { concluida: false, pendencia: "Confirme os beneficiários" };
      return { concluida: true, pendencia: null };
    }
    case "plano": {
      if (rascunho?.formato === "novo") {
        if (!rascunho.escolhas?.data_referencia_idade) {
          return { concluida: false, pendencia: "Informe a data de referência das idades" };
        }
        const p2novo = (pendencias || []).filter((p) => p.tipo === "bloqueio" && p.etapa === 2);
        if (p2novo.length) return { concluida: false, pendencia: p2novo[0].titulo };
        return { concluida: true, pendencia: null };
      }
      if (!rascunho?.subgrupos_atuais?.length) {
        return { concluida: false, pendencia: "Configure o plano atual" };
      }
      if (
        !rascunho.escolhas?.baseline_escolhido?.confirmado ||
        !rascunho.escolhas?.precedencia_atual_vida?.confirmado
      ) {
        return { concluida: false, pendencia: "Confirme as informações do plano" };
      }
      const p2 = (pendencias || []).filter((p) => p.tipo === "bloqueio" && p.etapa === 2);
      if (p2.length) return { concluida: false, pendencia: p2[0].titulo };
      return { concluida: true, pendencia: null };
    }
    case "cotacoes": {
      const pdfs = extracoes?.length || 0;
      const manuais = rascunho?.opcoes_proposta?.filter((o) => !o.extracao_id)?.length || 0;
      const importadas = rascunho?.opcoes_proposta?.filter((o) => o.extracao_id)?.length || 0;
      const docs = rascunho?.documentos_cotacao?.length || 0;
      const temFonte = pdfs > 0 || manuais > 0 || importadas > 0 || docs > 0;
      if (!temFonte) {
        return { concluida: false, pendencia: "Adicione ao menos uma cotação" };
      }
      const ops = rascunho?.opcoes_proposta?.length || 0;
      if (!ops) {
        return {
          concluida: false,
          pendencia: "Adicione planos ao comparativo (botão no fim da revisão)",
        };
      }
      if (!exigeCorrespondenciaManual(rascunho) && !cenariosSincronizados(rascunho)) {
        return {
          concluida: false,
          pendencia: "Aguarde a sincronização das propostas com o plano atual",
        };
      }
      const pendentesDocs = documentosPendentesRevisao(
        extracoes || [],
        rascunho?.opcoes_proposta || []
      );
      const aviso =
        pendentesDocs.length > 0
          ? `${pendentesDocs.length} cotação(ões) sem plano no comparativo (pode avançar com aviso)`
          : null;
      return { concluida: true, pendencia: null, aviso };
    }
    case "selecionados": {
      const ops = rascunho?.opcoes_proposta?.length || 0;
      if (!ops) return { concluida: false, pendencia: "Adicione planos ao comparativo" };
      if (!cenariosSincronizados(rascunho)) {
        return {
          concluida: false,
          pendencia:
            rascunho?.formato === "novo"
              ? "Confirme a atribuição das propostas às vidas"
              : "Confirme a matriz de propostas por subgrupo",
        };
      }
      return { concluida: true, pendencia: null };
    }
    case "comparativo": {
      if (!cenariosSincronizados(rascunho)) {
        return {
          concluida: false,
          pendencia:
            rascunho?.formato === "novo"
              ? "Aguarde a sincronização das propostas com as vidas"
              : "Confirme a matriz de propostas por subgrupo",
        };
      }
      if (!comparativoConfirmado(rascunho)) {
        return {
          concluida: false,
          pendencia: "Calcule, selecione propostas e confirme o comparativo",
        };
      }
      return { concluida: true, pendencia: null };
    }
    case "apresentacao":
      return { concluida: false, pendencia: "Gere e revise a apresentação" };
    default:
      return { concluida: false, pendencia: null };
  }
}

/** @param {number} indicePasso — 1-based na lista visível */
export function statusEtapa(indicePasso, ctx) {
  const chave = chavePassoVisivel(ctx.rascunho, indicePasso);
  if (!chave) return { concluida: false, pendencia: null };
  return statusEtapaPorChave(chave, ctx);
}

export function proximaEtapaDisponivel(passoAtual, ctx) {
  return statusEtapa(passoAtual, ctx).concluida;
}

export { passosVisiveis, exigeCorrespondenciaManual };
