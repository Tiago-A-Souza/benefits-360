import { centavosParaReaisExibicao } from "../money";

export const ROTULOS_FAIXA = [
  "0 a 18",
  "19 a 23",
  "24 a 28",
  "29 a 33",
  "34 a 38",
  "39 a 43",
  "44 a 48",
  "49 a 53",
  "54 a 58",
  "59+",
];

const REGIME_LABELS = {
  sem: "Sem coparticipação",
  parcial: "Coparticipação parcial (terapias)",
  percentual: "Coparticipação percentual",
};

const ESTADO_LABELS = {
  extraido: "Extraído",
  nao_reconhecido: "Não reconhecido",
  ocr_pendente: "OCR pendente",
  ocr_parcial: "OCR parcial",
  erro: "Erro",
};

export function rotuloEstado(estado) {
  return ESTADO_LABELS[estado] || estado;
}

export function formatarDataUpload(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

export function nomePlanoExibicao(op) {
  return (op.plano_nome?.texto || "Plano sem nome").trim();
}

export function inferirAcomodacao(op) {
  if (op.acomodacao?.texto) return op.acomodacao.texto;
  const n = (op.plano_nome?.texto || "").toUpperCase();
  if (/\bAPARTAMENTO\b/.test(n) || /\sQ\b/.test(n) || n.endsWith(" Q")) return "Apartamento";
  if (/\bENFERMARIA\b/.test(n) || /\sE\b/.test(n) || n.endsWith(" E")) return "Enfermaria";
  return "—";
}

/** Rótulo curto na grade; o nome completo vai no title. */
export function abreviarAcomodacao(texto) {
  if (!texto || texto === "—") return texto;
  const t = String(texto).trim().toLowerCase();
  if (t === "apartamento" || t.startsWith("apart")) return "Apt.";
  if (t === "enfermaria" || t.startsWith("enferm")) return "Enf.";
  return texto;
}

/** Coluna Copart. some só quando a seção já nomeia o regime. */
export function ocultaColunaCopart(tituloGrupo) {
  return Boolean(tituloGrupo);
}

export function inferirRegiao(op) {
  const n = (op.plano_nome?.texto || "").toUpperCase();
  if (n.includes("RIO")) return "Rio";
  if (n.includes("BRASIL")) return "Brasil";
  if (n.includes("NACIONAL")) return "Nacional";
  if (n.includes("SP ")) return "SP";
  return "—";
}

export function rotuloRegime(op) {
  const regime = op.regime_copart?.texto;
  const pct = op.copart_percentual?.inteiro;
  if (regime === "a_confirmar") return "A confirmar";
  if (regime === "sem") return REGIME_LABELS.sem;
  if (pct != null) return `Coparticipação ${pct}%`;
  return REGIME_LABELS[regime] || regime || "—";
}

export function grupoCopart(op) {
  const regime = op.regime_copart?.texto;
  const pct = op.copart_percentual?.inteiro;
  if (regime === "a_confirmar") return "A confirmar";
  if (regime === "sem") return "Sem coparticipação";
  if (pct != null) return `Coparticipação ${pct}%`;
  if (regime === "percentual") return "Coparticipação percentual";
  if (regime === "parcial") return "Coparticipação parcial (terapias)";
  return "Outros regimes";
}

export function situacaoOpcao(op) {
  if (op.excluida) return { codigo: "excluida", rotulo: "Excluída", motivos: [] };
  const faixasOk = op.tabela?.filter((fx) => fx.valor?.centavos != null).length || 0;
  if (faixasOk === 0) {
    return { codigo: "incompleto", rotulo: "Incompleto", motivos: ["Faixas incompletas"] };
  }
  const motivos = [];
  if (faixasOk < 10) {
    motivos.push("Faixas incompletas");
  }
  if (op.reconciliacao?.status === "divergente") {
    motivos.push("Reconciliação com divergências");
  }
  if (motivos.length) {
    return {
      codigo: "revisao",
      rotulo: motivos[0],
      motivos,
      bloqueiaConfirmacao: motivos.some(
        (m) => m === "Faixas incompletas" || m === "Reconciliação com divergências"
      ),
    };
  }
  if (faixasOk >= 10) {
    return { codigo: "pronto", rotulo: "Pronto", motivos: [] };
  }
  return { codigo: "incompleto", rotulo: "Incompleto", motivos: ["Faixas incompletas"] };
}

/** Motivos acionáveis para exibição — orienta seleção consciente do plano. */
export function resumirMotivosBloqueio(motivos = []) {
  const limpos = motivos.filter(
    (m) => m && !/confirme após revisar/i.test(m) && !/confirme ao menos/i.test(m)
  );
  if (limpos.length > 0) return limpos;
  if (motivos.some((m) => /divergência/i.test(m))) {
    return ["Divergência financeira — use Corrigir na tabela ou escolha outro plano."];
  }
  if (motivos.some((m) => /confirme/i.test(m))) {
    return ["Selecione este plano para confirmar os valores extraídos."];
  }
  return ["Revise os dados do plano ou escolha outra opção na lista."];
}

function listaPlanos(planos = []) {
  return planos.map((p) => `\u2022 ${p}`).join("\n");
}

function plural(n, singular, formaPlural) {
  return `${n} ${n === 1 ? singular : formaPlural}`;
}

/** Texto do gate: o que sai e o que isso desfaz na etapa 4, antes de aplicar. */
export function textoConfirmacaoRemocao(impacto) {
  const planos = impacto?.planos_removidos || [];
  const desfeitas = impacto?.atribuicoes_desfeitas || [];
  const incompletos = impacto?.cenarios_incompletos || [];
  if (!planos.length) return "";

  const partes = [
    `Esta aplicação remove ${plural(planos.length, "plano", "planos")} do comparativo:`,
    listaPlanos(planos),
  ];

  const porCenario = new Map();
  desfeitas.forEach((a) => {
    if (!porCenario.has(a.cenario_rotulo)) porCenario.set(a.cenario_rotulo, []);
    porCenario.get(a.cenario_rotulo).push(`\u2022 ${a.alvo_rotulo} \u2192 ${a.plano}`);
  });
  porCenario.forEach((linhas, cenario) => {
    partes.push(
      "",
      `Isso desfaz ${plural(linhas.length, "atribuição", "atribuições")} em «${cenario}»:`,
      linhas.join("\n")
    );
  });

  incompletos.forEach((c) => {
    partes.push(
      "",
      c.ficou_vazio
        ? `O cenário «${c.cenario_rotulo}» fica sem nenhum plano atribuído e terá de ser remontado na etapa 4.`
        : `O cenário «${c.cenario_rotulo}» fica incompleto: ${c.alvos_sem_atribuicao.join(", ")} ${
            c.alvos_sem_atribuicao.length === 1 ? "fica" : "ficam"
          } sem plano atribuído e a etapa 4 terá de ser remontada.`
    );
  });

  partes.push("", "Continuar?");
  return partes.join("\n");
}

/** Relato persistente do que saiu — não é diálogo, fica na tela depois de aplicar. */
export function textoRelatoRemocao(impacto) {
  const planos = impacto?.planos_removidos || [];
  if (!planos.length) return "";
  const desfeitas = impacto?.atribuicoes_desfeitas || [];
  const base = `${plural(planos.length, "plano", "planos")} ${
    planos.length === 1 ? "saiu" : "saíram"
  } do comparativo: ${planos.join(", ")}.`;
  if (!desfeitas.length) return base;
  const cenarios = [...new Set(desfeitas.map((a) => a.cenario_rotulo))];
  return `${base} ${plural(desfeitas.length, "atribuição", "atribuições")} ${
    desfeitas.length === 1 ? "foi desfeita" : "foram desfeitas"
  } em ${cenarios.map((c) => `«${c}»`).join(", ")}.`;
}

export function contextoSiscorSimulacao(resumoSiscor, subgrupoSelecionado) {
  const planos = resumoSiscor?.planos || [];
  return {
    totalGrupos: planos.length,
    grupoSelecionado: Boolean(subgrupoSelecionado),
    exigeEscolha: planos.length > 1 && !subgrupoSelecionado,
  };
}

export function formatarEstimativaSiscor(op, quantidades, ctx, totalNormalizadoCentavos = null) {
  if (ctx?.exigeEscolha) {
    return {
      texto: "Estimativa indisponível até selecionar o grupo",
      indisponivel: true,
      destacarGrupo: true,
    };
  }
  const temPop = quantidades && Object.values(quantidades).some((q) => q > 0);
  if (!temPop) {
    return { texto: "—", indisponivel: true, destacarGrupo: false };
  }
  const est =
    totalNormalizadoCentavos != null
      ? totalNormalizadoCentavos
      : calcularEstimadoCentavos(op, quantidades);
  if (est == null || est === 0) {
    return { texto: "—", indisponivel: true, destacarGrupo: false };
  }
  return { texto: centavosParaReaisExibicao(est), indisponivel: false, destacarGrupo: false };
}

export function rotuloReconciliacao(op) {
  const rec = op.reconciliacao;
  if (!rec) return "Reconciliação ainda não realizada — faltam população ou total de referência.";
  if (rec.status === "divergente") return "Reconciliação com divergências";
  if (rec.mensagem) return rec.mensagem;
  return "Reconciliação ainda não realizada — faltam população ou total de referência.";
}

export function formatarDiferencaReferencia(estimadoCentavos, referenciaCentavos) {
  if (estimadoCentavos == null || referenciaCentavos == null || referenciaCentavos === 0) {
    return {
      indisponivel: true,
      diffCentavos: null,
      textoDiff: "—",
      textoPct: "—",
      semantica: null,
      rotuloSemantica: null,
    };
  }
  const diff = estimadoCentavos - referenciaCentavos;
  const pct = Math.round((diff * 10000) / referenciaCentavos) / 100;
  const semantica = diff < 0 ? "economia" : diff > 0 ? "acrescimo" : "empate";
  const rotuloSemantica =
    semantica === "economia" ? "Economia estimada" : semantica === "acrescimo" ? "Acréscimo estimado" : "Sem diferença";
  const sinal = diff > 0 ? "+" : diff < 0 ? "-" : "";
  const textoDiff =
    diff === 0 ? "R$ 0,00" : `${sinal}${centavosParaReaisExibicao(Math.abs(diff))}`;
  return {
    indisponivel: false,
    diffCentavos: diff,
    textoDiff,
    textoPct: `${sinal}${pct.toFixed(2).replace(".", ",")}%`,
    semantica,
    rotuloSemantica,
  };
}

export function mapaQuantidadesFaixa(planoSiscor) {
  const map = {};
  for (const fx of planoSiscor?.faixas || []) {
    map[fx.faixa] = fx.quantidade_vidas || 0;
  }
  return map;
}

export function calcularEstimadoCentavos(op, quantidadesPorFaixa) {
  if (!op.tabela?.length || !quantidadesPorFaixa) return null;
  let total = 0;
  let usou = false;
  for (const fx of op.tabela) {
    const qtd = quantidadesPorFaixa[fx.faixa] ?? 0;
    if (qtd <= 0 || fx.valor?.centavos == null) continue;
    total += fx.valor.centavos * qtd;
    usou = true;
  }
  return usou ? total : null;
}

export function exigeSelecaoConsciente(detalhe) {
  if (!detalhe) return true;
  const ativas = detalhe.opcoes?.filter((o) => !o.excluida).length || 0;
  return detalhe.documento?.template_id?.startsWith("porto-") || ativas > 3;
}

export function traduzirAlerta(alerta) {
  if (
    (alerta.codigo === "PDF-PORTO-006" || alerta.codigo === "PDF-SUL-007" || alerta.codigo === "PDF-SUL-001")
    && alerta.mensagem
  ) {
    return alerta.mensagem;
  }
  const mapa = {
    "PDF-PORTO-001": "O plano destacado no resumo financeiro não foi associado automaticamente a uma linha da tabela.",
    "PDF-PORTO-004": "Não localizamos a tabela geral de prêmios neste PDF.",
    "PDF-PORTO-005": "Há planos com códigos muito parecidos — confira o nome antes de selecionar.",
    "PDF-PORTO-006": "Alguns planos da tabela tarifária não puderam ser extraídos — a lista pode estar incompleta.",
    "PDF-SUL-001": "Não localizamos a tabela tarifária esperada neste PDF SulAmérica.",
    "PDF-SUL-003": "O regime de coparticipação de uma tabela ficou ambíguo.",
    "PDF-SUL-004": "Valor de faixa possivelmente fragmentado — confira a célula no PDF.",
    "PDF-SUL-005": "A opção não possui exatamente 10 faixas tarifárias.",
    "PDF-SUL-006": "Nome do plano possivelmente fragmentado ou genérico.",
    "PDF-SUL-007": "Algumas linhas tarifárias da tabela SulAmérica não puderam ser montadas.",
    "PDF-TPL-001": "Reconhecemos a operadora, mas não a família de template deste layout.",
    "PDF-F02": "Documento não reconhecido — use entrada manual.",
  };
  const msg = mapa[alerta.codigo];
  if (msg) return msg;
  return alerta.mensagem;
}

export function filtrarOpcoes(opcoes, filtros) {
  const q = (filtros.busca || "").trim().toLowerCase();
  return opcoes.filter((op) => {
    if (op.excluida) return false;
    const nome = nomePlanoExibicao(op).toLowerCase();
    const acom = inferirAcomodacao(op).toLowerCase();
    const regime = rotuloRegime(op).toLowerCase();
    const regiao = inferirRegiao(op).toLowerCase();
    if (q && !`${nome} ${acom} ${regime} ${regiao}`.includes(q)) return false;
    if (filtros.acomodacao && inferirAcomodacao(op) !== filtros.acomodacao) return false;
    if (filtros.regime && grupoCopart(op) !== filtros.regime) return false;
    if (filtros.regiao && inferirRegiao(op) !== filtros.regiao) return false;
    return true;
  });
}

export function agruparOpcoes(opcoes, templateId) {
  if (!templateId?.startsWith("sulamerica") && !templateId?.startsWith("porto")) {
    return [{ titulo: null, opcoes }];
  }
  const grupos = new Map();
  for (const op of opcoes) {
    const g = grupoCopart(op);
    if (!grupos.has(g)) grupos.set(g, []);
    grupos.get(g).push(op);
  }
  const ordem = ["Sem coparticipação", "Coparticipação 30%", "A confirmar", "Outros regimes"];
  return ordem
    .filter((t) => grupos.has(t))
    .map((titulo) => ({ titulo, opcoes: grupos.get(titulo) }))
    .concat(
      [...grupos.keys()]
        .filter((k) => !ordem.includes(k))
        .map((titulo) => ({ titulo, opcoes: grupos.get(titulo) }))
    );
}

export function resumoFinanceiroOpcao(op) {
  if (op.total_recorrente?.centavos != null) {
    return centavosParaReaisExibicao(op.total_recorrente.centavos);
  }
  if (op.subtotal_impresso?.centavos != null) {
    return centavosParaReaisExibicao(op.subtotal_impresso.centavos);
  }
  return "—";
}
