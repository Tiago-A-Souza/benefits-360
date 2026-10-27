import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CelulaCobertura from "./CelulaCobertura.jsx";
import { celulaTemCodigoCru, partesCelula } from "./codigosCelula.js";

globalThis.React = React;

describe("código de cobertura na etapa 5", () => {
  it("siglas padrão não são cruas", () => {
    expect(partesCelula("H HD M PS").every((p) => !p.cru)).toBe(true);
    expect(celulaTemCodigoCru("H PS")).toBe(false);
  });

  it("código da base sem sigla é cru", () => {
    expect(partesCelula("HPED PSPED").map((p) => p.cru)).toEqual([true, true]);
    expect(partesCelula("H HCELT").map((p) => p.cru)).toEqual([false, true]);
  });

  it("vazio e travessão não geram partes", () => {
    expect(partesCelula("")).toEqual([]);
    expect(partesCelula("—")).toEqual([]);
    expect(partesCelula(undefined)).toEqual([]);
  });

  it("cinza itálico só no cru; sigla padrão fica sem marca", () => {
    const html = renderToStaticMarkup(<CelulaCobertura texto="H HPED" />);
    expect(html).toContain('class="cod-cru"');
    expect(html.match(/cod-cru/g)).toHaveLength(1);
    expect(renderToStaticMarkup(<CelulaCobertura texto="H PS" />)).not.toContain("cod-cru");
  });
});
