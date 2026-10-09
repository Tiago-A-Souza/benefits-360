/** Filtros da etapa 5 — funções puras (testáveis). */

export function filtrarLinhasRede(linhas, { zona = "", municipio = "", nome = "" } = {}) {
  const trecho = (nome || "").trim().toLowerCase();
  return (linhas || []).filter((ln) => {
    if (zona && ln.zona !== zona) return false;
    if (municipio && ln.municipio !== municipio) return false;
    if (trecho && !(ln.prestador || "").toLowerCase().includes(trecho)) return false;
    return true;
  });
}
