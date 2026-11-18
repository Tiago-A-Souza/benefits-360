import { describe, expect, it } from "vitest";
import { OPERADORAS } from "./fixtureOperadoras";
import {
  carregarRascunho,
  diferencasDoPadrao,
  fraseExemploPdf,
  hashNativa,
  itensDoImport,
  linhaErroImport,
  mudancasConfig,
  nomeExemploPdf,
  passosAjuda,
  perguntasAjuda,
  problemaArquivoImportar,
  resumoImportacao,
  saudacao,
  textoDoValor,
  textoPlanosImport,
  valoresParaSalvar,
  visivelConfig,
} from "./regrasRestante";

describe("saudacao e hashes", () => {
  it("divide o dia em três", () => {
    expect(saudacao(new Date("2026-11-17T08:00:00"))).toBe("Bom dia");
    expect(saudacao(new Date("2026-11-17T15:00:00"))).toBe("Boa tarde");
    expect(saudacao(new Date("2026-11-17T20:00:00"))).toBe("Boa noite");
  });

  it("reconhece hashes das telas restantes", () => {
    expect(hashNativa("#/inicio")).toBe(true);
    expect(hashNativa("#/ajuda")).toBe(true);
    expect(hashNativa("#/importar")).toBe(true);
    expect(hashNativa("#/robos")).toBe(true);
    expect(hashNativa("#/robo/sulamerica")).toBe(true);
    expect(hashNativa("#/estudos")).toBe(false);
  });
});

describe("importar", () => {
  it("só aceita .xlsx (sem teto de MB inventado)", () => {
    expect(problemaArquivoImportar({ name: "a.csv" })).toMatch(/xlsx/);
    expect(problemaArquivoImportar({ name: "pedidos.XLSX" })).toBe(null);
    expect(problemaArquivoImportar({ name: "pedidos.xlsx", size: 50 * 1024 * 1024 })).toBe(null);
  });

  it("resume válidos, erros e itens do POST /api/trabalhos", () => {
    const r = {
      validos: [
        { linha: 2, id: "Padaria", cnpj: "11444777000161", vidas: 3, cotacoes: 2, dados: { planos: "menor_preco:2" } },
      ],
      erros: [{ linha: 3, id: "L3", problemas: ["CNPJ inválido"] }],
    };
    const s = resumoImportacao(r);
    expect(s.n).toBe(2);
    expect(s.resumo).toContain("1 empresa pronta");
    expect(s.resumo).toContain("1 linha com problema");
    expect(linhaErroImport(r.erros[0])).toBe("Linha 3: CNPJ inválido");
    expect(textoPlanosImport("menor_preco:2")).toBe("os 2 mais baratos");
    expect(itensDoImport("sulamerica", r.validos)).toEqual([
      { operadora: "sulamerica", pedidos: [r.validos[0].dados] },
    ]);
  });
});

describe("ajuda", () => {
  it("usa texto da operadora na vaga e retencao_dias", () => {
    const ops = [
      {
        ...OPERADORAS[0],
        textos: {
          passo_login: "Guarde o CPF da SulAmérica.",
          perguntas: { pdfs: ["Onde ficam os PDFs?", "Cópia SULAMERICA <PLANO>.pdf."] },
        },
      },
    ];
    const passos = passosAjuda(ops);
    expect(passos[0][1]).toBe("Guarde o CPF da SulAmérica.");
    const qs = perguntasAjuda(ops, 45);
    expect(qs.some((p) => p[1].includes("45 dias"))).toBe(true);
    expect(qs.some((p) => p[1].includes("SULAMERICA"))).toBe(true);
  });
});

describe("configuração do robô", () => {
  const telas = [
    {
      etapa: "planos",
      campos: [
        {
          chave: "padroes.planos_modo",
          tipo: "escolha",
          valor: "lista",
          padrao: "lista",
          opcoes: [
            ["lista", "Escolher na lista"],
            ["menor_preco", "Os mais baratos"],
          ],
        },
        {
          chave: "padroes.planos",
          tipo: "planos",
          valor: ["Especial Mais | Apartamento"],
          padrao: ["Especial Mais | Apartamento"],
          visivel_se: { "padroes.planos_modo": "lista" },
        },
        {
          chave: "criterio_plano.quantidade",
          tipo: "numero",
          valor: 1,
          padrao: 1,
          visivel_se: { "padroes.planos_modo": "menor_preco" },
        },
      ],
    },
  ];

  it("detecta mudanças, visivel_se e payload PUT", () => {
    const { campos, rascunho, pares } = carregarRascunho(telas);
    expect(mudancasConfig(campos, rascunho, pares)).toEqual([]);
    rascunho["padroes.planos_modo"] = "menor_preco";
    expect(visivelConfig(campos["padroes.planos"], campos, rascunho, pares)).toBe(false);
    expect(visivelConfig(campos["criterio_plano.quantidade"], campos, rascunho, pares)).toBe(true);
    expect(valoresParaSalvar(campos, rascunho, pares)).toEqual({ "padroes.planos_modo": "menor_preco" });
    expect(diferencasDoPadrao(campos, rascunho, pares)).toContain("padroes.planos_modo");
  });

  it("exemplo de PDF e texto do valor", () => {
    const ex = { plano: "Especial Mais", versoes: ["COM COPARTICIPACAO"] };
    expect(nomeExemploPdf("SULAMERICA {plano_arquivo}.pdf", "", ex)).toBe("SULAMERICA ESPECIAL MAIS.pdf");
    expect(fraseExemploPdf("SULAMERICA {plano_arquivo}.pdf", ex)).toContain("COM COPARTICIPACAO");
    expect(textoDoValor({ tipo: "sim_nao" }, "nao")).toBe("não");
    expect(textoDoValor({ tipo: "escolha", opcoes: [["lista", "Escolher na lista"]] }, "lista")).toBe(
      "Escolher na lista",
    );
  });
});
