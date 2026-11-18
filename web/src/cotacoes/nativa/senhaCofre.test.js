import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chamarRpa, ocultarSegredosNoTexto, RPA_URL_PADRAO } from "../rpaClient";
import { corpoLoginParaRobo, limparSenhas } from "./regrasConexao";

const SENHA = "Treino#Falsa-26";
const CAMPOS = [
  { chave: "cpf", tipo: "cpf" },
  { chave: "email", tipo: "email" },
  { chave: "senha", tipo: "senha" },
];

describe("senha só na requisição ao robô local", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
    vi.stubGlobal("localStorage", {
      setItem: vi.fn(),
      getItem: vi.fn(),
      removeItem: vi.fn(),
    });
    vi.spyOn(console, "log").mockImplementation(() => {});
    vi.spyOn(console, "info").mockImplementation(() => {});
    vi.spyOn(console, "debug").mockImplementation(() => {});
    vi.spyOn(console, "error").mockImplementation(() => {});
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("POST vai só para 127.0.0.1:8600; senha no body; estado limpo; nada em storage/log/erro", async () => {
    fetch.mockResolvedValue({
      ok: false,
      status: 400,
      headers: { get: () => "application/json" },
      json: async () => ({ erro: `recusou ${SENHA}` }),
    });
    const valores = { cpf: "52998224725", email: "corretor.treino@simulador.local", senha: SENHA };
    const corpo = corpoLoginParaRobo(CAMPOS, valores);
    await expect(chamarRpa("POST", "/api/credenciais/sulamerica", corpo)).rejects.toMatchObject({
      message: expect.not.stringContaining(SENHA),
    });
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe(`${RPA_URL_PADRAO}/api/credenciais/sulamerica`);
    expect(url).toMatch(/^http:\/\/127\.0\.0\.1:8600\//);
    expect(JSON.parse(init.body).senha).toBe(SENHA);
    expect(limparSenhas(valores, CAMPOS).senha).toBe("");
    expect(localStorage.setItem).not.toHaveBeenCalled();
    const logs = [console.log, console.info, console.debug, console.error, console.warn]
      .map((fn) => fn.mock.calls.flat().join(" "))
      .join(" ");
    expect(logs).not.toContain(SENHA);
    expect(ocultarSegredosNoTexto(`falhou ${SENHA}`, corpo)).toBe("falhou •••");
  });

  it("CartaoLogin e cliente não gravam senha em URL, localStorage ou log", () => {
    const dir = dirname(fileURLToPath(import.meta.url));
    const login = readFileSync(join(dir, "CartaoLogin.jsx"), "utf8");
    const client = readFileSync(join(dir, "..", "rpaClient.js"), "utf8");
    expect(login).toContain('type={tipo}');
    expect(login).toContain('autoComplete={c.tipo === "senha" ? "new-password" : "off"}');
    expect(login).toContain("valoresLoginVazios(campos)");
    expect(login).not.toContain("localStorage");
    expect(login).not.toContain("searchParams");
    expect(client).toContain("ocultarSegredosNoTexto");
    expect(client).not.toContain("localStorage");
  });
});
