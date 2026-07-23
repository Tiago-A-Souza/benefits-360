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

export async function obterRascunho(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/rascunho`);
  return tratarResposta(res, "Não foi possível carregar o rascunho.");
}

export async function salvarRascunho(estudoId, rascunho) {
  const res = await fetch(`${API}/estudos/${estudoId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(rascunho),
  });
  return tratarResposta(res, "Não foi possível salvar o estudo.");
}

export async function obterPendencias(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/pendencias`);
  return tratarResposta(res, "Não foi possível verificar pendências.");
}

export async function calcularEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/calcular`, { method: "POST" });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    if (body.detail?.erros) {
      const err = new Error("O cálculo não pôde ser concluído.");
      err.pendenciasCompilador = body.detail.erros;
      throw err;
    }
    throw new Error("Não foi possível calcular o comparativo.");
  }
  return res.json();
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

export async function obterResumoPlanoAtual(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/resumo-plano-atual`);
  return tratarResposta(res, "Não foi possível carregar o resumo do plano atual.");
}

export async function importarCotacaoPdf(estudoId, arquivo) {
  const form = new FormData();
  form.append("arquivo", arquivo);
  const res = await fetch(`${API}/estudos/${estudoId}/importar-cotacao-pdf`, {
    method: "POST",
    body: form,
  });
  return tratarResposta(res, "Não foi possível importar o PDF.");
}

export async function listarExtracoesCotacao(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/extracao-cotacao`);
  return tratarResposta(res, "Não foi possível listar extrações.");
}

export async function obterExtracaoCotacao(estudoId, extracaoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}`);
  return tratarResposta(res, "Não foi possível carregar a extração.");
}

export async function atualizarCampoExtracao(estudoId, extracaoId, campoId, patch) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/campos/${campoId}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    }
  );
  return tratarResposta(res, "Não foi possível atualizar o campo.");
}

export async function excluirOpcaoExtracao(estudoId, extracaoId, opcaoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/opcoes/${opcaoId}/excluir`,
    { method: "POST" }
  );
  return tratarResposta(res, "Não foi possível excluir a opção.");
}

export async function confirmarLoteExtracao(estudoId, extracaoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/confirmar-lote`,
    { method: "POST" }
  );
  return tratarResposta(res, "Não foi possível confirmar o lote.");
}

export async function aplicarExtracaoCotacao(estudoId, extracaoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/aplicar`,
    { method: "POST" }
  );
  if (res.status === 422) {
    const body = await res.json();
    const err = new Error(body.detail?.mensagem || "Não foi possível aplicar a extração.");
    err.bloqueios = body.detail?.bloqueios || [];
    throw err;
  }
  return tratarResposta(res, "Não foi possível aplicar a extração.");
}

export async function gerarSnapshot(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/snapshot`, { method: "POST" });
  return tratarResposta(res, "Não foi possível gerar o snapshot.");
}

export async function listarSnapshots(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/snapshots`);
  return tratarResposta(res, "Não foi possível listar snapshots.");
}

export async function obterSnapshot(estudoId, snapshotId) {
  const res = await fetch(`${API}/estudos/${estudoId}/snapshots/${snapshotId}`);
  return tratarResposta(res, "Não foi possível carregar o snapshot.");
}

export async function aprovarSnapshot(estudoId, snapshotId, body) {
  const res = await fetch(`${API}/estudos/${estudoId}/snapshots/${snapshotId}/aprovar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível aprovar o snapshot.");
}

export async function obterSnapshotAprovado(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/snapshot-aprovado`);
  if (!res.ok) throw new Error("Não foi possível verificar aprovação.");
  return res.json();
}

export async function previewApresentacao(estudoId, snapshotId, body) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/snapshots/${snapshotId}/apresentacao/preview`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  return tratarResposta(res, "Não foi possível pré-visualizar.");
}

export async function gerarApresentacaoHtml(estudoId, snapshotId, body) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/snapshots/${snapshotId}/apresentacao/gerar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  return tratarResposta(res, "Não foi possível gerar o HTML.");
}
