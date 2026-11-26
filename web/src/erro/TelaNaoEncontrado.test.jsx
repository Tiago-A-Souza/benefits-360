import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import TelaNaoEncontrado from "./TelaNaoEncontrado.jsx";

globalThis.React = React;

describe("TelaNaoEncontrado", () => {
  it("estudo de outro usuário: aviso sem dados", () => {
    const html = renderToStaticMarkup(
      <TelaNaoEncontrado
        tipo="estudo"
        onVoltarEstudos={() => {}}
        onSimularRede={() => {}}
        onCotacoes={() => {}}
      />
    );
    expect(html).toContain("Estudo não encontrado");
    expect(html).toContain("não foi encontrado ou você não tem acesso");
    expect(html).not.toContain("Demo Ltda");
    expect(html).not.toContain("empresa");
    expect(html).not.toContain("Estudo Saúde");
    expect(html).toContain("Turya");
    expect(html).toContain("V1.0.1");
  });

  it("rota inválida não fica em branco", () => {
    const html = renderToStaticMarkup(
      <TelaNaoEncontrado tipo="rota" onVoltarEstudos={() => {}} onSimularRede={() => {}} onCotacoes={() => {}} />
    );
    expect(html).toContain("Esta página não existe");
    expect(html).toContain("Voltar aos estudos");
    expect(html).not.toContain("Estudo Saúde");
    expect(html).not.toContain("topbar");
    expect(html).toContain("V1.0.1");
  });
});
