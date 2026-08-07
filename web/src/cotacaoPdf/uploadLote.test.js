import { describe, expect, it, vi } from "vitest";
import {
  executarUploadLote,
  formatarResumoUploads,
  primeiroUploadComSucesso,
} from "./uploadLote.js";

describe("executarUploadLote", () => {
  it("continua após falha no meio e resume os três arquivos", async () => {
    const files = [{ name: "Porto.pdf" }, { name: "SulAmerica.pdf" }, { name: "Amil.pdf" }];
    const importarFn = vi.fn(async (file) => {
      if (file.name === "SulAmerica.pdf") {
        throw new Error("tabela não localizada");
      }
      const n = file.name === "Porto.pdf" ? 22 : 4;
      return {
        extracao_id: `ext-${file.name}`,
        sucesso: true,
        opcoes_encontradas: n,
        estado: "extraido",
      };
    });

    const resultados = await executarUploadLote(files, importarFn);

    expect(importarFn).toHaveBeenCalledTimes(3);
    expect(resultados.filter((r) => r.ok)).toHaveLength(2);
    expect(resultados.find((r) => r.nome === "SulAmerica.pdf")?.ok).toBe(false);

    const resumo = formatarResumoUploads(resultados);
    expect(resumo).toContain("Porto.pdf: 22 planos");
    expect(resumo).toContain("SulAmerica.pdf: falhou (tabela não localizada)");
    expect(resumo).toContain("Amil.pdf: 4 planos");

    expect(primeiroUploadComSucesso(resultados)).toBe("ext-Porto.pdf");
  });
});
