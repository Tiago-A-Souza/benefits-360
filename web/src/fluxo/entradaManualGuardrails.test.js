import { describe, expect, it } from "vitest";
import { faixaVazia, sugestaoFiscalPorOperadora, tabelaVazia } from "../constants";

describe("entrada manual — quantidade_cotada default", () => {
  it("começa em 0 como o caminho PDF", () => {
    expect(faixaVazia(0).quantidade_cotada).toBe(0);
    expect(tabelaVazia().every((f) => f.quantidade_cotada === 0)).toBe(true);
  });
});

describe("sugestão fiscal por operadora", () => {
  it("Amil → operadora", () => {
    const s = sugestaoFiscalPorOperadora("Amil");
    expect(s.tipo_fiscal).toBe("operadora");
    expect(s.price_basis).toBe("exclui_iof");
    expect(s.evidencia).toMatch(/Amil/i);
  });

  it("Bradesco / SulAmérica / Porto → seguradora", () => {
    for (const nome of ["Bradesco Saúde", "SulAmérica", "Porto Seguro"]) {
      const s = sugestaoFiscalPorOperadora(nome);
      expect(s.tipo_fiscal).toBe("seguradora");
      expect(s.price_basis).toBe("exclui_iof");
      expect(s.evidencia.length).toBeGreaterThan(10);
    }
  });

  it("operadora desconhecida → null", () => {
    expect(sugestaoFiscalPorOperadora("Hapvida")).toBeNull();
    expect(sugestaoFiscalPorOperadora("")).toBeNull();
  });
});
