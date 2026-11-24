import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import FaixaRascunho, { faixaRascunhoLigada } from "./FaixaRascunho.jsx";

globalThis.React = React;

describe("faixa RASCUNHO INTERNO", () => {
  it("desliga sem variável, 0 ou false", () => {
    expect(faixaRascunhoLigada(undefined)).toBe(false);
    expect(faixaRascunhoLigada("")).toBe(false);
    expect(faixaRascunhoLigada("0")).toBe(false);
    expect(faixaRascunhoLigada("false")).toBe(false);
  });

  it("liga com 1, true ou sim", () => {
    expect(faixaRascunhoLigada("1")).toBe(true);
    expect(faixaRascunhoLigada("true")).toBe(true);
    expect(faixaRascunhoLigada("SIM")).toBe(true);
  });

  it("não renderiza quando desligada", () => {
    const html = renderToStaticMarkup(<FaixaRascunho ligada={false} />);
    expect(html).toBe("");
  });

  it("padrão (sem prop) não reserva faixa no layout", () => {
    const html = renderToStaticMarkup(<FaixaRascunho />);
    expect(html).toBe("");
  });

  it("mostra o aviso no topo quando ligada", () => {
    const html = renderToStaticMarkup(<FaixaRascunho ligada />);
    expect(html).toContain("RASCUNHO INTERNO");
    expect(html).toContain("ainda não homologados");
    expect(html).toContain("faixa-rascunho");
  });
});
