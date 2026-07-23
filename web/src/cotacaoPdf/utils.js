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
  parcial: "Coparticipação parcial",
  percentual: "Coparticipação percentual",
  customizada: "Coparticipação customizada",
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
  if (regime === "sem") return REGIME_LABELS.sem;
  if (pct != null) return `Coparticipação ${pct}%`;
  return REGIME_LABELS[regime] || regime || "—";
}

export function grupoCopart(op) {
  const regime = op.regime_copart?.texto;
  const pct = op.copart_percentual?.inteiro;
  if (regime === "sem") return "Sem coparticipação";
  if (pct === 30 || regime === "parcial") return "Coparticipação 30%";
  if (pct != null) return `Coparticipação ${pct}%`;
  return "Outros regimes";
}

export function situacaoOpcao(op) {
  if (op.excluida) return { codigo: "excluida", rotulo: "Excluída" };
  const faixasOk = op.tabela?.filter((fx) => fx.valor?.centavos != null).length || 0;
  if (faixasOk === 0) return { codigo: "incompleto", rotulo: "Incompleto" };
  const pend =
    [op.plano_nome, op.regime_copart, op.tipo_fiscal].some(
      (c) => c && c.estado === "revisar"
    ) ||
    op.tabela.some((fx) => fx.valor?.estado === "revisar") ||
    (op.reconciliacao && !op.reconciliacao.ok);
  if (pend) return { codigo: "revisao", rotulo: "Exige revisão" };
  if (faixasOk < 10) return { codigo: "incompleto", rotulo: "Incompleto" };
  return { codigo: "pronto", rotulo: "Pronto" };
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
  const mapa = {
    "PDF-PORTO-001": "O plano destacado no resumo financeiro não foi associado automaticamente a uma linha da tabela.",
    "PDF-PORTO-004": "Não localizamos a tabela geral de prêmios neste PDF.",
    "PDF-PORTO-005": "Há planos com códigos muito parecidos — confira o nome antes de selecionar.",
    "PDF-SUL-001": "Não localizamos a tabela tarifária esperada neste PDF SulAmérica.",
    "PDF-SUL-003": "O regime de coparticipação de uma tabela ficou ambíguo.",
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
  if (!templateId?.startsWith("sulamerica")) {
    return [{ titulo: null, opcoes }];
  }
  const grupos = new Map();
  for (const op of opcoes) {
    const g = grupoCopart(op);
    if (!grupos.has(g)) grupos.set(g, []);
    grupos.get(g).push(op);
  }
  const ordem = ["Sem coparticipação", "Coparticipação 30%", "Outros regimes"];
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
