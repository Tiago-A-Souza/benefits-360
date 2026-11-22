import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import {
  chamarRpa,
  RpaClienteErro,
  urlBaseRpa,
  RPA_URL_PADRAO,
  opcoesChamadaRpa,
  resumoVersaoRobo,
} from "./rpaClient";

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
    expect(init.targetAddressSpace).toBe("loopback");
  });

  it("opcoesChamadaRpa marca loopback sem apagar o restante", () => {
    const o = opcoesChamadaRpa({ method: "GET", headers: { A: "1" } });
    expect(o.targetAddressSpace).toBe("loopback");
    expect(o.method).toBe("GET");
    expect(o.headers.A).toBe("1");
  });

  it("resumoVersaoRobo avisa se faltar commit e não bloqueia", () => {
    expect(resumoVersaoRobo(null).antigo).toBe(true);
    expect(resumoVersaoRobo({}).antigo).toBe(true);
    expect(resumoVersaoRobo({ codigo: {} }).texto).toMatch(/indisponível/);
    expect(resumoVersaoRobo({ codigo: { commit: "9db3e86" } })).toEqual({
      texto: "Robô 9db3e86",
      antigo: false,
    });
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
