import { describe, expect, it } from "vitest";
import { CNPJ_OK, OPERADORAS } from "./fixtureOperadoras";
import {
  aplicarDados,
  cnpjValido,
  cotacoesDe,
  estadoInicial,
  formatarCnpj,
  formatarValorRobo,
  fluxoConfirmacao,
  montarItens,
  problemasLocais,
  resumoDoRobo,
  totalVidas,
} from "./regrasNova";

describe("regrasNova — CNPJ e vidas", () => {
  it("valida CNPJ com dígitos verificadores", () => {
    expect(cnpjValido(CNPJ_OK)).toBe(true);
    expect(cnpjValido("11.444.777/0001-61")).toBe(true);
    expect(cnpjValido("00000000000000")).toBe(false);
    expect(cnpjValido("11444777000160")).toBe(false);
  });

  it("formata CNPJ", () => {
    expect(formatarCnpj(CNPJ_OK)).toBe("11.444.777/0001-61");
  });
});

describe("regrasNova — formulário a partir da API", () => {
  it("estado inicial usa planos, modo e campos da operadora", () => {
    const f = estadoInicial(OPERADORAS);
    const o = f.ops.sulamerica;
    expect(o.ativa).toBe(true);
    expect(o.campos.coparticipacao).toBe("as_duas");
    expect(o.campos.cuidado_360).toBe("sim");
    expect(o.planos).toEqual(["Especial Mais | Apartamento"]);
    expect(o.menor).toBe(false);
  });

  it("coparticipação as_duas multiplica cotações", () => {
    const f = estadoInicial(OPERADORAS);
    expect(cotacoesDe(f, OPERADORAS[0])).toBe(2);
  });

  it("pede idade exata nas faixas da API e vidas 3–29", () => {
    const f = estadoInicial(OPERADORAS);
    f.cnpj = CNPJ_OK;
    f.vidas["0_18"] = 1;
    expect(problemasLocais(f, OPERADORAS).some((p) => p.includes("idade"))).toBe(true);
    f.idades["0_18"] = "7";
    const p = problemasLocais(f, OPERADORAS);
    expect(p.some((t) => t.includes("3 a 29"))).toBe(true);
    f.vidas["29_33"] = 2;
    f.ops.sulamerica.campos.congenere_atual = "NOTREDAME";
    expect(problemasLocais(f, OPERADORAS)).toEqual([]);
  });

  it("exige operadora atual se não for seguro novo", () => {
    const f = estadoInicial(OPERADORAS);
    f.cnpj = CNPJ_OK;
    f.vidas["29_33"] = 3;
    const p = problemasLocais(f, OPERADORAS);
    expect(p.some((t) => t.includes("operadora atual"))).toBe(true);
    f.ops.sulamerica.campos.congenere_atual = "NOTREDAME";
    expect(problemasLocais(f, OPERADORAS)).toEqual([]);
  });

  it("montarItens envia CNPJ formatado, vidas e planos", () => {
    const f = estadoInicial(OPERADORAS);
    f.cnpj = CNPJ_OK;
    f.apelido = "Padaria";
    f.vidas["0_18"] = 1;
    f.idades["0_18"] = "7";
    f.vidas["29_33"] = 2;
    f.ops.sulamerica.campos.congenere_atual = "NOTREDAME";
    const itens = montarItens(f, OPERADORAS);
    expect(itens).toHaveLength(1);
    expect(itens[0].operadora).toBe("sulamerica");
    expect(itens[0].pedidos[0].cnpj).toBe("11.444.777/0001-61");
    expect(itens[0].pedidos[0].vidas_0_18).toBe(1);
    expect(itens[0].pedidos[0].idades_0_18).toBe("7");
    expect(itens[0].pedidos[0].planos).toBe("Especial Mais | Apartamento");
    expect(itens[0].pedidos[0].coparticipacao).toBe("as_duas");
  });

  it("aplicarDados não sobrescreve campos do robô", () => {
    const f = estadoInicial(OPERADORAS);
    const next = aplicarDados(
      f,
      {
        cnpj: CNPJ_OK,
        apelido: "X",
        coparticipacao: "sem",
        congenere_atual: "AMIL",
        planos: "Direto Nacional | Enfermaria",
      },
      OPERADORAS,
    );
    expect(next.ops.sulamerica.campos.coparticipacao).toBe("as_duas");
    expect(next.ops.sulamerica.campos.congenere_atual).toBe("AMIL");
    expect(next.ops.sulamerica.planos).toEqual(["Direto Nacional | Enfermaria"]);
  });

  it("resumo do robô usa o 3º texto da coparticipação", () => {
    const f = estadoInicial(OPERADORAS);
    const t = resumoDoRobo(OPERADORAS[0], (k) => f.ops.sulamerica.campos[k], { produto: "557 - AHO" });
    expect(t).toContain("Compulsória");
    expect(t).toContain("com e sem coparticipação");
    expect(t).toContain("Cuidado 360");
    expect(t).toContain("557 - AHO");
  });
});

describe("regrasNova — dinheiro", () => {
  it("formata reais do robô sem float", () => {
    expect(formatarValorRobo("1234.56")).toBe("R$\u00a01.234,56");
    expect(formatarValorRobo(100)).toBe("R$\u00a0100,00");
    expect(formatarValorRobo(null)).toBe("—");
  });

  it("formata centavos inteiros sem float", () => {
    expect(formatarValorRobo(123456, { comoCentavos: true })).toBe("R$\u00a01.234,56");
    expect(formatarValorRobo({ centavos: 50 })).toBe("R$\u00a00,50");
  });
});

describe("fluxoConfirmacao — emitir", () => {
  it("ensaio não pede confirmação", async () => {
    const confirmar = async () => {
      throw new Error("não deveria confirmar");
    };
    const r = await fluxoConfirmacao("ensaio", { cotacoes: 2, ja_emitidas: [] }, ["SulAmérica"], confirmar);
    expect(r).toEqual({ reemitir: [] });
  });

  it("emitir pede confirmação humana e aborta se Voltar", async () => {
    const confirmar = async (opts) => {
      expect(opts.titulo).toMatch(/Gerar 2 cotações na SulAmérica/);
      expect(opts.texto[0]).toContain("protocolo de verdade");
      return false;
    };
    const r = await fluxoConfirmacao("emitir", { cotacoes: 2, ja_emitidas: [] }, ["SulAmérica"], confirmar);
    expect(r.abortar).toBe(true);
  });

  it("já emitidas todas: alternativa gera reemitir após 2ª confirmação", async () => {
    const chamadas = [];
    const confirmar = async (opts) => {
      chamadas.push(opts.ok);
      if (chamadas.length === 1) return "alternativa";
      return true;
    };
    const r = await fluxoConfirmacao(
      "emitir",
      {
        cotacoes: 1,
        ja_emitidas: [{ plano: "Especial Mais", protocolo: "ABC123", quando: "2026-01-01T12:00:00" }],
      },
      ["SulAmérica"],
      confirmar,
    );
    expect(chamadas[0]).toBe("Ver em Cotações");
    expect(r.reemitir).toEqual(["ABC123"]);
  });
});

describe("totalVidas", () => {
  it("soma faixas", () => {
    const f = estadoInicial(OPERADORAS);
    f.vidas["0_18"] = 1;
    f.vidas["29_33"] = 2;
    expect(totalVidas(f.vidas)).toBe(3);
  });
});
