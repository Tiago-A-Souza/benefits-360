/** Regras da Nova cotação — espelho de rpa/app/web/js/telas/nova.js + base.js (fmt, CNPJ, resumo). */

export const FAIXAS = [
  ["0_18", "0 - 18"],
  ["19_23", "19 - 23"],
  ["24_28", "24 - 28"],
  ["29_33", "29 - 33"],
  ["34_38", "34 - 38"],
  ["39_43", "39 - 43"],
  ["44_48", "44 - 48"],
  ["49_53", "49 - 53"],
  ["54_58", "54 - 58"],
  ["59_mais", "59+"],
];

export const LIMITES = {
  "0_18": [0, 18],
  "19_23": [19, 23],
  "24_28": [24, 28],
  "29_33": [29, 33],
  "34_38": [34, 38],
  "39_43": [39, 43],
  "44_48": [44, 48],
  "49_53": [49, 53],
  "54_58": [54, 58],
  "59_mais": [59, 130],
};

export const STATUS_COTACAO = {
  OK: "Emitida",
  ENSAIO_OK: "Ensaio ok",
  ERRO: "Não emitida",
  VERIFICAR: "Conferir no portal",
  PULADO: "Já emitida antes",
  PARADO: "Parada",
};

export const CONEXAO = {
  desconectado: "Desconectado",
  abrindo: "Abrindo o portal",
  entrando: "Entrando no portal",
  aguardando_portal: "Esperando o portal liberar",
  aguardando_codigo: "Esperando o código",
  conectado: "Conectado",
  ocupado: "Robô trabalhando",
  saindo: "Saindo do portal",
};

export function digitos(t) {
  return String(t || "").replace(/\D/g, "");
}

export function formatarCnpj(t) {
  const d = digitos(t).slice(0, 14);
  let r = d.slice(0, 2);
  if (d.length > 2) r += "." + d.slice(2, 5);
  if (d.length > 5) r += "." + d.slice(5, 8);
  if (d.length > 8) r += "/" + d.slice(8, 12);
  if (d.length > 12) r += "-" + d.slice(12);
  return r;
}

export function cnpjValido(t) {
  const d = digitos(t);
  if (d.length !== 14 || /^(\d)\1+$/.test(d)) return false;
  const calc = (base, pesos) => {
    const r = base.split("").reduce((s, n, i) => s + Number(n) * pesos[i], 0) % 11;
    return r < 2 ? "0" : String(11 - r);
  };
  const p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
  const d1 = calc(d.slice(0, 12), p1);
  const d2 = calc(d.slice(0, 12) + d1, [6, ...p1]);
  return d.slice(12) === d1 + d2;
}

export function plural(n, um, varios) {
  return `${n} ${n === 1 ? um : varios}`;
}

export function listaIdades(t) {
  return String(t || "")
    .split(/[;,\s]+/)
    .filter(Boolean);
}

export function visivel(campo, valores) {
  if (!campo.visivel_se) return true;
  return Object.entries(campo.visivel_se).every(([k, v]) => String(valores[k]) === String(v));
}

export function faixasExatas(operadoras) {
  return new Set((operadoras || []).flatMap((o) => o.faixas_idade_exata || []));
}

export function totalVidas(vidas) {
  return Object.values(vidas).reduce((a, b) => a + Number(b || 0), 0);
}

export function opsAtivas(form, operadoras) {
  return (operadoras || []).filter((o) => form.ops[o.id] && form.ops[o.id].ativa);
}

export function multiplicador(form, op) {
  return op.campos.reduce(
    (m, c) => m * ((c.multiplica && c.multiplica[form.ops[op.id].campos[c.chave]]) || 1),
    1,
  );
}

export function cotacoesDe(form, op) {
  const o = form.ops[op.id];
  return (o.menor ? Number(o.qtdMenor) : o.planos.length) * multiplicador(form, op);
}

export function clonarForm(f) {
  return {
    ...f,
    vidas: { ...f.vidas },
    idades: { ...f.idades },
    ops: Object.fromEntries(
      Object.entries(f.ops).map(([id, o]) => [
        id,
        { ...o, campos: { ...o.campos }, planos: [...o.planos] },
      ]),
    ),
  };
}

