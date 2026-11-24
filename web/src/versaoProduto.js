/** Versão do produto (Benefits). Fonte única: web/package.json → Vite. Não é a versão da API/motor. */

export function versaoProduto() {
  return typeof __BENEFITS_VERSAO__ === "string" && __BENEFITS_VERSAO__
    ? __BENEFITS_VERSAO__
    : "0.0.0";
}

export function commitBuild() {
  return typeof __BENEFITS_COMMIT__ === "string" ? __BENEFITS_COMMIT__ : "";
}

export function rotuloVersao() {
  return `V${versaoProduto()}`;
}
