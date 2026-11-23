import { afterEach, describe, expect, it, vi } from "vitest";
import { registrarErro } from "./registrarErro";

describe("registrarErro", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("loga rota e componente sem e-mail nem CNPJ", () => {
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    registrarErro(new Error("falhou em 12.345.678/0001-90 e  ana@empresa.com"), {
      rota: "#/conexoes",
      componente: "Conexoes",
    });
    expect(spy).toHaveBeenCalledTimes(1);
    const payload = spy.mock.calls[0][1];
    expect(payload.componente).toBe("Conexoes");
    expect(payload.rota).toBe("#/conexoes");
    expect(payload.mensagem).not.toMatch(/12\.345/);
    expect(payload.mensagem).not.toMatch(/ana@/);
    expect(payload.mensagem).toMatch(/•••/);
  });
});
