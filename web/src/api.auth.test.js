import { beforeEach, describe, expect, it, vi } from "vitest";

const sessao = vi.hoisted(() => ({
  obterAccessToken: vi.fn(),
  sairSessao: vi.fn(),
  avisarNaoAutorizado: vi.fn(),
}));

vi.mock("./login/sessao.js", () => ({
  obterAccessToken: sessao.obterAccessToken,
  sairSessao: sessao.sairSessao,
  avisarNaoAutorizado: sessao.avisarNaoAutorizado,
}));

import { abrirEntregavelHtml, listarEstudos } from "./api.js";

describe("api.js autenticação", () => {
  beforeEach(() => {
    sessao.obterAccessToken.mockReset();
    sessao.sairSessao.mockReset();
    sessao.avisarNaoAutorizado.mockReset();
    sessao.obterAccessToken.mockResolvedValue("tok-abc");
    sessao.sairSessao.mockResolvedValue(undefined);
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        status: 200,
        json: async () => [],
        text: async () => "[]",
      }))
    );
  });

  it("envia Authorization Bearer", async () => {
    await listarEstudos();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [, opts] = globalThis.fetch.mock.calls[0];
    expect(opts.headers.get("Authorization")).toBe("Bearer tok-abc");
  });

  it("401 dispara saída", async () => {
    globalThis.fetch.mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Faça login para continuar." }),
      text: async () => JSON.stringify({ detail: "Faça login para continuar." }),
    });
    await expect(listarEstudos()).rejects.toThrow(/login/i);
    expect(sessao.sairSessao).toHaveBeenCalled();
    expect(sessao.avisarNaoAutorizado).toHaveBeenCalled();
  });

  it("JSON inválido em 200 vira erro, não quebra o then", async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => {
        throw new SyntaxError("boom");
      },
      text: async () => "<html>não é json</html>",
    });
    await expect(listarEstudos()).rejects.toThrow(/não é JSON/i);
  });

  it("envelope {estudos} vira lista", async () => {
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ estudos: [{ id: "e1" }] }),
      text: async () => JSON.stringify({ estudos: [{ id: "e1" }] }),
    });
    await expect(listarEstudos()).resolves.toEqual([{ id: "e1" }]);
  });

  it("HTML do entregável usa fetch+blob, não <a href>", async () => {
    const blob = new Blob(["<html></html>"], { type: "text/html" });
    globalThis.fetch.mockResolvedValue({
      ok: true,
      status: 200,
      blob: async () => blob,
    });
    const abrir = vi.fn();
    vi.stubGlobal("window", { open: abrir });
    globalThis.URL.createObjectURL = vi.fn(() => "blob:html");
    await abrirEntregavelHtml("est-1", "ent-1");
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/estudos/est-1/entregaveis/ent-1/html",
      expect.any(Object)
    );
    expect(abrir).toHaveBeenCalledWith("blob:html", "_blank", "noopener,noreferrer");
  });
});