export function estadoInicial(operadoras) {
  const ops = {};
  for (const op of operadoras || []) {
    const campos = {};
    for (const c of op.campos || []) {
      campos[c.chave] = c.padrao === undefined || c.padrao === null ? "" : String(c.padrao);
    }
    ops[op.id] = {
      ativa: op.marcada !== false || (operadoras || []).length === 1,
      campos,
      planos: [...(op.planos_padrao || [])],
      menor: op.planos_modo_padrao === "menor_preco",
      qtdMenor: op.menor_preco_padrao || 1,
      ajustar: false,
    };
  }
  return {
    cnpj: "",
    apelido: "",
    pasta: "",
    vidas: Object.fromEntries(FAIXAS.map(([k]) => [k, 0])),
    idades: Object.fromEntries(FAIXAS.map(([k]) => [k, ""])),
    ops,
  };
}

export function aplicarDados(f, dados, operadoras) {
  if (!dados) return f;
  const next = clonarForm(f);
  next.cnpj = digitos(dados.cnpj);
  next.apelido = dados.apelido || "";
  next.pasta = dados.pasta_destino || "";
  for (const [k] of FAIXAS) {
    next.vidas[k] = Number(dados[`vidas_${k}`] || 0);
    next.idades[k] = dados[`idades_${k}`] ? String(dados[`idades_${k}`]) : "";
  }
  const opId = dados.operadora || Object.keys(next.ops)[0];
  const o = next.ops[opId];
  if (!o) return next;
  const op = (operadoras || []).find((x) => x.id === opId);
  const doRobo = new Set(((op && op.campos) || []).filter((c) => c.robo).map((c) => c.chave));
  for (const chave of Object.keys(o.campos)) {
    if (doRobo.has(chave)) continue;
    if (dados[chave] !== undefined && dados[chave] !== null) o.campos[chave] = String(dados[chave]);
  }
  const planos = String(dados.planos || "");
  const m = planos.match(/^menor[\s_]*preco(?::(\d+))?$/i);
  o.menor = !!m;
  if (m) o.qtdMenor = Number(m[1] || o.qtdMenor);
  o.planos = m
    ? []
    : planos
        .split(";")
        .map((p) => p.trim())
        .filter(Boolean)
        .map((p) => (p.includes("|") ? p.split("|").map((x) => x.trim()).join(" | ") : p));
  return next;
}

export function problemasLocais(f, operadoras) {
  const p = [];
  if (!cnpjValido(f.cnpj)) p.push("Digite um CNPJ válido para a empresa.");
  const total = totalVidas(f.vidas);
  const exatas = faixasExatas(operadoras);
  for (const [k, rotulo] of FAIXAS) {
    const qtd = f.vidas[k];
    const idades = listaIdades(f.idades[k]);
    if (exatas.has(rotulo) && qtd > 0) {
      if (idades.length !== qtd) {
        p.push(`Informe ${plural(qtd, "idade", "idades")} na faixa ${rotulo} (você informou ${idades.length}).`);
      }
      const [min, max] = LIMITES[k];
      const fora = idades.filter((i) => !/^\d+$/.test(i) || Number(i) < min || Number(i) > max);
      if (fora.length) p.push(`As idades ${fora.join(", ")} não cabem na faixa ${rotulo}.`);
    }
  }
  for (const op of opsAtivas(f, operadoras)) {
    const o = f.ops[op.id];
    if (total < op.min_vidas || total > op.max_vidas) {
      p.push(
        `A ${op.nome} cota de ${op.min_vidas} a ${op.max_vidas} vidas neste produto; você distribuiu ${total}.`,
      );
    }
    if (!o.menor && o.planos.length === 0) p.push(`Escolha pelo menos um plano da ${op.nome}.`);
    for (const c of op.campos) {
      if (c.chave === "congenere_atual" && visivel(c, o.campos) && !String(o.campos[c.chave] || "").trim()) {
        p.push(`Informe a operadora atual da empresa ou marque que ela não tem plano hoje (${op.nome}).`);
      }
    }
  }
  if (!opsAtivas(f, operadoras).length) p.push("Escolha pelo menos uma operadora.");
  return p;
}

