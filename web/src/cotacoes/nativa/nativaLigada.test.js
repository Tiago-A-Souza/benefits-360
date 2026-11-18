import { describe, expect, it, vi, afterEach } from "vitest";
import { iframeCotacoes, nativaLigada } from "./regrasNova";

describe("nativaLigada e iframeCotacoes", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("desligada sem query nem hash", () => {
    vi.stubGlobal("window", { location: { search: "", hash: "" } });
    expect(nativaLigada()).toBe(false);
    expect(iframeCotacoes()).toBe(false);
  });

  it("flag Vite deste build não é exigida: hash de cotações liga nativa", () => {
    vi.stubGlobal("window", { location: { search: "", hash: "#/cotacoes" } });
    expect(nativaLigada()).toBe(true);
  });

  it("ligada com ?cotacoes-nativa=1", () => {
    vi.stubGlobal("window", { location: { search: "?cotacoes-nativa=1", hash: "" } });
    expect(nativaLigada()).toBe(true);
  });

  it("?cotacoes-iframe=1 vence e não liga nativa", () => {
    vi.stubGlobal("window", { location: { search: "?cotacoes-iframe=1", hash: "#/cotacoes" } });
    expect(iframeCotacoes()).toBe(true);
    expect(nativaLigada()).toBe(false);
  });

  it("hash #/nova e #/conexoes ligam nativa", () => {
    vi.stubGlobal("window", { location: { search: "", hash: "#/nova" } });
    expect(nativaLigada()).toBe(true);
    vi.stubGlobal("window", { location: { search: "", hash: "#/conexoes?op=sulamerica" } });
    expect(nativaLigada()).toBe(true);
  });
});
