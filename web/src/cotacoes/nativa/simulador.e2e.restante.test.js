import { describe, expect, it } from "vitest";
import { RPA_URL_PADRAO } from "../rpaClient";

/**
 * Leituras contra o robô em :8600. Sem gravar, sem ler senha, sem apagar credencial.
 * Pula se o robô não estiver no ar ou não for simulador.
 */
async function get(caminho) {
  const r = await fetch(`${RPA_URL_PADRAO}${caminho}`, { signal: AbortSignal.timeout(5000) });
  const tipo = r.headers.get("content-type") || "";
  const dados = tipo.includes("application/json") ? await r.json().catch(() => null) : await r.arrayBuffer();
  return { ok: r.ok, status: r.status, dados, tipo };
}

async function estadoRobo() {
  try {
    const r = await fetch(`${RPA_URL_PADRAO}/api/estado`, { signal: AbortSignal.timeout(2000) });
    if (!r.ok) return null;
    return r.json();
  } catch {
    return null;
  }
}

describe("e2e restante (só GET, sem cofre)", () => {
  it(
    "modelo xlsx, geral e esquema do robô",
    { timeout: 20_000 },
    async ({ skip }) => {
      const estado = await estadoRobo();
      if (!estado) {
        skip("robô não está no ar em 127.0.0.1:8600");
        return;
      }
      if (!estado.simulador) {
        skip("robô em :8600 não está em modo simulador");
        return;
      }

      const modelo = await get("/api/modelo/sulamerica");
      expect(modelo.ok, "GET /api/modelo/sulamerica").toBe(true);
      const bytes = new Uint8Array(modelo.dados);
      expect(bytes[0]).toBe(0x50);
      expect(bytes[1]).toBe(0x4b);

      const geral = await get("/api/geral");
      expect(geral.ok).toBe(true);
      expect(geral.dados.pasta_saida).toBeTruthy();
      expect(geral.dados.geral).toBeTruthy();
      expect("mapear" in geral.dados.geral).toBe(true);
      expect("modo_visual" in geral.dados.geral).toBe(true);

      const robo = await get("/api/robos/sulamerica");
      expect(robo.ok).toBe(true);
      expect(robo.dados.telas.length).toBeGreaterThan(0);
      const tipos = robo.dados.telas.flatMap((t) => (t.campos || []).map((c) => c.tipo));
      expect(tipos).toContain("credenciais");
      expect(tipos).toContain("escolha");
    },
  );
});
