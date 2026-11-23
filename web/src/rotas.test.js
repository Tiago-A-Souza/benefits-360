import { afterEach, describe, expect, it, vi } from "vitest";
import {
  HASH_ESTUDOS,
  HASH_SIMULAR,
  ehErroSemAcesso,
  ehHashCotacoes,
  hashEstudo,
  irPara,
  parseHash,
} from "./rotas";

describe("parseHash", () => {
  it("vazio e #/ são Meus estudos", () => {
    expect(parseHash("")).toEqual({ area: "estudos" });
    expect(parseHash("#")).toEqual({ area: "estudos" });
    expect(parseHash("#/")).toEqual({ area: "estudos" });
    expect(parseHash(HASH_ESTUDOS)).toEqual({ area: "estudos" });
  });

  it("query cotacoes-nativa só vale com hash vazio", () => {
    expect(parseHash("", "?cotacoes-nativa=1")).toEqual({ area: "cotacoes" });
    expect(parseHash(HASH_ESTUDOS, "?cotacoes-nativa=1")).toEqual({ area: "estudos" });
    expect(parseHash("#/simular-rede", "?cotacoes-nativa=1")).toEqual({ area: "simular" });
  });

  it("Simular rede", () => {
    expect(parseHash(HASH_SIMULAR)).toEqual({ area: "simular" });
  });

  it("estudo com id e etapa", () => {
    expect(parseHash("#/estudos/42/etapa/3")).toEqual({
      area: "estudo",
      estudoId: "42",
      passo: 3,
    });
    expect(parseHash("#/estudos/est-6ec6d7945a/etapa/1")).toEqual({
      area: "estudo",
      estudoId: "est-6ec6d7945a",
      passo: 1,
    });
    expect(parseHash("#/estudos/demo-1")).toEqual({
      area: "estudo",
      estudoId: "demo-1",
      passo: 1,
    });
  });

  it("etapa inválida ou endereço desconhecido", () => {
    expect(parseHash("#/estudos/42/etapa/0").area).toBe("invalida");
    expect(parseHash("#/estudos/42/etapa/abc").area).toBe("invalida");
    expect(parseHash("#/estudos/42/foo").area).toBe("invalida");
    expect(parseHash("#/banana").area).toBe("invalida");
    expect(parseHash("#/conexoes-antiga").area).toBe("invalida");
  });

  it("abas de Cotações (incluindo query no hash do robô)", () => {
    for (const h of [
      "#/inicio",
      "#/nova",
      "#/nova?cnpj=123",
      "#/cotacoes",
      "#/importar",
      "#/conexoes",
      "#/conexoes?op=sulamerica",
      "#/robos",
      "#/robo/amil",
      "#/andamento/12",
      "#/ajuda",
    ]) {
      expect(parseHash(h), h).toEqual({ area: "cotacoes" });
      expect(ehHashCotacoes(h), h).toBe(true);
    }
    expect(ehHashCotacoes("#/estudos")).toBe(false);
    expect(ehHashCotacoes("#/estudos/42/etapa/3")).toBe(false);
    expect(ehHashCotacoes("#/simular-rede")).toBe(false);
  });
});

describe("hashEstudo", () => {
  it("monta #/estudos/:id/etapa/:n", () => {
    expect(hashEstudo("42", 3)).toBe("#/estudos/42/etapa/3");
    expect(hashEstudo("demo-1", 1)).toBe("#/estudos/demo-1/etapa/1");
  });
});

describe("ehErroSemAcesso", () => {
  it("404 e 403 são o mesmo aviso (sem vazar se existe)", () => {
    expect(ehErroSemAcesso({ status: 404 })).toBe(true);
    expect(ehErroSemAcesso({ status: 403 })).toBe(true);
    expect(ehErroSemAcesso({ status: 500 })).toBe(false);
    expect(ehErroSemAcesso(null)).toBe(false);
  });
});

describe("irPara", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("empilha o hash quando o endereço muda", () => {
    const loc = { href: "http://127.0.0.1:4173/#/conexoes", hash: "#/conexoes" };
    Object.defineProperty(loc, "hash", {
      writable: true,
      value: "#/conexoes",
    });
    vi.stubGlobal("window", {
      location: loc,
      history: { replaceState: vi.fn() },
      dispatchEvent: vi.fn(),
    });
    irPara("#/estudos");
    expect(loc.hash).toBe("#/estudos");
  });
});
