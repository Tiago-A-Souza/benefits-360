/** Heurísticas de conclusão por etapa do fluxo operacional. */

import { chavePassoVisivel, exigeCorrespondenciaManual, passosVisiveis } from "./passos";

function idsOpcoes(rascunho) {
  return new Set((rascunho?.opcoes_proposta || []).map((op) => op.id));
}

function mapaOpcaoSubgrupo(rascunho) {
  const mapa = new Map();
  for (const c of rascunho?.cenarios || []) {
    for (const a of c.atribuicoes || []) {
      if (a.opcao_plano_id) mapa.set(a.opcao_plano_id, a.alvo_id);
    }
  }
  return mapa;
}

export function cenariosSincronizados(rascunho) {
  const ops = rascunho?.opcoes_proposta || [];
  if (!ops.length) return false;
  const sgs = rascunho?.subgrupos_atuais || [];
  if (!sgs.length) return false;

  const mapa = mapaOpcaoSubgrupo(rascunho);
  const cenarios = rascunho?.cenarios || [];

  if (sgs.length === 1) {
    const sgId = sgs[0].id;
    if (cenarios.length !== ops.length) return false;
    return ops.every((op) => mapa.get(op.id) === sgId);
  }

  return ops.every((op) => {
    const sgId = mapa.get(op.id);
    return sgId && sgs.some((sg) => sg.id === sgId);
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
      return { concluida: true, pendencia: null };
    }
    case "selecionados": {
      const ops = rascunho?.opcoes_proposta?.length || 0;
      if (!ops) return { concluida: false, pendencia: "Adicione planos ao comparativo" };
      if (!cenariosSincronizados(rascunho)) {
        return { concluida: false, pendencia: "Defina a comparação com cada plano atual" };
      }
      return { concluida: true, pendencia: null };
    }
    case "comparativo": {
      if (!cenariosSincronizados(rascunho)) {
        return {
          concluida: false,
          pendencia: "Defina a correspondência de todas as propostas",
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
