import { describe, expect, it } from "vitest";
import { RPA_URL_PADRAO } from "../rpaClient";
import { CNPJ_OK } from "./fixtureOperadoras";
import { estadoInicial, montarItens, problemasLocais } from "./regrasNova";

/**
 * Ponta a ponta contra o robô em modo simulador (HTTP real em :8600, sem mock).
 * Exige `estado.simulador === true`. Pula se o robô não estiver no ar.
 * Login de treino do simulador SulAmérica (não é PII).
 */
const LOGIN_TREINO = {
  cpf: "52998224725",
  email: "corretor.treino@simulador.local",
  senha: "Treino#Falsa-26",
};

async function json(metodo, caminho, corpo) {
  const init = { method: metodo, headers: {} };
  if (metodo !== "GET") init.headers["X-Newport-Tela"] = "1";
  if (corpo !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(corpo);
  }
  const r = await fetch(`${RPA_URL_PADRAO}${caminho}`, init);
  const dados = await r.json().catch(() => null);
  return { ok: r.ok, status: r.status, dados };
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

describe("e2e robô simulador (HTTP real)", () => {
  it(
    "validar → enfileirar ensaio → esperar terminar → conferir resultado",
    { timeout: 480_000 },
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

      const ops = (await json("GET", "/api/operadoras")).dados;
      const sul = (ops || []).find((o) => o.id === "sulamerica");
      expect(sul, "SulAmérica precisa estar ativa no robô").toBeTruthy();

      const login = await json("POST", "/api/credenciais/sulamerica", LOGIN_TREINO);
      expect(login.ok, JSON.stringify(login.dados)).toBe(true);

      const form = estadoInicial(ops);
      form.cnpj = CNPJ_OK;
      form.apelido = "E2E nativa";
      form.vidas["29_33"] = 3;
      for (const id of Object.keys(form.ops)) form.ops[id].ativa = id === "sulamerica";
      form.ops.sulamerica.campos.congenere_atual = "NOTREDAME";
      if ("coparticipacao" in form.ops.sulamerica.campos) form.ops.sulamerica.campos.coparticipacao = "com";
      const especial = (sul.planos || []).find((p) => p.nome === "Especial Mais" && p.acomodacao === "Apartamento")
        || (sul.planos || [])[0];
      expect(especial, "catálogo da SulAmérica veio vazio").toBeTruthy();
      form.ops.sulamerica.menor = false;
      form.ops.sulamerica.planos = [`${especial.nome} | ${especial.acomodacao}`];
      expect(problemasLocais(form, ops)).toEqual([]);
      const itens = montarItens(form, ops);
      expect(itens).toHaveLength(1);

      const validar = await json("POST", "/api/validar", { itens });
      expect(validar.ok, JSON.stringify(validar.dados)).toBe(true);
      expect(validar.dados.ok).toBe(true);
      expect(validar.dados.cotacoes).toBeGreaterThan(0);

      const criado = await json("POST", "/api/trabalhos", { modo: "ensaio", itens });
      expect(criado.ok, JSON.stringify(criado.dados)).toBe(true);
      expect(criado.dados.id).toBeGreaterThan(0);
      const tid = criado.dados.id;

      const limite = Date.now() + 420_000;
      let t;
      while (Date.now() < limite) {
        const r = await json("GET", `/api/trabalhos/${tid}`);
        expect(r.ok).toBe(true);
        t = r.dados;
        if (!["na_fila", "rodando"].includes(t.status)) break;
        await new Promise((res) => setTimeout(res, 1000));
      }
      expect(["na_fila", "rodando"].includes(t.status)).toBe(false);
      expect(t.status).toBe("concluido");
      expect(t.cotacoes.length).toBeGreaterThan(0);
      expect(t.cotacoes.some((c) => c.status === "ENSAIO_OK")).toBe(true);
      const comValor = t.cotacoes.find((c) => c.total_com_iof != null);
      if (comValor) {
        expect(typeof comValor.total_com_iof).toBe("number");
        expect(Number.isFinite(comValor.total_com_iof)).toBe(true);
      }
      expect(itens[0].pedidos[0].cnpj.replace(/\D/g, "")).toBe(CNPJ_OK);
    },
  );
});
