import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { chamarRpa, RpaClienteErro, urlBaseRpa, RPA_URL_PADRAO } from "./rpaClient";

describe("rpaClient", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("usa URL padrão sem VITE_RPA_URL", () => {
    expect(urlBaseRpa()).toBe(RPA_URL_PADRAO);
  });

  it("GET estado feliz", async () => {
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ simulador: true }),
    });
    const d = await chamarRpa("GET", "/api/estado");
    expect(d.simulador).toBe(true);
    expect(fetch).toHaveBeenCalledWith(
      `${RPA_URL_PADRAO}/api/estado`,
      expect.objectContaining({ method: "GET" }),
    );
    const init = fetch.mock.calls[0][1];
    expect(init.headers["X-Newport-Tela"]).toBeUndefined();
  });

  it("mutação envia X-Newport-Tela", async () => {
    fetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => "application/json" },
      json: async () => ({ ok: true }),
    });
    await chamarRpa("POST", "/api/validar", { itens: [] });
    const init = fetch.mock.calls[0][1];
    expect(init.headers["X-Newport-Tela"]).toBe("1");
    expect(init.headers["Content-Type"]).toBe("application/json");
  });

  it("rede caída → ROBO_DESLIGADO", async () => {
    fetch.mockRejectedValue(new TypeError("Failed to fetch"));
    await expect(chamarRpa("GET", "/api/estado")).rejects.toMatchObject({
      codigo: "ROBO_DESLIGADO",
    });
    await expect(chamarRpa("GET", "/api/estado")).rejects.toBeInstanceOf(RpaClienteErro);
  });
});
