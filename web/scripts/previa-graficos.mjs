/** Prévia estática dos gráficos da etapa 1, para conferir acabamento.
 *
 * Renderiza o componente real com o CSS real em várias larguras de contêiner,
 * incluindo os casos-limite. Não faz parte do app: é ferramenta de revisão.
 *
 *   cd web && npx vite-node scripts/previa-graficos.mjs
 *   → .data/previa-graficos-etapa1.html
 */

import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

globalThis.React = React;

const AQUI = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(AQUI, "..");

const { default: TabelaFaixasCotacao } = await import(
  resolve(WEB, "src/fluxo/TabelaFaixasCotacao.jsx")
);
const { derivarGraficos } = await import(resolve(WEB, "src/fluxo/graficosFaixas.js"));
const { default: GraficosFaixasCotacao } = await import(
  resolve(WEB, "src/fluxo/GraficosFaixasCotacao.jsx")
);

const fixture = (nome) =>
  JSON.parse(readFileSync(resolve(WEB, "src/fluxo/__fixtures__", nome), "utf-8"));

const CASOS = [
  ["Anistia 41 — 29F / 12M, tabela (estado inicial)", "tabelaAnistia41.json", "tabela"],
  ["Anistia 41 — gráficos", "tabelaAnistia41.json", "grafico"],
  ["IVTEC 12 com sexo — 6F / 6M", "tabelaIvtec12ComSexo.json", "grafico"],
  ["Sexo parcial — 2F / 0M / 2 não informado", "tabelaSexoParcial.json", "grafico"],
  ["Uma vida só — fatia de 100% e coluna sozinha", "tabelaUmaVida.json", "grafico"],
  ["Todas na mesma faixa", "tabelaMesmaFaixa.json", "grafico"],
  ["Trezentas vidas concentradas em duas faixas", "tabela300Vidas.json", "grafico"],
  ["Três vidas — percentuais 34/33/33", "tabelaTresIguais.json", "grafico"],
  ["Base sem coluna SEXO — nenhum botão de gráfico", "tabelaSemSexo12.json", "tabela"],
];

const LARGURAS = [1280, 1024, 900, 760, 700, 560, 420, 360];

const css = readFileSync(resolve(WEB, "src/styles.css"), "utf-8").replace(
  /@import[^;]+;/g,
  "",
);

function bloco(titulo, nomeFixture, vista) {
  const tabela = fixture(nomeFixture);
  const corpo =
    vista === "grafico"
      ? renderToStaticMarkup(
          React.createElement(GraficosFaixasCotacao, {
            graficos: derivarGraficos(tabela),
          }),
        )
      : renderToStaticMarkup(React.createElement(TabelaFaixasCotacao, { tabela }));
  const painel =
    vista === "grafico"
      ? `<div class="panel"><div class="panel-head"><div><h2>Faixas para cotação</h2>
<p>Quadro ANS para colar no formulário da operadora.</p></div>
<div class="gr-acoes"><button type="button" class="btn-compacto secundario" aria-pressed="true">Ver tabela</button></div>
</div><div class="panel-body"><div class="gr-area">${corpo}</div></div></div>`
      : corpo;

  return LARGURAS.map(
    (largura) => `
<section class="previa">
  <h3>${titulo} <span>· ${largura}px</span></h3>
  <div class="previa-caixa" style="width:${largura}px">${painel}</div>
</section>`,
  ).join("\n");
}

const html = `<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<title>Prévia — gráficos da etapa 1</title>
<style>${css}</style>
<style>
  body { padding: 24px; background: var(--page); }
  .previa { margin: 0 0 28px; }
  .previa h3 { font-size: 12px; text-transform: uppercase; letter-spacing: .07em;
    color: var(--muted); margin: 0 0 8px; }
  .previa h3 span { color: var(--blue); }
  .previa-caixa { max-width: 100%; overflow: hidden; resize: horizontal;
    outline: 1px dashed var(--line-strong); }
</style>
</head><body>
<h1 style="font-size:18px;margin:0 0 20px">Gráficos da etapa 1 — casos-limite por largura</h1>
${CASOS.map(([t, f, v]) => bloco(t, f, v)).join("\n")}
</body></html>
`;

const saida = resolve(WEB, "..", ".data", "previa-graficos-etapa1.html");
mkdirSync(dirname(saida), { recursive: true });
writeFileSync(saida, html, "utf-8");
console.log(`prévia: ${saida}`);
console.log(`casos: ${CASOS.length} × larguras: ${LARGURAS.length}`);
