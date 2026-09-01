/** Render real dos gráficos e da alternância — casos-limite do acabamento. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

// O Vitest compila os .jsx no runtime clássico; os componentes do app são
// escritos para o automático (plugin-react) e não importam React. Só aqui,
// no ambiente de teste, o global cobre essa diferença.
globalThis.React = React;

import GraficosFaixasCotacao from "./GraficosFaixasCotacao.jsx";
import TabelaFaixasCotacao from "./TabelaFaixasCotacao.jsx";
import { derivarGraficos } from "./graficosFaixas.js";

import anistia41 from "./__fixtures__/tabelaAnistia41.json";
import mesmaFaixa from "./__fixtures__/tabelaMesmaFaixa.json";
import semSexo12 from "./__fixtures__/tabelaSemSexo12.json";
import sexoParcial from "./__fixtures__/tabelaSexoParcial.json";
import trezentas from "./__fixtures__/tabela300Vidas.json";
import umaVida from "./__fixtures__/tabelaUmaVida.json";

function render(tabela) {
  return renderToStaticMarkup(
    <GraficosFaixasCotacao graficos={derivarGraficos(tabela)} />,
  );
}

function contar(html, agulha) {
  return html.split(agulha).length - 1;
}

describe("render da rosca", () => {
  it("desenha uma fatia por sexo presente, com valor visível", () => {
    const html = render(anistia41);
    expect(contar(html, "gr-fatia gr-fatia--feminino")).toBe(1);
    expect(contar(html, "gr-fatia gr-fatia--masculino")).toBe(1);
    expect(html).toContain(">29<");
    expect(html).toContain(">12<");
    expect(html).toContain(">71%<");
    expect(html).toContain(">29%<");
  });

  it("fatia de 100%: círculo cheio, sem dasharray nem risco residual", () => {
    const html = render(umaVida);
    expect(contar(html, "gr-fatia gr-fatia--feminino")).toBe(1);
    expect(contar(html, "gr-fatia gr-fatia--masculino")).toBe(0);
    expect(html).not.toContain("stroke-dasharray");
    expect(html).not.toContain("stroke-dashoffset");
  });

  it("fatia de 0% aparece na legenda, nunca no desenho", () => {
    const html = render(umaVida);
    expect(html).toContain("gr-swatch--masculino");
    expect(html).toContain(">0%<");
    expect(contar(html, "gr-fatia gr-fatia--masculino")).toBe(0);
  });

  it("sem «Não informado» quando a base tem sexo completo", () => {
    expect(render(anistia41)).not.toContain("gr-swatch--nao_informado");
    expect(render(sexoParcial)).toContain("gr-swatch--nao_informado");
  });

  it("distingue as fatias por textura, não só por cor", () => {
    const html = render(anistia41);
    expect(html).toContain("gr-fatia-textura");
    expect(html).toContain("gr-hachura-traco");
  });
});

describe("render das barras", () => {
  it("dez barras sempre, faixa vazia marcada", () => {
    const html = render(anistia41);
    expect(contar(html, '<li class="gr-barra')).toBe(10);
    expect(contar(html, "gr-barra gr-barra--zero")).toBeGreaterThan(0);
  });

  it("todo valor fica escrito, sem depender de hover", () => {
    const html = render(mesmaFaixa);
    expect(contar(html, "gr-barra-valor num")).toBe(10);
    expect(html).toContain(">8<");
  });

  it("base grande: a faixa de uma vida recebe fração > 0", () => {
    const html = render(trezentas);
    expect(html).toMatch(/--fracao:0\.00526/);
    expect(contar(html, '<li class="gr-barra')).toBe(10);
  });

  it("rótulos curtos no eixo, rótulo ANS completo no texto alternativo", () => {
    const html = render(anistia41);
    expect(html).toContain("0\u201318");
    expect(html).toContain("59+");
    expect(html).toContain("0 a 18: ");
  });
});

describe("acessibilidade", () => {
  it("cada gráfico tem role e descrição associada", () => {
    const html = render(anistia41);
    expect(contar(html, 'role="img"')).toBe(2);
    expect(contar(html, "aria-labelledby=")).toBe(2);
    expect(contar(html, 'class="apenas-leitor"')).toBe(2);
    expect(html).toContain("Distribuição por sexo em 41 vidas");
    expect(html).toContain("Vidas por faixa etária, 41 no total");
  });
});

describe("alternância na etapa 1", () => {
  it("estado inicial: tabela e «Copiar tabela», botão «Ver gráficos»", () => {
    const html = renderToStaticMarkup(<TabelaFaixasCotacao tabela={anistia41} />);
    expect(html).toContain("tabela-faixas-cotacao");
    expect(html).toContain("Copiar tabela");
    expect(html).toContain("Ver gráficos");
    expect(html).toContain('aria-pressed="false"');
    expect(html).not.toContain("gr-faixas");
  });

  it("base sem sexo: nenhum botão de gráfico, etapa 1 como hoje", () => {
    const html = renderToStaticMarkup(<TabelaFaixasCotacao tabela={semSexo12} />);
    expect(html).toContain("Copiar tabela");
    expect(html).not.toContain("Ver gráficos");
    expect(html).not.toContain("aria-pressed");
    expect(html).not.toContain("gr-faixas");
  });

  it("a tabela permanece intacta ao lado da nova ação", () => {
    const html = renderToStaticMarkup(<TabelaFaixasCotacao tabela={anistia41} />);
    // Cabeçalho e linha de total continuam como antes dos gráficos.
    expect(html).toContain("Tit. M");
    expect(html).toContain("Dep. F");
    expect(contar(html, "total-row")).toBe(1);
  });
});
