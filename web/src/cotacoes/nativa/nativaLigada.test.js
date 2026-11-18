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

  it("flag Vite deste build não liga nativa", () => {
    expect(import.meta.env.VITE_COTACOES_NATIVA).not.toBe("1");
  });

  it("ligada com ?cotacoes-nativa=1", () => {
    vi.stubGlobal("window", { location: { search: "?cotacoes-nativa=1", hash: "" } });
    expect(nativaLigada()).toBe(true);
  });

  it("hash #/nova sozinho não liga nativa (Benefits não usa hash)", () => {
    vi.stubGlobal("window", { location: { search: "", hash: "#/nova" } });
    expect(nativaLigada()).toBe(false);
    vi.stubGlobal("window", { location: { search: "", hash: "#/andamento/12" } });
    expect(nativaLigada()).toBe(false);
  });
});
