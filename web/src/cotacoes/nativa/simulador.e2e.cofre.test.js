import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const e2e = readFileSync(join(dirname(fileURLToPath(import.meta.url)), "simulador.e2e.test.js"), "utf8");

describe("e2e não toca o cofre Windows NewportCotacoes/<op>", () => {
  it("não chama a API de credenciais nem manda senha de treino", () => {
    expect(e2e).not.toMatch(/["'`]\/api\/credenciais/);
    expect(e2e).not.toMatch(/\bLOGIN_TREINO\b/);
    expect(e2e).not.toMatch(/Treino#Falsa/);
  });

  it("só segue em modo simulador (cofre de memória do processo, não keyring)", () => {
    expect(e2e).toMatch(/estado\.simulador/);
    expect(e2e).toMatch(/este teste não grava credencial/);
  });
});
