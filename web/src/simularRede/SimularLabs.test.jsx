import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

vi.mock("../api.js", () => ({
  obterOpcoesSimulacaoRede: () => new Promise(() => {}),
  obterOpcoesSimulacaoLaboratorio: () => new Promise(() => {}),
  consultarRedePorHospital: () => new Promise(() => {}),
  consultarRedePorPlano: () => new Promise(() => {}),
  consultarRedePorLaboratorio: () => new Promise(() => {}),
  consultarRedePorPlanoLaboratorio: () => new Promise(() => {}),
  mensagemErroOperador: (e, fallback) => e?.message || fallback,
}));

import SimularRede from "./SimularRede.jsx";
import SimularLabs, { TabelaLabs } from "./SimularLabs.jsx";

globalThis.React = React;

const RESP_MARCAS = {
  modo: "laboratorio",
  colunas: [
    { chave: "10", operadora: "Amil", plano: "S750" },
    { chave: "20", operadora: "Porto Seguro", plano: "Prata" },
  ],
  blocos: [
    {
      titulo: "Laboratórios",
      municipio: "",
      linhas: [
        {
          linha_id: "marca:DELBONI",
          prestador_nome: "Delboni",
          principal: true,
          municipios: ["Sao Paulo", "Osasco"],
          celulas: { 10: "✓", 20: "✓" },
        },
        {
          linha_id: "marca:LAVOISIER",
          prestador_nome: "Lavoisier",
          principal: true,
          municipios: ["Sao Paulo"],
          celulas: { 10: "✓", 20: "" },
        },
      ],
    },
  ],
  contagem_por_coluna: { 10: 2, 20: 1 },
};

describe("seletor Hospitais | Laboratórios", () => {
  it("abre em Hospitais com os modos de hospital intactos", () => {
    const html = renderToStaticMarkup(
      <SimularRede onMeusEstudos={() => {}} onSimularRede={() => {}} />
    );
    expect(html).toContain("Hospitais");
    expect(html).toContain("Laboratórios");
    expect(html).toContain("Por hospital");
    expect(html).toContain("Por plano");
    expect(html).toContain("Zona");
    expect(html).toContain("Ver todos os prestadores");
    expect(html).not.toContain("Por laboratório");
    expect(html).not.toContain("Ver todos os laboratórios");
  });
});

describe("SimularLabs", () => {
  it("não oferece zona nem códigos H/M/PS", () => {
    const html = renderToStaticMarkup(<SimularLabs />);
    expect(html).toContain("Por laboratório");
    expect(html).toContain("Por plano");
    expect(html).toContain("Ver todos os laboratórios");
    expect(html).toContain("Marca ou prestador");
    expect(html).not.toContain(">Zona<");
    expect(html).not.toContain("Hospital geral");
    expect(html).not.toContain("Pronto-socorro");
  });

  it("tabela agrupa marca, lista municípios, usa ✓ e linha Cobertos", () => {
    const html = renderToStaticMarkup(<TabelaLabs resp={RESP_MARCAS} />);
    expect(html).toContain("Delboni");
    expect(html).toContain("Sao Paulo, Osasco");
    expect(html).toContain("Lavoisier");
    expect(html).toContain("✓");
    expect(html).not.toContain("ULTRA");
    expect(html).not.toContain("HGER");
    expect(html).toContain("Cobertos");
    expect(html).toContain(">2<");
    expect(html).toContain(">1<");
    expect(html).toContain("Laboratório");
  });

  it("marca prestador não curado no modo ver todos", () => {
    const html = renderToStaticMarkup(
      <TabelaLabs
        resp={{
          colunas: [{ chave: "1", operadora: "Amil", plano: "S750" }],
          blocos: [
            {
              titulo: "Sao Paulo · SP",
              municipio: "SP.SAO PAULO",
              linhas: [
                {
                  linha_id: "l9",
                  prestador_nome: "LAB EXEMPLO",
                  principal: false,
                  municipios: [],
                  celulas: { 1: "✓" },
                },
              ],
            },
          ],
          contagem_por_coluna: { 1: 1 },
        }}
      />
    );
    expect(html).toContain("Não curado");
    expect(html).toContain("LAB EXEMPLO");
  });
});
