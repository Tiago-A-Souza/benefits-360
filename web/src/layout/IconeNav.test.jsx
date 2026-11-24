import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import IconeNav, { RotuloNav } from "./IconeNav.jsx";
import NavegacaoFerramentas from "../NavegacaoFerramentas.jsx";

globalThis.React = React;

describe("ícones da barra", () => {
  it("desenha o ícone vazado pedido", () => {
    const html = renderToStaticMarkup(<IconeNav nome="estudos" />);
    expect(html).toContain("nav-icone");
    expect(html).toContain("stroke=");
    expect(html).not.toContain('fill="currentColor"');
  });

  it("rótulo junta ícone e texto", () => {
    const html = renderToStaticMarkup(<RotuloNav icone="simular">Simular rede</RotuloNav>);
    expect(html).toContain("Simular rede");
    expect(html).toContain("nav-icone");
  });

  it("Navegar leva ícone em cada tópico", () => {
    const html = renderToStaticMarkup(
      <NavegacaoFerramentas
        ativo="estudos"
        onMeusEstudos={() => {}}
        onSimularRede={() => {}}
        onCotacoes={() => {}}
      />
    );
    expect(html.match(/nav-icone/g)?.length).toBe(3);
    expect(html).toContain("Meus estudos");
    expect(html).toContain("Simular rede");
    expect(html).toContain("Cotações");
  });
});
