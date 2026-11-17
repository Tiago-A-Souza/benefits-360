import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import NavegacaoFerramentas from "../NavegacaoFerramentas.jsx";

globalThis.React = React;

describe("navegação — Cotações (RPA)", () => {
  it("mostra Cotações ao lado de Simular rede quando onCotacoes existe", () => {
    const html = renderToStaticMarkup(
      <NavegacaoFerramentas
        ativo="estudos"
        onMeusEstudos={() => {}}
        onSimularRede={() => {}}
        onCotacoes={() => {}}
      />
    );
    expect(html).toContain("Cotações");
    expect(html).toContain("Simular rede");
  });

  it("marca a aba Cotações como página atual", () => {
    const html = renderToStaticMarkup(
      <NavegacaoFerramentas
        ativo="cotacoes"
        onMeusEstudos={() => {}}
        onSimularRede={() => {}}
        onCotacoes={() => {}}
      />
    );
    expect(html).toContain('aria-current="page"');
    expect(html).toContain("Cotações");
  });
});