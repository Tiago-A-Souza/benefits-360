/** Log de erro de UI sem PII (sem e-mail, CNPJ, nome de empresa, senha). */

const PII = [
  /\b\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}\b/g,
  /\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g,
  /[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi,
];

function limpar(texto) {
  let t = String(texto || "").slice(0, 400);
  for (const re of PII) t = t.replace(re, "•••");
  return t;
}

export function registrarErro(erro, { rota = "", componente = "" } = {}) {
  const mensagem = limpar(erro && (erro.stack || erro.message || erro));
  const hash =
    typeof window !== "undefined" ? String(window.location.hash || "").split("?")[0] : "";
  // eslint-disable-next-line no-console
  console.error("[Benefits]", {
    rota: rota || hash,
    componente,
    mensagem,
  });
}
