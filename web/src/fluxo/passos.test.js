import { describe, expect, it } from "vitest";
import { passosVisiveis } from "./passos.js";

describe("passosVisiveis", () => {
  it("renovação um subgrupo: seis etapas com rede antes do comparativo", () => {
    const rascunho = {
      formato: "renovacao",
      subgrupos_atuais: [{ id: "sg-a" }],
    };
    const passos = passosVisiveis(rascunho);
    expect(passos).toHaveLength(5);
    const chaves = passos.map((p) => p.chave);
    expect(chaves.indexOf("rede")).toBeLessThan(chaves.indexOf("comparativo"));
    expect(chaves).toContain("rede");
    expect(chaves.at(-1)).toBe("comparativo");
  });

  it("renovação multiplos subgrupos: sete etapas incluindo correspondência", () => {
    const rascunho = {
      formato: "renovacao",
      subgrupos_atuais: [{ id: "sg-a" }, { id: "sg-b" }],
    };
    const passos = passosVisiveis(rascunho);
    expect(passos).toHaveLength(6);
    expect(passos.map((p) => p.chave)).toEqual([
      "base",
      "plano",
      "cotacoes",
      "selecionados",
      "rede",
      "comparativo",
    ]);
  });
});
