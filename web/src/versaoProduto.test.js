import { describe, expect, it } from "vitest";
import { commitBuild, rotuloVersao, versaoProduto } from "./versaoProduto.js";

describe("versão do produto", () => {
  it("lê a versão do package.json injetada pelo Vite, não a da API", () => {
    expect(versaoProduto()).toBe("1.0.0");
    expect(rotuloVersao()).toBe("V1.0.0");
    expect(versaoProduto()).not.toBe("2.8.2");
  });

  it("expõe o commit curto do build (pode ser vazio fora do git)", () => {
    const c = commitBuild();
    expect(typeof c).toBe("string");
    expect(c.length === 0 || c.length <= 12).toBe(true);
  });
});
