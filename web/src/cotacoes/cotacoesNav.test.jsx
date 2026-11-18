import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import NavegacaoFerramentas from "../NavegacaoFerramentas.jsx";

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");

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

  it("sem a flag, o menu Cotações do App continua no iframe (CotacoesRpa)", () => {
    const app = readFileSync(join(raiz, "App.jsx"), "utf8");
    expect(app).toContain("onCotacoes={() => setCotacoesRpa(true)}");
    expect(app).toContain("nativaLigada()");
    const iframe = readFileSync(join(raiz, "cotacoes", "CotacoesRpa.jsx"), "utf8");
    expect(iframe).toContain("<iframe");
    expect(iframe).toContain("Newport Cotações (RPA)");
  });
});