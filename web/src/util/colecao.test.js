import { describe, expect, it } from "vitest";
import { asArray, asObject, camposDaOperadora, etapasDaOperadora } from "./colecao";

describe("asArray", () => {
  it("mantém listas", () => {
    expect(asArray([1])).toEqual([1]);
  });
  it("extrai envelopes comuns da API/robô", () => {
    expect(asArray({ operadoras: [{ id: "amil" }] })).toEqual([{ id: "amil" }]);
    expect(asArray({ estudos: [{ id: "e1" }] })).toEqual([{ id: "e1" }]);
    expect(asArray({ pendencias: [] })).toEqual([]);
  });
  it("objeto sem lista vira vazio", () => {
    expect(asArray({ erro: "x" })).toEqual([]);
    expect(asArray(null)).toEqual([]);
    expect(asArray("x")).toEqual([]);
  });
});

describe("campos/etapas da operadora", () => {
  it("não quebra sem campos nem etapas", () => {
    expect(camposDaOperadora({ id: "amil" })).toEqual([]);
    expect(etapasDaOperadora(null)).toEqual([]);
  });
  it("asObject ignora lista", () => {
    expect(asObject([1])).toEqual({});
    expect(asObject({ a: 1 })).toEqual({ a: 1 });
  });
});
