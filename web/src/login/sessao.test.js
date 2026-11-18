import { beforeEach, describe, expect, it, vi } from "vitest";

const auth = vi.hoisted(() => ({
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signOut: vi.fn(),
  resetPasswordForEmail: vi.fn(),
  getSession: vi.fn(),
  onAuthStateChange: vi.fn(() => ({
    data: { subscription: { unsubscribe: vi.fn() } },
  })),
}));

vi.mock("./supabase.js", () => ({
  supabaseConfigurado: () => true,
  obterCliente: () => ({ auth }),
}));

import { criarConta, entrar, obterAccessToken } from "./sessao.js";

describe("sessao.js com Supabase simulado", () => {
  beforeEach(() => {
    auth.signInWithPassword.mockReset();
    auth.signUp.mockReset();
    auth.signOut.mockReset();
    auth.signOut.mockResolvedValue({ error: null });
  });

  it("login ok", async () => {
    auth.signInWithPassword.mockResolvedValue({
      data: {
        session: { user: { email_confirmed_at: "2026-01-01T00:00:00Z" } },
        user: { email_confirmed_at: "2026-01-01T00:00:00Z" },
      },
      error: null,
    });
    const r = await entrar("corretor@corretora.com.br", "senha1234");
    expect(r.ok).toBe(true);
    expect(auth.signInWithPassword).toHaveBeenCalledWith({
      email: "corretor@corretora.com.br",
      password: "senha1234",
    });
  });

  it("login com erro", async () => {
    auth.signInWithPassword.mockResolvedValue({
      data: { session: null, user: null },
      error: { message: "Invalid login credentials", code: "invalid_credentials" },
    });
    const r = await entrar("corretor@corretora.com.br", "errada");
    expect(r.ok).toBe(false);
    expect(r.erro).toBe("E-mail ou senha incorretos.");
  });

  it("e-mail não confirmado falha com mensagem clara", async () => {
    auth.signInWithPassword.mockResolvedValue({
      data: { session: null, user: null },
      error: { message: "Email not confirmed", code: "email_not_confirmed" },
    });
    const r = await entrar("corretor@corretora.com.br", "senha1234");
    expect(r.ok).toBe(false);
    expect(r.erro).toBe("Confirme o e-mail antes de entrar.");
  });

  it("obterAccessToken devolve o JWT da sessão", async () => {
    auth.getSession.mockResolvedValue({
      data: { session: { access_token: "jwt-de-teste" } },
    });
    await expect(obterAccessToken()).resolves.toBe("jwt-de-teste");
  });

  it("criar conta", async () => {
    auth.signUp.mockResolvedValue({
      data: {
        user: { id: "u1", identities: [{ id: "i1" }] },
        session: null,
      },
      error: null,
    });
    const r = await criarConta("novo@corretora.com.br", "senha1234", "senha1234");
    expect(r.ok).toBe(true);
    expect(r.aviso).toBe(
      "Enviamos um e-mail de confirmação. Confirme e depois faça login."
    );
    expect(auth.signUp).toHaveBeenCalled();
  });
});
