/** Revisão da cotação: acomodação inferida e tipo fiscal uma vez no documento. */

import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

globalThis.React = React;

import { RevisaoPlano } from "../CotacaoPdfPanel.jsx";
import {
  acomodacaoPrecisaDeclarar,
  camposAcomodacaoInferidaParaGravar,
  idsTipoFiscalPendentes,
  rotuloAcomodacaoRevisao,
  rotuloTipoFiscalCotacao,
  tipoFiscalPrecisaDeclararNaCotacao,
  valorAcomodacaoCanonica,
} from "./utils.js";

function opcao(over = {}) {
  return {
    id: "op-1",
    plano_nome: { texto: "Executivo R1 Apartamento (Nacional)" },
    operadora: { texto: "SulAmérica" },
    tipo_fiscal: { id: "tf-1", texto: "" },
    acomodacao: { id: "ac-1", texto: "" },
    regime_copart: { id: "rg-1", texto: "sem" },
    validade_oficial: { data: "2026-04-10" },
    tabela: [],
    ...over,
  };
}

function htmlRevisao(op) {
  return renderToStaticMarkup(
    <RevisaoPlano
      op={op}
      quantidades={{ 0: 1 }}
      siscorCtx={{ exigeEscolha: false }}
      estimativaMotor={null}
      validadeDocumento="2026-04-10"
      onSalvarCampo={() => {}}
    />
  );
}

describe("acomodação na revisão", () => {
  it("Apartamento no nome resolve sem dropdown", () => {
    const op = opcao();
    expect(valorAcomodacaoCanonica(op)).toBe("apartamento");
    expect(acomodacaoPrecisaDeclarar(op)).toBe(false);
    expect(rotuloAcomodacaoRevisao(op)).toBe("Apartamento");
    const html = htmlRevisao(op);
    expect(html).not.toContain("Não extraída do PDF nem do nome");
    expect(html).not.toContain("O IOF de 2,38%");
    expect(html).toContain("Apartamento");
  });

  it("letra Q no nome Porto resolve Apartamento", () => {
    expect(
      valorAcomodacaoCanonica(
        opcao({ plano_nome: { texto: "P220 Q" }, acomodacao: { id: "ac-1", texto: "" } })
      )
    ).toBe("apartamento");
  });

  it("sem pista no nome ainda pede declaração", () => {
    const op = opcao({ plano_nome: { texto: "Executivo R1 Nacional" } });
    expect(acomodacaoPrecisaDeclarar(op)).toBe(true);
    expect(htmlRevisao(op)).toContain("Não extraída do PDF nem do nome");
  });

  it("grava a inferência só quando o campo veio vazio", () => {
    const vazia = opcao();
    expect(camposAcomodacaoInferidaParaGravar([vazia])).toEqual([
      { id: "ac-1", texto: "apartamento" },
    ]);
    const jaPreenchida = opcao({ acomodacao: { id: "ac-1", texto: "apartamento" } });
    expect(camposAcomodacaoInferidaParaGravar([jaPreenchida])).toEqual([]);
  });
});

describe("tipo fiscal da cotação", () => {
  it("um dropdown cobre todos os planos ainda vazios", () => {
    const a = opcao({ tipo_fiscal: { id: "tf-a", texto: "" } });
    const b = opcao({ id: "op-2", tipo_fiscal: { id: "tf-b", texto: "" } });
    expect(tipoFiscalPrecisaDeclararNaCotacao([a, b])).toBe(true);
    expect(idsTipoFiscalPendentes([a, b])).toEqual(["tf-a", "tf-b"]);
    expect(rotuloTipoFiscalCotacao([a, b])).toBe(null);
  });

  it("já declarado some da declaração", () => {
    const a = opcao({ tipo_fiscal: { id: "tf-a", texto: "seguradora" } });
    expect(tipoFiscalPrecisaDeclararNaCotacao([a])).toBe(false);
    expect(rotuloTipoFiscalCotacao([a])).toBe("Seguradora");
  });
});
