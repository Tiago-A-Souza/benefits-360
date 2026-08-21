import { describe, expect, it } from "vitest";
import { MAX_PROPOSTAS_POR_PAGINA, paginarPropostas } from "./logica.js";

describe("paginarPropostas", () => {
  it("reparte seis propostas em dois blocos de três", () => {
    const seis = Array.from({ length: 6 }, (_, i) => ({ opcao_id: `op-${i + 1}` }));
    const paginas = paginarPropostas(seis);
    expect(MAX_PROPOSTAS_POR_PAGINA).toBe(3);
    expect(paginas.map((p) => p.map((x) => x.opcao_id))).toEqual([
      ["op-1", "op-2", "op-3"],
      ["op-4", "op-5", "op-6"],
    ]);
  });

  it("mantém uma única página quando cabem no limite", () => {
    const duas = [{ opcao_id: "a" }, { opcao_id: "b" }];
    expect(paginarPropostas(duas)).toEqual([duas]);
  });
});
