import { describe, expect, it } from "vitest";
import { RPA_URL_PADRAO } from "../rpaClient";

/**
 * Ponta a ponta leve contra o robô em modo simulador, se estiver no ar.
 * Pula se 127.0.0.1:8600 não responder — não sobe a suíte de 68 min.
 */
async function estadoRobo() {
  try {
    const r = await fetch(`${RPA_URL_PADRAO}/api/estado`, { signal: AbortSignal.timeout(1500) });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

describe("e2e robô simulador (opcional)", () => {
  it("GET /api/operadoras devolve campos, planos e faixas de idade exata", async () => {
    const estado = await estadoRobo();
    if (!estado) {
      return;
    }
    const r = await fetch(`${RPA_URL_PADRAO}/api/operadoras`);
    expect(r.ok).toBe(true);
    const ops = await r.json();
    expect(Array.isArray(ops)).toBe(true);
    expect(ops.length).toBeGreaterThan(0);
    const op = ops[0];
    expect(op.campos.length).toBeGreaterThan(0);
    expect(op.planos.length).toBeGreaterThan(0);
    expect(op.min_vidas).toBeGreaterThan(0);
    expect(Array.isArray(op.faixas_idade_exata)).toBe(true);
    const validar = await fetch(`${RPA_URL_PADRAO}/api/validar`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Newport-Tela": "1" },
      body: JSON.stringify({ itens: [] }),
    });
    const v = await validar.json();
    expect(v).toHaveProperty("ok");
    expect(v).toHaveProperty("cotacoes");
  });
});
