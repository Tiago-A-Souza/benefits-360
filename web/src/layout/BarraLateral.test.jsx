import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import AppChrome from "./AppChrome.jsx";
import BarraLateral from "./BarraLateral.jsx";

globalThis.React = React;

describe("BarraLateral", () => {
  it("logo no topo, Sair e versão no rodapé, sem Estudo Saúde", () => {
    const html = renderToStaticMarkup(
      <AppChrome onSair={() => {}}>
        <BarraLateral>
          <p>Meus estudos</p>
        </BarraLateral>
      </AppChrome>
    );
    expect(html).toContain("turya-logo.png");
    expect(html).toContain('alt="Turya"');
    expect(html).toContain("Sair");
    expect(html).toContain("V1.0.1");
    expect(html).not.toContain("Estudo Saúde");
    expect(html).not.toContain("topbar");
    expect(html).not.toContain("system-title");
    expect(html).toContain("app-sidebar-rodape");
    expect(html.indexOf("turya-logo.png")).toBeLessThan(html.indexOf("Sair"));
    expect(html.indexOf("Sair")).toBeLessThan(html.indexOf("V1.0.1"));
  });

  it("sem onSair não mostra o botão, mas mostra a versão", () => {
    const html = renderToStaticMarkup(
      <BarraLateral>
        <p>filtro</p>
      </BarraLateral>
    );
    expect(html).not.toContain(">Sair<");
    expect(html).toContain("V1.0.1");
    expect(html).toContain("Turya");
  });
});
