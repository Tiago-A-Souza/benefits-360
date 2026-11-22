import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { chamarRpa, RpaClienteErro, baixarUrlRpa, RPA_URL_PADRAO } from "../rpaClient";

describe("rpaClient — extras da nativa", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("aceitarErro devolve o JSON mesmo com HTTP de erro", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 404,
      headers: { get: () => "application/json" },
      json: async () => ({}),
    });
    const d = await chamarRpa("GET", "/api/empresas/11444777000161", undefined, { aceitarErro: true });
    expect(d).toEqual({});
  });

  it("erro HTTP anexa dados.problemas", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => "application/json" },
      json: async () => ({ erro: "há pedidos com problema", problemas: { X: ["vidas"] } }),
    });
    await expect(chamarRpa("POST", "/api/trabalhos", { modo: "ensaio" })).rejects.toMatchObject({
      codigo: "ROBO_HTTP",
      dados: { problemas: { X: ["vidas"] } },
    });
    await expect(chamarRpa("POST", "/api/trabalhos", {})).rejects.toBeInstanceOf(RpaClienteErro);
  });

  it("POST /api/importar com FormData não manda JSON", async () => {
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ validos: [], erros: [] }),
    });
    const form = new FormData();
    form.append("operadora", "sulamerica");
    form.append("arquivo", new Blob(["PK"], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }), "a.xlsx");
    const r = await chamarRpa("POST", "/api/importar", form);
    expect(r).toEqual({ validos: [], erros: [] });
    const [, init] = fetch.mock.calls[0];
    expect(init.body).toBe(form);
    expect(init.headers["Content-Type"]).toBeUndefined();
    expect(init.headers["X-Newport-Tela"]).toBe("1");
  });

  it("POST escolher-pasta envia X-Newport-Tela", async () => {
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ pasta: "C:\\\\cotacoes" }),
    });
    const r = await chamarRpa("POST", "/api/escolher-pasta");
    expect(r.pasta).toContain("cotacoes");
    expect(fetch.mock.calls[0][1].headers["X-Newport-Tela"]).toBe("1");
  });

  it("baixarUrlRpa dispara download do blob", async () => {
    if (typeof document === "undefined") return;
    const blob = new Blob(["pdf"], { type: "application/pdf" });
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: (h) => (h === "content-disposition" ? 'attachment; filename="x.pdf"' : "") },
      blob: async () => blob,
    });
    const clicked = [];
    const createObjectURL = vi.fn(() => "blob:fake");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });
    const orig = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag) => {
      const el = orig(tag);
      if (tag === "a") el.click = () => clicked.push(el.download);
      return el;
    });
    await baixarUrlRpa("/api/cotacoes/1/pdf");
    expect(fetch).toHaveBeenCalledWith(
      `${RPA_URL_PADRAO}/api/cotacoes/1/pdf`,
      expect.objectContaining({ targetAddressSpace: "loopback" }),
    );
    expect(clicked[0]).toBe("x.pdf");
  });
});
