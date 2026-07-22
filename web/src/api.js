const API = "/api";

async function tratarResposta(res, mensagemPadrao) {
  if (res.ok) return res.json();
  let detalhe = mensagemPadrao;
  try {
    const body = await res.json();
    if (typeof body.detail === "string") detalhe = body.detail;
    else if (body.detail?.mensagem) detalhe = body.detail.mensagem;
    else if (body.detail?.opcoes) {
      const err = new Error(body.detail.mensagem || mensagemPadrao);
      err.opcoes = body.detail.opcoes;
      err.status = res.status;
      throw err;
    }
  } catch (e) {
    if (e.status) throw e;
  }
  throw new Error(detalhe);
}

export async function obterConfig() {
  const res = await fetch(`${API}/config`);
  if (!res.ok) throw new Error("Não foi possível carregar a configuração.");
  return res.json();
}

export async function obterEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}`);
  return tratarResposta(res, "Não foi possível carregar o estudo.");
}

export async function calcularEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/calcular`, { method: "POST" });
  return tratarResposta(res, "Não foi possível calcular o comparativo.");
}

export async function listarEstudos() {
  const res = await fetch(`${API}/estudos`);
  return tratarResposta(res, "Não foi possível listar estudos.");
}

export async function criarEstudo(id, titulo) {
  const res = await fetch(`${API}/estudos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, titulo }),
  });
  return tratarResposta(res, "Não foi possível criar o estudo.");
}

export async function importarSiscor(estudoId, arquivo, { modo, titulo } = {}) {
  const form = new FormData();
  form.append("arquivo", arquivo);
  const params = new URLSearchParams();
  if (modo) params.set("modo", modo);
  if (titulo) params.set("titulo", titulo);
  const qs = params.toString();
  const url = `${API}/estudos/${estudoId}/importar-siscor${qs ? `?${qs}` : ""}`;
  const res = await fetch(url, { method: "POST", body: form });
  if (res.status === 409) {
    const body = await res.json();
    const err = new Error(body.detail?.mensagem || "Reimportação requer decisão.");
    err.opcoes = body.detail?.opcoes || [];
    err.status = 409;
    throw err;
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(
      typeof body.detail === "string" ? body.detail : "Falha ao importar planilha."
    );
  }
  return res.json();
}

export async function obterConferenciaSiscor(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/conferencia-siscor`);
  return tratarResposta(res, "Não foi possível carregar a conferência.");
}

export async function confirmarLoteSiscor(estudoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/conferencia-siscor/confirmar-lote`,
    { method: "POST" }
  );
  return tratarResposta(res, "Não foi possível confirmar o lote.");
}

export async function atualizarLinhaSiscor(estudoId, linhaId, patch) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/conferencia-siscor/linhas/${linhaId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }
  );
  return tratarResposta(res, "Não foi possível atualizar a linha.");
}
