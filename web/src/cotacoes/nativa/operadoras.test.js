import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { MARCA_OPERADORAS, attrsCartaoOperadora, estiloMarcaOperadora } from "./operadoras";

const dir = dirname(fileURLToPath(import.meta.url));

describe("marca das operadoras", () => {
  it("cores principais vêm da amostragem das logos (Amil violeta, Bradesco vermelho, SulAmérica laranja)", () => {
    expect(MARCA_OPERADORAS.amil.cor).toBe("#4018F8");
    expect(MARCA_OPERADORAS.bradesco.cor).toBe("#CC092F");
    expect(MARCA_OPERADORAS.sulamerica.cor).toBe("#F08810");
    expect(MARCA_OPERADORAS.amil.corCabeca).toBe("rgba(64, 24, 248, 0.06)");
    expect(MARCA_OPERADORAS.bradesco.corCabeca).toBe("rgba(204, 9, 47, 0.06)");
    expect(MARCA_OPERADORAS.sulamerica.corCabeca).toBe("rgba(240, 136, 16, 0.06)");
    expect(MARCA_OPERADORAS.porto.cor).toBe("#00A651");
  });

  it("estilo do cartão leva --cor-op, suave e cabeçalho", () => {
    const s = estiloMarcaOperadora("amil");
    expect(s["--cor-op"]).toBe("#4018F8");
    expect(s["--cor-op-suave"]).toBe("rgba(64, 24, 248, 0.12)");
    expect(s["--cor-op-cabeca"]).toBe("rgba(64, 24, 248, 0.06)");
    const a = attrsCartaoOperadora("bradesco", true);
    expect(a.className).toContain("nativa-op-cartao--ativo");
    expect(a["data-cor-op"]).toBe("#CC092F");
  });

  it("CSS do cartão vence o border shorthand de .cartao (faixa 4px + borda da marca)", () => {
    const css = readFileSync(join(dir, "nativa.css"), "utf8");
    expect(css).toMatch(/\.nativa-shell \.cartao\.nativa-op-cartao/);
    expect(css).toMatch(/border-left:\s*4px solid var\(--cor-op/);
    expect(css).toMatch(/--cor-op-cabeca/);
    expect(css).not.toMatch(/border-left-width:\s*3px/);
  });

  it("a barra de ação de Cotações não flutua por cima da tabela", () => {
    const css = readFileSync(join(dir, "nativa.css"), "utf8");
    const bloco = css.match(/\.nativa-barra-acao\s*\{[^}]+\}/)[0];
    expect(bloco).not.toMatch(/position:\s*(sticky|fixed)/);
    expect(bloco).not.toMatch(/box-shadow:\s*var\(--shadow/);
    expect(css).not.toMatch(/\.nativa-main\s*\{[^}]*padding-bottom:\s*7\.5rem/);
  });
});
