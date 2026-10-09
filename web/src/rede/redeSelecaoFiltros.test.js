import { describe, expect, it } from "vitest";
import { filtrarLinhasRede } from "./redeSelecaoFiltros.js";

const LINHAS = [
  { linha_id: "a", prestador: "HOSP ALPHA", municipio: "RJ.RIO DE JANEIRO", zona: "S" },
  { linha_id: "b", prestador: "HOSP BETA", municipio: "SP.SAO PAULO", zona: "O" },
  { linha_id: "c", prestador: "CLINICA GAMA", municipio: "RJ.RIO DE JANEIRO", zona: "S" },
];

describe("filtrarLinhasRede", () => {
  it("sem filtros devolve todas", () => {
    expect(filtrarLinhasRede(LINHAS)).toHaveLength(3);
  });

  it("filtra por zona", () => {
    expect(filtrarLinhasRede(LINHAS, { zona: "O" }).map((l) => l.linha_id)).toEqual(["b"]);
  });

  it("filtra por município e nome", () => {
    const out = filtrarLinhasRede(LINHAS, {
      municipio: "RJ.RIO DE JANEIRO",
      nome: "hosp",
    });
    expect(out.map((l) => l.linha_id)).toEqual(["a"]);
  });
});
