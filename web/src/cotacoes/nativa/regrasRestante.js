/** Regras de Início, Ajuda, Importar e Ajustes — espelho de inicio.js, ajuda.js, importar.js, robos.js, robo.js. */

import { FAIXAS, formatarCnpj, plural, visivel } from "./regrasNova";

export const FAIXAS_ANS = FAIXAS.map(([, rotulo]) => rotulo);

export function saudacao(agora = new Date()) {
  const h = agora.getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

export function iguaisJson(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

/** O JS do robô só recusa o que não é .xlsx; não há teto de MB na tela. */
export function problemaArquivoImportar(arquivo) {
  if (!arquivo) return null;
  if (!/\.xlsx$/i.test(arquivo.name || "")) return "Escolha uma planilha do Excel (.xlsx).";
  return null;
}

export function textoPlanosImport(t) {
  return String(t || "")
    .replace(/;\s*/g, ", ")
    .replace(/menor[\s_]*preco(:(\d+))?/i, (m, a, q) => `os ${q || 1} mais baratos`);
}

export function linhaErroImport(e) {
  const id = e.id && !/^L\d+$/.test(e.id) ? ` (${e.id})` : "";
  return `Linha ${e.linha}${id}: ${(e.problemas || []).join("; ")}`;
}

export function resumoImportacao(resultado) {
  const validos = (resultado && resultado.validos) || [];
  const erros = (resultado && resultado.erros) || [];
  const n = validos.reduce((a, v) => a + Number(v.cotacoes || 0), 0);
  const partes = [plural(validos.length, "empresa pronta", "empresas prontas")];
  if (erros.length) partes.push(plural(erros.length, "linha com problema", "linhas com problema"));
  return { validos, erros, n, resumo: partes.join(", ") };
}

export function itensDoImport(opId, validos) {
  return [{ operadora: opId, pedidos: validos.map((v) => v.dados) }];
}

export const PASSOS_AJUDA = [
  {
    vaga: "passo_login",
    titulo: "Guarde o login uma vez",
    generico:
      "Na engrenagem do robô (tela Login), guarde o login do portal. Ele fica no cofre do Windows, só neste computador e no seu usuário do Windows. O robô entra no portal sozinho quando precisa.",
  },
  {
    vaga: "passo_nova",
    titulo: "Preencha a Nova cotação",
    generico: "CNPJ, vidas por faixa etária e os planos. As opções do portal vêm da configuração do seu robô.",
  },
  [
    "Ensaie, se quiser conferir",
    "No ensaio o robô passa por todas as telas com o primeiro plano e para antes de emitir. Serve para conferir valores sem gerar protocolo.",
  ],
  [
    "Gere as cotações",
    "O robô emite uma cotação por plano, baixa o PDF de cada uma e copia para a pasta do cliente com o nome de sempre.",
  ],
  [
    "Baixe os PDFs aqui",
    "Em Cotações ficam todas as cotações feitas, com o PDF a um clique. Não precisa entrar no portal para buscar.",
  ],
];

export const PERGUNTAS_AJUDA = [
  [
    "O robô pode emitir a mesma cotação duas vezes?",
    "Sozinho, não. Ele guarda cada cotação emitida (CNPJ, vidas, opções e plano) e pula o que já saiu, mesmo que você peça de novo ou clique em Tentar de novo. Se você quiser emitir de novo de propósito (para testar ou mostrar o robô), clique em Gerar: a tela avisa que a cotação já foi emitida, com o protocolo, e oferece “Emitir de novo mesmo assim”. Sai um protocolo novo e o PDF de antes continua em Cotações. Se o robô clicou em emitir e não viu o protocolo, a cotação fica em “Conferir no portal” e ele não tenta de novo até você conferir.",
  ],
  [
    "Uma cotação ficou em “Conferir no portal”. O que eu faço?",
    "Entre no portal, em Cotações emitidas, e procure pela empresa. Se a cotação saiu, baixe o PDF lá e marque “Saiu: já tenho o PDF” na tela Cotações. Se não saiu, marque “Não saiu: liberar” e peça de novo.",
  ],
  [
    "O robô parou numa tela. E agora?",
    "Abra o pedido (em Cotações ou na faixa escura do topo) e veja o motivo em cada plano. Na maioria das vezes basta clicar em Tentar de novo. Se o mesmo erro se repetir, o portal pode ter mudado: avise quem cuida do robô e mande o registro do pedido.",
  ],
  [
    "Posso usar o computador enquanto o robô trabalha?",
    "Pode. A janela do portal fica escondida e o robô entra sozinho, inclusive se o portal pedir login de novo no meio do caminho. Só não feche a janela preta do Newport Cotações. Se o portal pedir um código de verificação, a faixa dourada no topo pede para você digitar o código que chegou.",
  ],
  [
    "Onde fica a minha senha do portal?",
    "No cofre do Windows (Gerenciador de Credenciais), no seu usuário do Windows. Não vai para planilha, configuração, histórico, registros nem prints, e a tela nunca mostra a senha de volta. Em computador compartilhado, cada corretor entra com o próprio usuário do Windows. Ao sair da Newport, use “Apagar credenciais” na engrenagem do robô.",
  ],
  [
    "O portal recusou a senha. E agora?",
    "O robô para na primeira recusa e não tenta de novo, para não bloquear a sua conta. Confira a senha entrando no portal pelo seu navegador e guarde de novo na engrenagem do robô (tela Login). Se o portal pedir para trocar a senha ou mostrar um captcha, o robô também para e avisa: resolva no seu navegador e tente de novo.",
  ],
  { vaga: "sair_do_portal" },
  { vaga: "acesso_ativo" },
  {
    vaga: "pdfs",
    generico: [
      "Onde ficam os PDFs?",
      "Se você informou a pasta do cliente, uma cópia vai para lá com o nome que a operadora usa. O robô também guarda uma cópia na pasta dele, que é a que você baixa por aqui.",
    ],
  },
  ["retencao"],
  [
    "O robô fecha negócio ou inicia a contratação?",
    "Nunca. Ele só emite a cotação e baixa o PDF. O botão de iniciar a contratação fica sempre com o corretor.",
  ],
  {
    vaga: "configurar",
    generico: [
      "Como mudo o que o robô preenche no portal?",
      "Clique na engrenagem do cartão da operadora (no pé do menu ou em Robôs). Lá estão as telas do portal na ordem em que o robô passa, com o que dá para mudar em cada uma. Mude e clique em Salvar configuração: vale para as próximas cotações. Para uma cotação só, use “Mudar só nesta cotação” na Nova cotação.",
    ],
  },
  { vaga: "versoes" },
];

export function passosAjuda(operadoras) {
  return PASSOS_AJUDA.map((p) => {
    if (Array.isArray(p)) return p;
    const textos = (operadoras || []).map((op) => ((op.textos || {})[p.vaga])).filter(Boolean);
    return [p.titulo, textos.length === 1 ? textos[0] : textos.length ? textos.join(" ") : p.generico];
  });
}

export function perguntasAjuda(operadoras, retencaoDias = 90) {
  const lista = [];
  for (const p of PERGUNTAS_AJUDA) {
    if (Array.isArray(p) && p[0] === "retencao") {
      lista.push([
        "Por quanto tempo as coisas ficam guardadas?",
        `Os arquivos que o robô guarda para si (PDFs, prints e registros) são apagados depois de ${retencaoDias || 90} dias. A pasta do cliente nunca é tocada.`,
      ]);
      continue;
    }
    if (Array.isArray(p)) {
      lista.push(p);
      continue;
    }
    const das = (operadoras || [])
      .map((op) => [op, (((op.textos || {}).perguntas) || {})[p.vaga]])
      .filter(([, t]) => t);
    if (!das.length && p.generico) lista.push(p.generico);
    for (const [op, par] of das) {
      const [q, r] = par;
      lista.push([das.length > 1 || (operadoras || []).length > 1 ? `${op.nome}: ${q}` : q, r]);
    }
  }
  return lista;
}

export function textoDoValor(campo, valor) {
  if (!campo) return String(valor);
  if (campo.tipo === "escolha") {
    return ((campo.opcoes || []).find((o) => String(o[0]) === String(valor)) || [])[1] || String(valor);
  }
  if (campo.tipo === "sim_nao") return valor === "sim" ? "sim" : "não";
  if (campo.tipo === "texto") return valor ? `“${valor}”` : "vazio";
  if (campo.tipo === "faixas" || campo.tipo === "planos") return valor && valor.length ? valor.join(", ") : "nenhum";
  if (campo.tipo === "pares") {
    const n = valor && typeof valor === "object" ? Object.keys(valor).length : 0;
    return n ? plural(n, "linha", "linhas") : "nenhuma linha";
  }
  return String(valor ?? "");
}

/** Como o robô monta o nome (nucleo/saidas.py, nome_pdf_destino). */
export function nomeExemploPdf(modelo, versao = "", ex = {}) {
  let m = String(modelo || "");
  let plano = String(ex.plano || "Plano").toUpperCase();
  if (versao && !m.includes("{versao}")) {
    if (m.includes("{plano_arquivo}")) plano += " " + versao;
    else m = /\.pdf$/i.test(m) ? m.slice(0, -4) + " {versao}.pdf" : m + " {versao}";
  }
  return m
    .replace(/\{plano_arquivo\}/g, plano)
    .replace(/\{plano\}/g, ex.plano || "Plano")
    .replace(/\{protocolo\}/g, "1234567")
    .replace(/\{cnpj\}/g, "12345678000199")
    .replace(/\{acomodacao\}/g, "Apartamento")
    .replace(/\{versao\}/g, versao)
    .replace(/\s+/g, " ")
    .replace(/ \.pdf$/i, ".pdf");
}

export function fraseExemploPdf(modelo, ex = {}) {
  const versoes = ex.versoes || [];
  return (
    `Exemplo: ${nomeExemploPdf(modelo, "", ex)}.` +
    (versoes.length
      ? ` ${ex.frase_versoes || "Com as versões"}: ${versoes.map((v) => nomeExemploPdf(modelo, v, ex)).join(" e ")}.`
      : "")
  );
}

export function carregarRascunho(telas) {
  const campos = {};
  const rascunho = {};
  const pares = {};
  for (const t of telas || []) {
    for (const c of t.campos || []) {
      if (!c.chave) continue;
      campos[c.chave] = c;
      rascunho[c.chave] = JSON.parse(JSON.stringify(c.valor));
      if (c.tipo === "pares") pares[c.chave] = Object.entries(c.valor || {});
    }
  }
  return { campos, rascunho, pares };
}

export function valorDeConfig(chave, campos, rascunho, pares) {
  const c = campos[chave];
  if (c && c.tipo === "pares") {
    return Object.fromEntries((pares[chave] || []).map(([a, b]) => [String(a).trim(), String(b).trim()]).filter(([a, b]) => a && b));
  }
  return rascunho[chave];
}

export function mudancasConfig(campos, rascunho, pares) {
  return Object.keys(campos).filter((k) => !iguaisJson(valorDeConfig(k, campos, rascunho, pares), campos[k].valor));
}

export function diferencasDoPadrao(campos, rascunho, pares) {
  return Object.keys(campos).filter((k) => !iguaisJson(valorDeConfig(k, campos, rascunho, pares), campos[k].padrao));
}

export function valoresParaSalvar(campos, rascunho, pares) {
  const valores = {};
  for (const k of mudancasConfig(campos, rascunho, pares)) {
    valores[k] = valorDeConfig(k, campos, rascunho, pares);
  }
  return valores;
}

export function visivelConfig(campo, campos, rascunho, pares) {
  if (!campo.visivel_se) return true;
  const valores = {};
  for (const k of Object.keys(campo.visivel_se)) {
    valores[k] = valorDeConfig(k, campos, rascunho, pares);
  }
  return visivel(campo, valores);
}

export function hashNativa(h) {
  const t = String(h || "");
  return (
    t.startsWith("#/nova") ||
    t.startsWith("#/andamento/") ||
    t.startsWith("#/cotacoes") ||
    t.startsWith("#/conexoes") ||
    t.startsWith("#/inicio") ||
    t.startsWith("#/ajuda") ||
    t.startsWith("#/importar") ||
    t.startsWith("#/robos") ||
    t.startsWith("#/robo/")
  );
}
