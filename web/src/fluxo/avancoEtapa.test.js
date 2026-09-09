import { describe, expect, it } from "vitest";
import {
  ETAPAS_CONFIRMA_NO_AVANCO,
  mensagemExcecaoBase,
  mensagemLacunasAtribuicao,
  proximaEtapaClicavel,
} from "./avancoEtapa.js";

describe("avancoEtapa", () => {
  it("etapas 1, 2 e 4 confirmam no avanço; a 5 não", () => {
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("base")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("plano")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("selecionados")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("comparativo")).toBe(false);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("cotacoes")).toBe(false);
  });

  it("próxima etapa fica clicável nas etapas que confirmam ao avançar", () => {
    const never = () => false;
    expect(proximaEtapaClicavel("base", 1, {}, never)).toBe(true);
    expect(proximaEtapaClicavel("plano", 2, {}, never)).toBe(true);
    expect(proximaEtapaClicavel("selecionados", 4, {}, never)).toBe(true);
    expect(proximaEtapaClicavel("cotacoes", 3, {}, never)).toBe(false);
    expect(proximaEtapaClicavel("comparativo", 5, {}, never)).toBe(false);
  });

  it("mensagem de exceção da etapa 1 é a mesma da pendência", () => {
    expect(mensagemExcecaoBase(2)).toBe("2 exceção(ões) na base");
  });

  it("mensagem de cenário incompleto lista o que falta", () => {
    expect(mensagemLacunasAtribuicao([["S750"], []])).toBe(
      "Cenário 1: falta escolher cotação para S750"
    );
  });
});
