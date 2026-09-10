/** FASE 1 — tela de seleção por grupo. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

globalThis.React = React;

import {
  alternarPlano,
  avisoSelecaoVazia,
  aposUltimoPdfDeveVoltarLista,
  avancoDeveRevelarSelecaoPorGrupo,
  exibeSelecaoPorGrupo,
  visaoSelecaoPorGrupo,
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

describe("avanço revela a seleção por grupo", () => {
  it("dentro de um PDF, com dois grupos, o avanço fica na etapa 3", () => {
    expect(avancoDeveRevelarSelecaoPorGrupo(true, "selecao")).toBe(true);
    expect(avancoDeveRevelarSelecaoPorGrupo(true, "revisao")).toBe(true);
  });

  it("já na lista, o avanço segue para a etapa 4", () => {
    expect(avancoDeveRevelarSelecaoPorGrupo(true, "lista")).toBe(false);
  });

  it("estudo de um plano vigente não intercepta", () => {
    expect(avancoDeveRevelarSelecaoPorGrupo(false, "selecao")).toBe(false);
    expect(avancoDeveRevelarSelecaoPorGrupo(false, "lista")).toBe(false);
  });
});

describe("último PDF volta à lista", () => {
  it("dois grupos e sem próximo documento voltam à lista", () => {
    expect(aposUltimoPdfDeveVoltarLista(true, false)).toBe(true);
  });

  it("ainda há PDF pendente: segue o documento, não a lista", () => {
    expect(aposUltimoPdfDeveVoltarLista(true, true)).toBe(false);
  });

  it("um plano vigente não muda o fluxo de hoje", () => {
    expect(aposUltimoPdfDeveVoltarLista(false, false)).toBe(false);
    expect(aposUltimoPdfDeveVoltarLista(false, true)).toBe(false);
  });
});

describe("visao da secao", () => {
  it("dois grupos mostram a tela", () => {
    expect(
      visaoSelecaoPorGrupo(
        { grupos: [grupo(), grupo({ subgrupo_id: "sg-2" })] },
        null,
        true
      )
    ).toBe("tela");
  });

  it("GET falho com dois grupos mostra o erro", () => {
    expect(visaoSelecaoPorGrupo(null, "falha de rede", true)).toBe("erro");
  });

  it("um plano vigente não mostra tela nem erro de GET", () => {
    expect(visaoSelecaoPorGrupo({ grupos: [grupo()] }, null, false)).toBe(null);
    expect(visaoSelecaoPorGrupo(null, "falha de rede", false)).toBe(null);
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
