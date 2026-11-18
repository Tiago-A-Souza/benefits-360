import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  CHAVE_SESSAO,
  entrarDemo,
  mensagemCamposLogin,
  sairSessao,
  sessaoAtiva,
} from "./sessao";

describe("Tela de login (fase 2, demonstração)", () => {
  let store;

  beforeEach(() => {
    store = {};
    vi.stubGlobal("sessionStorage", {
      getItem: (k) => (k in store ? store[k] : null),
      setItem: (k, v) => {
        store[k] = String(v);
      },
      removeItem: (k) => {
        delete store[k];
      },
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("campos vazios mostram erro", () => {
    expect(mensagemCamposLogin("", "")).toBe("Informe o e-mail e a senha.");
    expect(mensagemCamposLogin("  ", "")).toBe("Informe o e-mail e a senha.");
    expect(sessaoAtiva()).toBe(false);
  });

  it("preenchidos entram", () => {
    expect(mensagemCamposLogin("corretor@corretora.com.br", "segredo")).toBe("");
    entrarDemo();
    expect(sessaoAtiva()).toBe(true);
    expect(store[CHAVE_SESSAO]).toBe("1");
    sairSessao();
    expect(sessaoAtiva()).toBe(false);
  });
});