export function montarItens(f, operadoras) {
  return opsAtivas(f, operadoras).map((op) => {
    const o = f.ops[op.id];
    const dados = {
      id: f.apelido.trim() || formatarCnpj(f.cnpj),
      apelido: f.apelido.trim(),
      cnpj: formatarCnpj(f.cnpj),
      pasta_destino: f.pasta.trim(),
      operadora: op.id,
    };
    for (const [k] of FAIXAS) {
      dados[`vidas_${k}`] = f.vidas[k];
      if (f.vidas[k] > 0 && f.idades[k].trim()) dados[`idades_${k}`] = listaIdades(f.idades[k]).join("; ");
    }
    for (const c of op.campos) if (visivel(c, o.campos)) dados[c.chave] = o.campos[c.chave];
    dados.planos = o.menor ? `menor_preco:${o.qtdMenor}` : o.planos.join("; ");
    return { operadora: op.id, pedidos: [dados] };
  });
}

export function resumoDoRobo(op, valor, extras = {}) {
  const ordem = { escolha: 0, sim_nao: 1, texto: 2 };
  const campos = ((op && op.campos) || [])
    .filter((c) => c.robo)
    .sort((a, b) => (ordem[a.tipo] ?? 3) - (ordem[b.tipo] ?? 3));
  const partes = [];
  for (const c of campos) {
    const v = valor(c.chave);
    if (c.tipo === "escolha") {
      const o = (c.opcoes || []).find((x) => String(x[0]) === String(v)) || [];
      const t = o[2] || o[1];
      if (t) partes.push(t);
    } else if (c.tipo === "sim_nao") partes.push(`${v === "sim" ? "com" : "sem"} ${c.titulo || c.rotulo}`);
    else if (c.tipo === "texto" && v) partes.push(`${c.rotulo.toLowerCase()} ${v}`);
  }
  if (extras.produto) partes.push(`produto ${extras.produto}`);
  const minuscula = (t) => (t.length > 1 && t[1] === t[1].toLowerCase() ? t[0].toLowerCase() + t.slice(1) : t);
  return partes.map((p, i) => (i === 0 ? p : minuscula(p))).join(", ");
}

export function fraseResumoBarra(form, operadoras) {
  const total = totalVidas(form.vidas);
  const partes = opsAtivas(form, operadoras).map((op) => `${plural(cotacoesDe(form, op), "cotação", "cotações")} na ${op.nome}`);
  return `${plural(total, "vida", "vidas")}${partes.length ? ", " + partes.join(" e ") : ""}`;
}

export function totalCotacoes(form, operadoras) {
  return opsAtivas(form, operadoras).reduce((a, op) => a + cotacoesDe(form, op), 0);
}

/**
 * Valor do robô → `{ ok, centavos }` ou `{ ok: false, erro }`.
 * Não multiplica float (* 100) nem aceita texto "R$".
 * O RPA grava REAL e o JSON da API serializa **número** (float), não string Decimal.
 * Inteiro JSON = reais inteiros. `{ centavos }` / `comoCentavos` = já é centavo.
 * Mais de duas casas (5.816, 0.1+0.2) → erro, nunca truncamento silencioso.
 */
export function valorRoboParaCentavos(valor, { comoCentavos = false } = {}) {
  if (valor === null || valor === undefined) {
    return { ok: false, erro: "valor ausente" };
  }
  if (typeof valor === "object") {
    if (valor && Number.isInteger(valor.centavos)) return { ok: true, centavos: valor.centavos };
    return { ok: false, erro: "objeto sem centavos inteiros" };
  }
  if (typeof valor === "number") {
    if (!Number.isFinite(valor)) return { ok: false, erro: "número inválido" };
    if (valor < 0) return { ok: false, erro: "valor negativo" };
    if (comoCentavos) {
      if (!Number.isInteger(valor)) return { ok: false, erro: "centavos devem ser inteiros" };
      return { ok: true, centavos: valor };
    }
    if (Number.isInteger(valor)) return { ok: true, centavos: valor * 100 };
    if (/e/i.test(valor.toString())) return { ok: false, erro: "notação científica" };
    return partesDecimais(valor.toString());
  }
  if (typeof valor === "string") {
    const t = valor.trim();
    if (!t) return { ok: false, erro: "valor ausente" };
    if (/[R$\s]/.test(t) || (t.includes(".") && t.includes(","))) {
      return { ok: false, erro: "não aceite texto monetário formatado" };
    }
    if (comoCentavos) {
      if (!/^\d+$/.test(t)) return { ok: false, erro: "centavos devem ser inteiros" };
      return { ok: true, centavos: parseInt(t, 10) };
    }
    const canon = t.includes(",") && !t.includes(".") ? t.replace(",", ".") : t;
    return partesDecimais(canon);
  }
  return { ok: false, erro: "tipo não suportado" };
}

