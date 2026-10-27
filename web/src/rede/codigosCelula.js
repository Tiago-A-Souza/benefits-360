// Célula de cobertura da etapa 5: as quatro siglas padrão (H, HD, M, PS) e, só em
// hospital incluído à mão fora do critério, códigos crus da base (HPED, HOFTA…).
// Na TELA o código cru vai em cinza itálico; no documento exportado ele tem o
// mesmo estilo dos demais (isso é decidido no renderer HTML, não aqui).

export const SIGLAS_PADRAO = new Set(["H", "HD", "M", "PS"]);

export function partesCelula(texto) {
  const t = (texto || "").trim();
  if (!t || t === "—") return [];
  return t
    .split(/\s+/)
    .filter(Boolean)
    .map((codigo) => ({ codigo, cru: !SIGLAS_PADRAO.has(codigo.toUpperCase()) }));
}

export function celulaTemCodigoCru(texto) {
  return partesCelula(texto).some((p) => p.cru);
}
