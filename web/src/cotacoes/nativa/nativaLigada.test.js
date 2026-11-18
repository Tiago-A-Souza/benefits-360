import { describe, expect, it, vi, afterEach } from "vitest";
import { nativaLigada } from "./regrasNova";

describe("nativaLigada", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("desligada sem query", () => {
    vi.stubGlobal("window", { location: { search: "", hash: "" } });
    expect(nativaLigada()).toBe(false);
  });

  it("ligada com ?cotacoes-nativa=1", () => {
    vi.stubGlobal("window", { location: { search: "?cotacoes-nativa=1", hash: "" } });
    expect(nativaLigada()).toBe(true);
  });
});
