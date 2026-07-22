const API = "/api";

export async function obterEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}`);
  if (!res.ok) throw new Error("Não foi possível carregar o estudo.");
  return res.json();
}

export async function calcularEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/calcular`, { method: "POST" });
  if (!res.ok) throw new Error("Não foi possível calcular o comparativo.");
  return res.json();
}

export async function listarEstudos() {
  const res = await fetch(`${API}/estudos`);
  if (!res.ok) throw new Error("Não foi possível listar estudos.");
  return res.json();
}