function partesDecimais(s) {
  const m = s.match(/^(\d+)(?:\.(\d+))?$/);
  if (!m) return { ok: false, erro: "formato decimal inválido" };
  const frac = m[2] || "";
  if (frac.length > 2 && !/^0+$/.test(frac.slice(2))) {
    return { ok: false, erro: "mais de duas casas decimais" };
  }
  const reais = parseInt(m[1], 10);
  const cents = parseInt((frac + "00").slice(0, 2), 10);
  return { ok: true, centavos: reais * 100 + cents };
}

/** Exibição a partir de centavos inteiros. Ausente ou inválido → "—", nunca R$ 0,00. */
export function formatarValorRobo(valor, opts = {}) {
  const r = valorRoboParaCentavos(valor, opts);
  if (!r.ok) return "—";
  return formatarCentavos(r.centavos);
}

function formatarCentavos(centavos) {
  let neg = centavos < 0;
  let v = neg ? -centavos : centavos;
  const reais = Math.trunc(v / 100);
  const cents = v % 100;
  const inteiro = String(reais).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${neg ? "-" : ""}R$\u00a0${inteiro},${String(cents).padStart(2, "0")}`;
}

export const TEXTO_PENDENCIA = {
  emitindo:
    "O robô clicou em emitir e não viu o protocolo. Entre no portal, em Cotações emitidas, e veja se esta cotação saiu.",
  emitida: "Saiu no portal, mas o PDF não veio. O robô tenta baixar de novo na próxima vez que você gerar cotações.",
  pdf_manual: "Saiu no portal, mas o robô não conseguiu baixar o PDF. Baixe à mão no portal, em Cotações emitidas.",
};

export function tituloProblemaLogin(opNome, motivo) {
  if (motivo === "sem_credenciais") return `Cadastre o login da ${opNome} na engrenagem do robô`;
  if (motivo === "recusadas") return `O portal da ${opNome} recusou o login guardado`;
  if (motivo === "senha_comprida") return "A senha guardada é maior do que o portal aceita";
  return `O robô não conseguiu entrar no portal da ${opNome}`;
}

export function agruparVersoes(lista, operadoras) {
  const grupos = new Map();
  for (const c of lista) {
    const k = [c.trabalho_id, c.cnpj, c.pedido_id, c.plano, c.acomodacao].join("|");
    if (!grupos.has(k)) grupos.set(k, []);
    grupos.get(k).push(c);
  }
  const posicao = (c) => {
    const op = (operadoras || []).find((o) => o.id === c.operadora);
    const i = Object.keys((op && op.versoes) || {}).indexOf(c.versao);
    return i < 0 ? 99 : i;
  };
  const saida = [];
  for (const g of grupos.values()) {
    g.sort((a, b) => posicao(a) - posicao(b));
    g.forEach((c, i) => {
      saida.push({
        ...c,
        _mesmoPlano: i > 0 && !!c.versao && !!g[i - 1].versao && c.versao !== g[i - 1].versao,
      });
    });
  }
  return saida;
}

export function motivoCotacao(c, operadoras) {
  const op = (operadoras || []).find((o) => o.id === c.operadora);
  const etapa = c.etapa_erro && op ? (op.etapas.find((x) => x.id === c.etapa_erro) || {}).nome : c.etapa_erro || "";
  const detalhe = (c.erro || "").split(" | ")[0];
  switch (c.status) {
    case "ERRO":
      return `O robô parou${etapa ? ` na tela ${etapa}` : ""}: ${detalhe}. Pedir de novo é seguro: nada foi emitido.`;
    case "VERIFICAR": {
      const erro = c.erro || "";
      const prot = c.protocolo ? ` (protocolo ${c.protocolo})` : "";
      if (erro.includes("clicou em emitir") || erro.includes("durante a emissão"))
        return "O robô clicou em emitir e não viu o protocolo. Confira no portal, em Cotações emitidas, se esta cotação saiu; a pendência fica no topo de Cotações.";
      if (erro.includes("à mão"))
        return `A cotação saiu no portal${prot}, mas o robô não conseguiu baixar o PDF. Baixe à mão no portal, em Cotações emitidas, e marque como resolvida em Cotações.`;
      return `A cotação saiu no portal${prot}, mas o PDF não veio. O robô tenta baixar de novo na próxima vez que gerar cotações.`;
    }
    case "PULADO":
      return `Esta cotação já tinha sido emitida antes${c.protocolo ? ` (protocolo ${c.protocolo})` : ""}. O robô não emite de novo o que já saiu.`;
    case "PARADO":
      return "Você parou o robô antes desta cotação. Nada foi emitido para ela.";
    default:
      return c.erro ? c.erro : null;
  }
}

export function textoVersao(c, operadoras) {
  const op = (operadoras || []).find((o) => o.id === c.operadora);
  return ((op && op.versoes) || {})[c.versao] || c.versao || "";
}

export function quando(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const ontem = new Date();
  ontem.setDate(ontem.getDate() - 1);
  if (d.toDateString() === new Date().toDateString()) return `hoje às ${hora}`;
  if (d.toDateString() === ontem.toDateString()) return `ontem às ${hora}`;
  return `${d.toLocaleDateString("pt-BR")} às ${hora}`;
}

export function nativaLigada() {
  if (typeof window === "undefined") return false;
  const q = new URLSearchParams(window.location.search);
  if (q.get("cotacoes-nativa") === "1") return true;
  try {
    if (import.meta.env.VITE_COTACOES_NATIVA !== "1") return false;
  } catch {
    return false;
  }
  const h = window.location.hash || "";
  return h.startsWith("#/nova") || h.startsWith("#/andamento/");
}

/**
 * Confirmações humanas da Nova cotação (ensaio / emitir / já emitidas).
 * confirmar(...) → true | false | "alternativa"
 */
export async function fluxoConfirmacao(modo, validacao, nomesOps, confirmar) {
  const ja = (modo === "emitir" && validacao.ja_emitidas) || [];
  const linhasJa = ja.map(
    (j) =>
      `${j.plano}: protocolo ${j.protocolo || "—"}${j.quando ? `, emitida ${quando(j.quando)}` : ""}.`,
  );
  let reemitir = [];
  if (ja.length && ja.length >= validacao.cotacoes) {
    const reemitiveis = ja.filter((j) => j.protocolo);
    const escolha = await confirmar({
      titulo: ja.length === 1 ? "Esta cotação já foi emitida" : "Estas cotações já foram emitidas",
      texto: [
        ...linhasJa,
        "Sozinho, o robô não emite de novo a mesma cotação (mesma empresa, vidas, opções e plano): é o que evita protocolo duplicado quando um pedido é repetido sem querer. O PDF já está em Cotações.",
        reemitiveis.length
          ? "Para testar ou mostrar o robô, você pode emitir de novo de propósito: sai um protocolo novo."
          : "Para uma cotação nova, mude o plano, as vidas ou as opções.",
      ],
      ok: "Ver em Cotações",
      cancelar: "Voltar",
      principal: false,
      alternativa: reemitiveis.length ? "Emitir de novo mesmo assim" : null,
    });
    if (escolha !== "alternativa") {
      return { abortar: true, irCotacoes: !!escolha };
    }
    const n = reemitiveis.length;
    const certeza = await confirmar({
      titulo: n === 1 ? "Emitir de novo esta cotação?" : `Emitir de novo estas ${n} cotações?`,
      texto: [
        "O robô emite de novo no portal e cada cotação ganha um protocolo novo. Os protocolos de antes continuam no portal e os PDFs de antes continuam em Cotações.",
        "Use para testar e mostrar o robô. Com cliente de verdade, evite repetir a mesma cotação.",
      ],
      ok: n === 1 ? "Emitir de novo" : `Emitir de novo as ${n}`,
    });
    if (!certeza) return { abortar: true };
    reemitir = reemitiveis.map((j) => j.protocolo);
  } else if (modo === "emitir") {
    const ops = nomesOps.join(" e ");
    const novas = validacao.cotacoes - ja.length;
    const reemitiveis = ja.filter((j) => j.protocolo);
    const ok = await confirmar({
      titulo: `Gerar ${plural(novas, "cotação", "cotações")} na ${ops}?`,
      texto: [
        "Cada cotação gera um protocolo de verdade no portal da operadora.",
        "O robô entra no portal sozinho, com o login guardado na engrenagem.",
        ja.length ? `Já emitidas antes (o robô pula, não sai de novo): ${ja.map((j) => j.plano).join("; ")}.` : null,
      ].filter(Boolean),
      ok: `Gerar ${plural(novas, "cotação", "cotações")}`,
      alternativa: reemitiveis.length ? `Emitir todas (${validacao.cotacoes})` : null,
    });
    if (!ok) return { abortar: true };
    if (ok === "alternativa") {
      const n = reemitiveis.length;
      const certeza = await confirmar({
        titulo: n === 1 ? "Emitir de novo também a que já saiu?" : `Emitir de novo também as ${n} que já saíram?`,
        texto: [
          ...reemitiveis.map((j) => `${j.plano}: protocolo ${j.protocolo}.`),
          "Elas ganham um protocolo novo; os de antes continuam no portal e os PDFs de antes continuam em Cotações.",
          "Use para testar e mostrar o robô. Com cliente de verdade, evite repetir a mesma cotação.",
        ],
        ok: `Emitir as ${validacao.cotacoes}`,
      });
      if (!certeza) return { abortar: true };
      reemitir = reemitiveis.map((j) => j.protocolo);
    }
  }
  return { reemitir };
}

export const CONFIRMACOES_REPETIR = {
  gerar: {
    titulo: "Gerar as cotações de verdade?",
    ok: "Gerar as cotações",
    texto: [
      "O robô repete o pedido e emite uma cotação por plano no portal da operadora, com protocolo.",
      "O que já foi emitido antes não sai de novo.",
    ],
  },
  continuar: {
    titulo: "Continuar de onde parou?",
    ok: "Continuar",
    texto: ["O robô emite as cotações que faltaram.", "As que já saíram não saem de novo."],
  },
  tentar: {
    titulo: "Tentar de novo?",
    ok: "Tentar de novo",
    texto: ["O robô tenta de novo as cotações que não saíram.", "As que já saíram não saem de novo."],
  },
};

export function contarStatus(cotacoes) {
  const n = {};
  for (const c of cotacoes || []) n[c.status] = (n[c.status] || 0) + 1;
  return n;
}

export function nomeEtapa(operadoras, opId, etapa) {
  const op = (operadoras || []).find((o) => o.id === opId);
  const achada = op && (op.etapas || []).find((x) => x.id === etapa);
  return achada ? achada.nome : etapa;
}

export function empresaDe(c) {
  return c.razao_social || formatarCnpj(c.cnpj);
}

export function horaRegistro(iso) {
  return iso ? new Date(iso).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "";
}

export function subtituloTrabalho(t) {
  const qtd = t.total_cotacoes ? plural(t.total_cotacoes, "cotação", "cotações") : "";
  const empresas = t.total_pedidos > 1 ? ` em ${t.total_pedidos} empresas` : "";
  if (t.tipo === "conectar") return `Teste do login no portal, pedido ${quando(t.criado_em)}`;
  if (t.modo === "ensaio") {
    return `Ensaio, sem emitir${t.total_pedidos > 1 ? `, de ${t.total_pedidos} empresas` : ""}. Pedido ${quando(t.criado_em)}.`;
  }
  return `Emissão de ${qtd}${empresas}. Pedida ${quando(t.criado_em)}.`;
}
