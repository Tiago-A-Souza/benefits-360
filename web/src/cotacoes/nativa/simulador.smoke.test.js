import { describe, expect, it } from "vitest";
import { RPA_URL_PADRAO } from "../rpaClient";

/**
 * Fumaça contra o robô real em 127.0.0.1:8600 (HTTP de verdade, sem mock).
 * Não cria trabalho. Se o robô estiver desligado, o caso é skip — não falha a suíte.
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

describe("fumaça HTTP no robô (8600, sem mock)", () => {
  it("GET /api/operadoras e POST /api/validar (itens vazios)", async ({ skip }) => {
    const estado = await estadoRobo();
    if (!estado) {
      skip("robô não está no ar em 127.0.0.1:8600");
      return;
    }
    const r = await fetch(`${RPA_URL_PADRAO}/api/operadoras`);
    expect(r.ok).toBe(true);
    const ops = await r.json();
    expect(ops.length).toBeGreaterThan(0);
    expect(ops[0].campos.length).toBeGreaterThan(0);
    const validar = await fetch(`${RPA_URL_PADRAO}/api/validar`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Newport-Tela": "1" },
      body: JSON.stringify({ itens: [] }),
    });
    const v = await validar.json();
    expect(v).toHaveProperty("ok");
    expect(v).toHaveProperty("cotacoes");
    const lista = await fetch(`${RPA_URL_PADRAO}/api/cotacoes?status=OK`);
    expect(lista.ok).toBe(true);
    expect(Array.isArray(await lista.json())).toBe(true);
    const pend = await fetch(`${RPA_URL_PADRAO}/api/pendencias`);
    expect(pend.ok).toBe(true);
  });
});
