import { describe, expect, it } from "vitest";
import { classeDiffEstimativa } from "../money.js";
import {
  ETAPAS_CONFIRMA_NO_AVANCO,
  mensagemExcecaoBase,
  mensagemLacunasAtribuicao,
  proximaEtapaClicavel,
  rotuloOpcaoComDiff,
  rotuloOpcaoNome,
} from "./avancoEtapa.js";

describe("avancoEtapa", () => {
  it("etapas 1, 2 e 4 confirmam no avanço; rede e comparativo não", () => {
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("base")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("plano")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("selecionados")).toBe(true);
    expect(ETAPAS_CONFIRMA_NO_AVANCO.has("rede")).toBe(false);
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

  it("rótulo do dropdown usa o diff pronto e omite opção sem estimativa", () => {
    expect(rotuloOpcaoNome("Prata", "Apartamento")).toBe("Prata (Apartamento)");
    expect(rotuloOpcaoComDiff("Diamante mais 1 Q", null, -573900)).toBe(
      "Diamante mais 1 Q — -R$ 5.739,00"
    );
    expect(rotuloOpcaoComDiff("Ouro mais 1 Q", null, 78000)).toBe(
      "Ouro mais 1 Q — +R$ 780,00"
    );
    expect(rotuloOpcaoComDiff("Prata", "Apartamento", null)).toBe("Prata (Apartamento)");
    expect(rotuloOpcaoComDiff("Prata", "Apartamento", null)).not.toContain("R$ 0");
    expect(rotuloOpcaoComDiff("Prata", null, null)).toBe("Prata");
    expect(rotuloOpcaoComDiff("Prata", null, null)).not.toContain("—");
  });

  it("diff negativo é economia (verde) e positivo é acréscimo (vermelho)", () => {
    expect(classeDiffEstimativa(-577959)).toBe("cmp-valor--economia");
    expect(classeDiffEstimativa(6346306)).toBe("cmp-valor--aumento");
    expect(classeDiffEstimativa(0)).toBe("cmp-valor--neutro");
    expect(classeDiffEstimativa(null)).toBe(null);
  });
});
