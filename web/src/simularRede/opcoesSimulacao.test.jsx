import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import NavegacaoFerramentas from "../NavegacaoFerramentas.jsx";
import {
  gruposDeOperadora,
  haFiltroGeografico,
  haRedeVerticalizada,
  municipiosDaUf,
  planosDaOperadora,
  temTermoConsulta,
  textoContagem,
  textoContagemLabs,
  zonasDoMunicipio,
} from "./opcoesSimulacao.js";

// Vitest compila .jsx no runtime clássico; os componentes do app usam o automático.
globalThis.React = React;

const opcoes = {
  operadoras: [
    { nome: "Amil", planos: [{ chave: "1", rotulo: "S750" }] },
    { nome: "Porto Seguro", planos: [{ chave: "2", rotulo: "Prata" }, { chave: "3", rotulo: "Ouro" }] },
  ],
  ufs: [
    {
      uf: "RJ",
      municipios: [{ chave: "RJ.RIO DE JANEIRO", rotulo: "Rio De Janeiro", zonas: ["BARRA", "ZONA SUL"] }],
    },
    { uf: "SP", municipios: [] },
  ],
};

describe("navegação lateral", () => {
  it("mostra «Simular rede» sem exigir estudo aberto", () => {
    const html = renderToStaticMarkup(
      <NavegacaoFerramentas ativo="estudos" onMeusEstudos={() => {}} onSimularRede={() => {}} />
    );
    expect(html).toContain("Simular rede");
    expect(html).toContain("Meus estudos");
    expect(html).not.toContain("Voltar ao estudo");
  });

  it("oferece voltar ao estudo só quando há estudo em andamento", () => {
    const html = renderToStaticMarkup(
      <NavegacaoFerramentas
        ativo="simular"
        onMeusEstudos={() => {}}
        onSimularRede={() => {}}
        onVoltarEstudo={() => {}}
        rotuloEstudo="Anistia"
      />
    );
    expect(html).toContain("Voltar ao estudo · Anistia");
    expect(html).toContain('aria-current="page"');
  });
});

describe("selects encadeados", () => {
  it("município depende da UF; zona, do município", () => {
    expect(municipiosDaUf(opcoes, "")).toEqual([]);
    expect(municipiosDaUf(opcoes, "RJ")).toHaveLength(1);
    expect(zonasDoMunicipio(opcoes, "RJ", "RJ.RIO DE JANEIRO")).toEqual(["BARRA", "ZONA SUL"]);
    expect(zonasDoMunicipio(opcoes, "RJ", "")).toEqual([]);
    expect(zonasDoMunicipio(opcoes, "SP", "SP.X")).toEqual([]);
  });

  it("plano depende da operadora", () => {
    expect(planosDaOperadora(opcoes, "")).toEqual([]);
    expect(planosDaOperadora(opcoes, "Porto Seguro").map((p) => p.rotulo)).toEqual(["Prata", "Ouro"]);
  });
});

describe("consulta só com mínimo", () => {
  it("exige 2 caracteres e aceita A+", () => {
    expect(temTermoConsulta("")).toBe(false);
    expect(temTermoConsulta(" ")).toBe(false);
    expect(temTermoConsulta("E")).toBe(false);
    expect(temTermoConsulta("Ei")).toBe(true);
    expect(temTermoConsulta("A+")).toBe(true);
    expect(temTermoConsulta("Einstein")).toBe(true);
  });
});

describe("resultado", () => {
  it("agrupa colunas consecutivas da mesma operadora", () => {
    const g = gruposDeOperadora([
      { chave: "1", operadora: "Amil" },
      { chave: "2", operadora: "Porto Seguro" },
      { chave: "3", operadora: "Porto Seguro" },
    ]);
    expect(g.map((x) => [x.operadora, x.colunas.length])).toEqual([
      ["Amil", 1],
      ["Porto Seguro", 2],
    ]);
  });

  it("detecta filtro geográfico e rede verticalizada", () => {
    expect(haFiltroGeografico({ uf: "", municipio: "", zona: "" })).toBe(false);
    expect(haFiltroGeografico({ uf: "SP", municipio: "", zona: "" })).toBe(true);
    expect(haRedeVerticalizada([{ linhas: [{ rede_verticalizada: "" }] }])).toBe(false);
    expect(haRedeVerticalizada([{ linhas: [{ rede_verticalizada: "Hapvida" }] }])).toBe(true);
  });

  it("conta prestadores e informa os não principais ocultos", () => {
    expect(textoContagem({ total_linhas: 1, ocultos_nao_principais: 0 })).toBe("1 prestador");
    expect(
      textoContagem({ total_linhas: 8, ocultos_nao_principais: 3, mostrando_todos: false })
    ).toBe("8 prestadores · 3 não principal(is) oculto(s)");
    expect(
      textoContagem({ total_linhas: 11, ocultos_nao_principais: 0, mostrando_todos: true })
    ).toBe("11 prestadores");
  });
});

describe("totais de laboratório", () => {
  it("distingue marcas, laboratórios e linhas não curadas", () => {
    expect(textoContagemLabs({ total_linhas: 7, total_encontrado: 7, ocultos_nao_principais: 120 })).toBe(
      "7 marcas · 120 não curada(s) oculta(s)"
    );
    expect(
      textoContagemLabs({
        total_linhas: 85,
        total_encontrado: 85,
        ocultos_nao_principais: 0,
        mostrando_todos: true,
      })
    ).toBe("85 laboratórios");
    expect(
      textoContagemLabs({ total_linhas: 1, total_encontrado: 4, ocultos_nao_principais: 3 })
    ).toBe("1 marca · 4 encontrado(s) · 3 não curada(s) oculta(s)");
  });
});
