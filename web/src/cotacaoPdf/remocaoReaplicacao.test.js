import { describe, expect, it } from "vitest";
import { textoConfirmacaoRemocao, textoRelatoRemocao } from "./utils.js";

const IMPACTO_COMPLETO = {
  planos_removidos: ["Plano A", "Plano B"],
  atribuicoes_desfeitas: [
    {
      cenario_id: "cen-1",
      cenario_rotulo: "Plano A + Plano B",
      alvo_id: "sg-1",
      alvo_rotulo: "AMIL S750 - Apto.",
      plano: "Plano A",
    },
    {
      cenario_id: "cen-1",
      cenario_rotulo: "Plano A + Plano B",
      alvo_id: "sg-2",
      alvo_rotulo: "AMIL ONE S2500 - Apto.",
      plano: "Plano B",
    },
  ],
  cenarios_incompletos: [
    {
      cenario_id: "cen-1",
      cenario_rotulo: "Plano A + Plano B",
      alvos_sem_atribuicao: ["AMIL S750 - Apto.", "AMIL ONE S2500 - Apto."],
      ficou_vazio: true,
    },
  ],
};

describe("textoConfirmacaoRemocao", () => {
  it("nomeia cada plano que sai e cada atribuição desfeita", () => {
    const texto = textoConfirmacaoRemocao(IMPACTO_COMPLETO);
    expect(texto).toContain("remove 2 planos do comparativo");
    expect(texto).toContain("• Plano A");
    expect(texto).toContain("• Plano B");
    expect(texto).toContain("Isso desfaz 2 atribuições em «Plano A + Plano B»");
    expect(texto).toContain("• AMIL S750 - Apto. → Plano A");
    expect(texto).toContain("• AMIL ONE S2500 - Apto. → Plano B");
    expect(texto).toContain("Continuar?");
  });

  it("diz que o cenário fica sem nenhum plano quando esvazia", () => {
    const texto = textoConfirmacaoRemocao(IMPACTO_COMPLETO);
    expect(texto).toContain(
      "O cenário «Plano A + Plano B» fica sem nenhum plano atribuído"
    );
  });

  it("lista os grupos órfãos quando o cenário só fica incompleto", () => {
    const texto = textoConfirmacaoRemocao({
      planos_removidos: ["Plano A"],
      atribuicoes_desfeitas: [
        {
          cenario_id: "cen-1",
          cenario_rotulo: "Plano A + Plano B",
          alvo_id: "sg-1",
          alvo_rotulo: "AMIL S750 - Apto.",
          plano: "Plano A",
        },
      ],
      cenarios_incompletos: [
        {
          cenario_id: "cen-1",
          cenario_rotulo: "Plano A + Plano B",
          alvos_sem_atribuicao: ["AMIL S750 - Apto."],
          ficou_vazio: false,
        },
      ],
    });
    expect(texto).toContain("remove 1 plano do comparativo");
    expect(texto).toContain("Isso desfaz 1 atribuição em «Plano A + Plano B»");
    expect(texto).toContain("fica incompleto: AMIL S750 - Apto. fica sem plano atribuído");
  });

  it("não fala de cenário quando a remoção não toca a etapa 4", () => {
    const texto = textoConfirmacaoRemocao({
      planos_removidos: ["Plano C"],
      atribuicoes_desfeitas: [],
      cenarios_incompletos: [],
    });
    expect(texto).toContain("remove 1 plano do comparativo");
    expect(texto).not.toContain("cenário");
    expect(texto).not.toContain("atribuiç");
  });

  it("é vazio quando não há remoção — nada de diálogo à toa", () => {
    expect(textoConfirmacaoRemocao({ planos_removidos: [] })).toBe("");
    expect(textoConfirmacaoRemocao(null)).toBe("");
  });
});

describe("textoRelatoRemocao", () => {
  it("relata planos e atribuições desfeitas", () => {
    const texto = textoRelatoRemocao(IMPACTO_COMPLETO);
    expect(texto).toBe(
      "2 planos saíram do comparativo: Plano A, Plano B. " +
        "2 atribuições foram desfeitas em «Plano A + Plano B»."
    );
  });

  it("no singular, sem mencionar cenário quando não houve atribuição perdida", () => {
    const texto = textoRelatoRemocao({
      planos_removidos: ["Plano C"],
      atribuicoes_desfeitas: [],
    });
    expect(texto).toBe("1 plano saiu do comparativo: Plano C.");
  });

  it("é vazio sem remoção", () => {
    expect(textoRelatoRemocao({ planos_removidos: [] })).toBe("");
  });
});
