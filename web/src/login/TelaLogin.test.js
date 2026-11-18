import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("./supabase", () => ({
  supabaseConfigurado: () => false,
  obterCliente: () => null,
  urlSupabase: () => "",
}));

import {
  CHAVE_SESSAO,
  entrar,
  mensagemCamposCriarConta,
  mensagemCamposLogin,
  sairSessao,
  sessaoAtiva,
} from "./sessao";

describe("Tela de login (modo demonstração, sem Supabase)", () => {
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
    expect(mensagemCamposCriarConta("a@b.com", "curta", "curta")).toBe(
      "A senha deve ter pelo menos 8 caracteres."
    );
    expect(mensagemCamposCriarConta("a@b.com", "senha1234", "outra")).toBe(
      "As senhas não coincidem."
    );
    expect(sessaoAtiva()).toBe(false);
  });

  it("preenchidos entram", async () => {
    expect(mensagemCamposLogin("corretor@corretora.com.br", "segredo")).toBe("");
    const r = await entrar("corretor@corretora.com.br", "segredo");
    expect(r.ok).toBe(true);
    expect(sessaoAtiva()).toBe(true);
    expect(store[CHAVE_SESSAO]).toBe("1");
    await sairSessao();
    expect(sessaoAtiva()).toBe(false);
  });
});
