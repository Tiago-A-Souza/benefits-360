/** FASE 2 — o dropdown da etapa 4 oferece só os planos do grupo. */

import { describe, expect, it } from "vitest";

import {
  atribuicaoForaDaSelecao,
  opcoesDoSubgrupo,
  opcoesParaDropdown,
} from "./opcoesPorGrupo.js";

const OPCOES = [
  { id: "op-1", plano_nome: "Plano A" },
  { id: "op-2", plano_nome: "Plano B" },
  { id: "op-3", plano_nome: "Plano C" },
  { id: "op-4", plano_nome: "Plano D" },
  { id: "op-5", plano_nome: "Executivo R2" },
];

function matriz(pares) {
  return {
    celulas: pares.map(([subgrupo_id, opcao_id]) => ({ subgrupo_id, opcao_id })),
  };
}

const TRES_E_DOIS = matriz([
  ["sg-1", "op-1"],
  ["sg-1", "op-2"],
  ["sg-1", "op-3"],
  ["sg-2", "op-3"],
  ["sg-2", "op-4"],
]);

describe("lista de cada grupo", () => {
  it("o dropdown do grupo 1 lista tres e o do grupo 2 lista dois", () => {
    expect(opcoesDoSubgrupo(OPCOES, TRES_E_DOIS, "sg-1").map((o) => o.id)).toEqual([
      "op-1",
      "op-2",
      "op-3",
    ]);
    expect(opcoesDoSubgrupo(OPCOES, TRES_E_DOIS, "sg-2").map((o) => o.id)).toEqual([
      "op-3",
      "op-4",
    ]);
  });

  it("plano escolhido nos dois grupos aparece nos dois", () => {
    expect(opcoesDoSubgrupo(OPCOES, TRES_E_DOIS, "sg-1").map((o) => o.id)).toContain(
      "op-3"
    );
    expect(opcoesDoSubgrupo(OPCOES, TRES_E_DOIS, "sg-2").map((o) => o.id)).toContain(
      "op-3"
    );
  });

  it("o Executivo R2, fora da selecao, some do dropdown", () => {
    const ids = opcoesDoSubgrupo(OPCOES, TRES_E_DOIS, "sg-1").map((o) => o.id);
    expect(ids).not.toContain("op-5");
  });

  it("sem matriz carregada, degrada para o catalogo inteiro", () => {
    expect(opcoesDoSubgrupo(OPCOES, null, "sg-1")).toHaveLength(5);
  });
});

describe("atribuicao que ficou fora depois de mudar a selecao", () => {
  it("continua visivel no dropdown, para nao sumir em silencio", () => {
    const ids = opcoesParaDropdown(OPCOES, TRES_E_DOIS, "sg-1", "op-5").map((o) => o.id);
    expect(ids).toEqual(["op-1", "op-2", "op-3", "op-5"]);
  });

  it("e denunciada pelo nome", () => {
    expect(atribuicaoForaDaSelecao(OPCOES, TRES_E_DOIS, "sg-1", "op-5")).toBe(
      "Executivo R2"
    );
  });

  it("atribuicao dentro da selecao nao gera aviso", () => {
    expect(atribuicaoForaDaSelecao(OPCOES, TRES_E_DOIS, "sg-1", "op-2")).toBeNull();
  });

  it("cenario vazio nao gera aviso", () => {
    expect(atribuicaoForaDaSelecao(OPCOES, TRES_E_DOIS, "sg-1", "")).toBeNull();
  });

  it("nao acrescenta nada quando a atribuicao esta na lista", () => {
    expect(opcoesParaDropdown(OPCOES, TRES_E_DOIS, "sg-1", "op-2")).toHaveLength(3);
  });
});
