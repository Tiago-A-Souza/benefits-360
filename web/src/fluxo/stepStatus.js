/** Heurísticas de conclusão por etapa do fluxo operacional. */

export function statusEtapa(passo, ctx) {
  const { conferencia, rascunho, extracoes, pendencias } = ctx;
  switch (passo) {
    case 1: {
      if (!conferencia?.linhas?.length) {
        return { concluida: false, pendencia: "Importe a planilha SISCOR" };
      }
      const exc = conferencia.estatisticas?.linhas_com_excecao || 0;
      const conf = conferencia.estatisticas?.confirmadas || 0;
      if (exc > 0) return { concluida: false, pendencia: `${exc} exceção(ões) na base` };
      if (conf === 0) return { concluida: false, pendencia: "Confirme os beneficiários" };
      return { concluida: true, pendencia: null };
    }
    case 2: {
      if (!rascunho?.subgrupos_atuais?.length) {
        return { concluida: false, pendencia: "Configure o plano atual" };
      }
      if (!rascunho.escolhas?.baseline_escolhido?.confirmado ||
          !rascunho.escolhas?.precedencia_atual_vida?.confirmado) {
        return { concluida: false, pendencia: "Confirme as informações do plano" };
      }
      const p2 = (pendencias || []).filter(
        (p) => p.tipo === "bloqueio" && p.etapa === 2
      );
      if (p2.length) return { concluida: false, pendencia: p2[0].titulo };
      return { concluida: true, pendencia: null };
    }
    case 3: {
      const pdfs = extracoes?.length || 0;
      const manuais = rascunho?.opcoes_proposta?.filter((o) => !o.extracao_id)?.length || 0;
      if (!pdfs && !manuais) {
        return { concluida: false, pendencia: "Adicione ao menos uma cotação" };
      }
      return { concluida: true, pendencia: null };
    }
    case 4: {
      const ops = rascunho?.opcoes_proposta?.length || 0;
      if (!ops) return { concluida: false, pendencia: "Adicione planos ao comparativo" };
      const sgs = rascunho?.subgrupos_atuais?.length || 0;
      if (sgs <= 1) return { concluida: true, pendencia: null };
      const cenarios = rascunho?.cenarios || [];
      const mapeadas = new Set();
      for (const c of cenarios) {
        for (const a of c.atribuicoes) {
          if (a.opcao_plano_id) mapeadas.add(a.opcao_plano_id);
        }
      }
      if (rascunho.opcoes_proposta.some((op) => !mapeadas.has(op.id))) {
        return { concluida: false, pendencia: "Defina a comparação com cada plano atual" };
      }
      return { concluida: true, pendencia: null };
    }
    case 5:
      return { concluida: false, pendencia: "Execute o comparativo financeiro" };
    case 6:
      return { concluida: false, pendencia: "Gere e revise a apresentação" };
    default:
      return { concluida: false, pendencia: null };
  }
}

export function proximaEtapaDisponivel(passoAtual, ctx) {
  return statusEtapa(passoAtual, ctx).concluida;
}
