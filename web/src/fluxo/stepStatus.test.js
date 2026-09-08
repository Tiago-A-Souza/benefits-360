import { describe, expect, it } from "vitest";
import {
  comparativoConfirmado,
  confirmacaoEmVigor,
  confirmacaoPrecisaRefazer,
} from "./stepStatus.js";

const rascunhoConfirmado = {
  confirmacao_comparativo: {
    hash_comparativo: "abc",
    ordem: ["op-1"],
    confirmado_em: "2026-09-07T23:44:00Z",
    rascunho_fingerprint: "fp",
  },
};

describe("confirmacaoEmVigor / confirmacaoPrecisaRefazer", () => {
  it("não trava o botão enquanto o status de governança não chegou", () => {
    expect(confirmacaoEmVigor(rascunhoConfirmado, null)).toBe(false);
    expect(confirmacaoPrecisaRefazer(rascunhoConfirmado, null)).toBe(true);
    expect(comparativoConfirmado(rascunhoConfirmado)).toBe(true);
  });

  it("desbloqueia quando a aprovação caiu (snapshot superado)", () => {
    expect(
      confirmacaoEmVigor(rascunhoConfirmado, {
        estado: "superado",
        aprovado: false,
        formato_incompativel: false,
      })
    ).toBe(false);
    expect(
      confirmacaoPrecisaRefazer(rascunhoConfirmado, {
        estado: "superado",
        aprovado: false,
        formato_incompativel: false,
      })
    ).toBe(true);
  });

  it("trava só com candidato ou aprovação em vigor", () => {
    expect(
      confirmacaoEmVigor(rascunhoConfirmado, {
        estado: "candidato",
        aprovado: false,
      })
    ).toBe(true);
    expect(
      confirmacaoPrecisaRefazer(rascunhoConfirmado, {
        estado: "candidato",
        aprovado: false,
      })
    ).toBe(false);
    expect(
      confirmacaoEmVigor(rascunhoConfirmado, {
        estado: "aprovado",
        aprovado: true,
      })
    ).toBe(true);
  });

  it("pede reconfirmação se o formato do snapshot é anterior", () => {
    expect(
      confirmacaoEmVigor(rascunhoConfirmado, {
        estado: "aprovado",
        aprovado: true,
        formato_incompativel: true,
      })
    ).toBe(false);
    expect(
      confirmacaoPrecisaRefazer(rascunhoConfirmado, {
        estado: "aprovado",
        aprovado: true,
        formato_incompativel: true,
      })
    ).toBe(true);
  });
});
