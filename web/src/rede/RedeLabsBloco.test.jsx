import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import RedeLabsBloco from "./RedeLabsBloco.jsx";

globalThis.React = React;

const COLUNAS = [
  { chave: "rede-atual", operadora: "Amil", plano_nome: "S750", contrato_atual: true },
  { chave: "prop:a", operadora: "Bradesco", plano_nome: "Top", contrato_atual: false },
];

describe("RedeLabsBloco", () => {
  it("não renderiza se não houver marcas", () => {
    expect(renderToStaticMarkup(<RedeLabsBloco colunas={COLUNAS} />)).toBe("");
    expect(
      renderToStaticMarkup(
        <RedeLabsBloco colunas={COLUNAS} laboratorios={{ linhas: [] }} />
      )
    ).toBe("");
  });

  it("mostra ✓, totais e o título Laboratórios", () => {
    const html = renderToStaticMarkup(
      <RedeLabsBloco
        colunas={COLUNAS}
        laboratorios={{
          linhas: [
            { marca: "Delboni", celulas: { "rede-atual": "✓", "prop:a": "" } },
            { marca: "Lavoisier", celulas: { "rede-atual": "✓", "prop:a": "✓" } },
          ],
          contagem_por_coluna: { "rede-atual": 2, "prop:a": 1 },
        }}
      />
    );
    expect(html).toContain("Laboratórios");
    expect(html).toContain("Delboni");
    expect(html).toContain("Lavoisier");
    expect(html).toContain("✓");
    expect(html).not.toContain("ULTRA");
    expect(html).toContain("Cobertos");
    expect(html).toContain(">2<");
    expect(html).toContain(">1<");
  });
});
