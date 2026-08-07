import { describe, expect, it } from "vitest";
import { buildPrefillManualFromExtracao } from "./prefillManual.js";

describe("buildPrefillManualFromExtracao", () => {
  it("herda operadora e documento_id sem inventar tarifas", () => {
    const detalhe = {
      id: "ext-sul",
      estado: "ocr_parcial",
      numero_cotacao: { texto: "12345" },
      validade_oficial: { data: "2026-12-31" },
      alertas: [{ codigo: "PDF-SUL-001" }],
      opcoes: [],
    };
    const doc = {
      id: "doc-sul-1",
      operadora_detectada: "SulAmérica",
      template_id: "sulamerica-pme-sem-cp-13",
      nome_arquivo: "SulAmerica.pdf",
    };

    const prefill = buildPrefillManualFromExtracao(detalhe, doc);

    expect(prefill.operadora).toBe("SulAmérica");
    expect(prefill.documento_cotacao_id).toBe("doc-sul-1");
    expect(prefill.validade_oficial).toBe("2026-12-31");
    expect(prefill.extracao_id).toBe("ext-sul");
    expect(prefill.plano_nome).toBe("");
    expect(prefill.observacoes).toContain("sulamerica-pme-sem-cp-13");
  });
});
