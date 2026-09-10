/** FASE 1 — tela de seleção por grupo. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

globalThis.React = React;

import {
  alternarPlano,
  avisoSelecaoVazia,
  exibeSelecaoPorGrupo,
  seloGrupo,
  subtituloGrupo,
  textoContexto,
} from "./selecaoPorGrupo.js";

function grupo(over = {}) {
  return {
    subgrupo_id: "sg-1",
    plano_nome: "AMIL S750 - Apto.",
    quantidade_beneficiarios: 36,
    referencia_reais: "R$ 28.862,01",
    referencia_rotulo: "reajustada",
    selecao_propria: true,
    escolhidos: 3,
    planos: [
      { opcao_id: "op-1", escolhido: true },
      { opcao_id: "op-2", escolhido: false },
      { opcao_id: "op-3", escolhido: true },
    ],
    ...over,
  };
}

describe("visibilidade da tela", () => {
  it("um plano vigente não abre a tela nova", () => {
    expect(exibeSelecaoPorGrupo({ grupos: [grupo()] })).toBe(false);
  });

  it("dois planos vigentes abrem", () => {
    expect(
      exibeSelecaoPorGrupo({ grupos: [grupo(), grupo({ subgrupo_id: "sg-2" })] })
    ).toBe(true);
  });

  it("resposta ausente não quebra", () => {
    expect(exibeSelecaoPorGrupo(null)).toBe(false);
  });
});

describe("aba do grupo", () => {
  it("mostra vidas e valor reajustado, sem papel", () => {
    expect(subtituloGrupo(grupo())).toBe("36 vidas · R$ 28.862,01 reajustado");
  });

  it("uma vida no singular", () => {
    expect(subtituloGrupo(grupo({ quantidade_beneficiarios: 1 }))).toContain("1 vida ·");
  });

  it("selo conta os escolhidos", () => {
    expect(seloGrupo(grupo()).texto).toBe("3 planos escolhidos");
    expect(seloGrupo(grupo({ escolhidos: 1 })).texto).toBe("1 plano escolhido");
  });

  it("grupo sem escolha própria diz que herdou todos", () => {
    const selo = seloGrupo(grupo({ selecao_propria: false, escolhidos: 5 }));
    expect(selo.herdado).toBe(true);
    expect(selo.texto).toBe("5 planos — todos");
  });

  it("escolha própria vazia é sinalizada", () => {
    expect(seloGrupo(grupo({ escolhidos: 0 })).vazio).toBe(true);
  });
});

describe("faixa de contexto", () => {
  it("nomeia o grupo ativo e as vidas", () => {
    expect(textoContexto(grupo())).toBe(
      "Você está escolhendo os planos que vão competir com o AMIL S750 - Apto. " +
        "— os valores abaixo são calculados para as 36 vidas deste grupo."
    );
  });

  it("nome de plano terminado em ponto não vira ponto duplo", () => {
    expect(textoContexto(grupo())).not.toContain("Apto..");
  });
});

describe("alternar plano", () => {
  it("marca preservando a ordem do catálogo", () => {
    expect(alternarPlano(grupo(), "op-2")).toEqual(["op-1", "op-2", "op-3"]);
  });

  it("desmarca sem tocar nos demais", () => {
    expect(alternarPlano(grupo(), "op-1")).toEqual(["op-3"]);
  });
});

describe("aviso de seleção vazia", () => {
  it("cala com pelo menos um plano", () => {
    expect(avisoSelecaoVazia(["op-1"])).toBeNull();
  });

  it("avisa que a etapa 4 fica sem o que atribuir", () => {
    expect(avisoSelecaoVazia([])).toContain("etapa 4");
  });
});
