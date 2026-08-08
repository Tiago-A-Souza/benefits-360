const API = "/api";

function montarErroApi(res, body, mensagemPadrao) {
  const detail = body?.detail;
  let mensagem = mensagemPadrao;
  let codigo = null;
  if (typeof detail === "string" && detail.trim()) {
    mensagem = detail;
  } else if (detail && typeof detail === "object") {
    if (detail.mensagem) mensagem = detail.mensagem;
    else if (detail.message) mensagem = detail.message;
    if (detail.codigo) codigo = detail.codigo;
    if (detail.opcoes) {
      const err = new Error(mensagem || mensagemPadrao);
      err.opcoes = detail.opcoes;
      err.status = res.status;
      err.codigo = codigo;
      err.body = body;
      return err;
    }
  } else if (Array.isArray(detail) && detail.length) {
    const primeiro = detail[0];
    mensagem =
      primeiro?.msg ||
      primeiro?.mensagem ||
      (typeof primeiro === "string" ? primeiro : mensagemPadrao);
  } else if (typeof body === "string" && body.trim()) {
    mensagem = body.trim().slice(0, 300);
  }
  const prefixo = codigo ? `${codigo}: ` : res.status ? `HTTP ${res.status}: ` : "";
  const err = new Error(`${prefixo}${mensagem}`);
  err.status = res.status;
  err.codigo = codigo;
  err.body = body;
  return err;
}

async function tratarResposta(res, mensagemPadrao) {
  if (res.ok) return res.json();
  const texto = await res.text();
  let body = null;
  try {
    body = texto ? JSON.parse(texto) : null;
  } catch {
    body = texto || null;
  }
  throw montarErroApi(res, body, mensagemPadrao);
}

/** Mensagem legível para o operador; rede/timeout têm texto próprio. */
export function mensagemErroOperador(err, mensagemPadrao) {
  if (!err) return mensagemPadrao;
  const raw = String(err.message || "");
  if (
    err.name === "TypeError" ||
    /failed to fetch|networkerror|load failed|fetch/i.test(raw)
  ) {
    return "Falha de rede ao falar com o servidor. Verifique se a API está no ar e tente novamente.";
  }
  if (/timeout|timed out|aborted/i.test(raw)) {
    return "A requisição demorou demais (timeout). Tente novamente.";
  }
  return raw || mensagemPadrao;
}

export async function registrarDiagnostico({ estudoId, etapa, evento, detalhe } = {}) {
  try {
    await fetch(`${API}/diagnostico`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        estudo_id: estudoId || null,
        etapa: etapa || "cotacao_pdf",
        evento,
        detalhe: detalhe || {},
      }),
    });
  } catch {
    /* diagnóstico nunca bloqueia o fluxo principal */
  }
}

export async function obterConfig() {
  const res = await fetch(`${API}/config`);
  if (!res.ok) throw new Error("Não foi possível carregar a configuração.");
  return res.json();
}

export async function obterDiagnostico(limite = 200) {
  const res = await fetch(`${API}/diagnostico?limite=${limite}`);
  return tratarResposta(res, "Não foi possível carregar o diagnóstico.");
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

export async function confirmarComparativo(estudoId, hashComparativo, opcaoIds) {
  const body = { opcao_ids: opcaoIds };
  if (hashComparativo) body.hash_comparativo = hashComparativo;
  const res = await fetch(`${API}/estudos/${estudoId}/comparativo/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível confirmar o comparativo.");
}

export async function salvarSelecaoApresentacao(estudoId, opcaoIds) {
  const res = await fetch(`${API}/estudos/${estudoId}/comparativo/selecao-apresentacao`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opcao_ids: opcaoIds }),
  });
  return tratarResposta(res, "Não foi possível salvar a seleção para apresentação.");
}

export async function listarEstudos() {
  const res = await fetch(`${API}/estudos`);
  return tratarResposta(res, "Não foi possível listar estudos.");
}

export async function criarEstudo({ titulo, nome_empresa, id, formato } = {}) {
  const res = await fetch(`${API}/estudos`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      titulo,
      nome_empresa: nome_empresa,
      id: id || null,
      formato: formato || "renovacao",
    }),
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

export async function estimarPropostasExtracao(estudoId, extracaoId, quantidadesPorFaixa) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/estimar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ quantidades_por_faixa: quantidadesPorFaixa }),
    }
  );
  return tratarResposta(res, "Não foi possível estimar as propostas.");
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

export async function selecionarOpcaoExtracao(estudoId, extracaoId, opcaoId, selecionada) {
  let res;
  try {
    res = await fetch(
      `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/opcoes/${opcaoId}/selecionar`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ selecionada }),
      }
    );
  } catch (err) {
    const e = new Error(mensagemErroOperador(err, "Não foi possível atualizar a seleção."));
    e.causaRede = true;
    throw e;
  }
  return tratarResposta(res, "Não foi possível atualizar a seleção. Recarregue a cotação e tente de novo.");
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

export async function removerExtracaoCotacao(estudoId, extracaoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}`,
    { method: "DELETE" }
  );
  return tratarResposta(res, "Não foi possível remover a cotação.");
}

export async function descartarExtracaoCotacao(estudoId, extracaoId, motivo) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/descartar`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo }),
    }
  );
  return tratarResposta(res, "Não foi possível descartar a cotação.");
}

export async function reverterDescarteExtracaoCotacao(estudoId, extracaoId) {
  const res = await fetch(
    `${API}/estudos/${estudoId}/extracao-cotacao/${extracaoId}/reverter-descarte`,
    { method: "POST" }
  );
  return tratarResposta(res, "Não foi possível reverter o descarte da cotação.");
}

export function urlPdfCotacao(estudoId, documentoId) {
  return `${API}/estudos/${estudoId}/documentos-cotacao/${documentoId}/pdf`;
}

/** Carrega o PDF como blob URL — renderiza inline sem popup de download. */
export async function carregarPdfCotacaoBlob(estudoId, documentoId) {
  const res = await fetch(urlPdfCotacao(estudoId, documentoId));
  if (!res.ok) {
    let detalhe = "Não foi possível carregar o PDF.";
    try {
      const body = await res.json();
      if (typeof body.detail === "string") detalhe = body.detail;
    } catch {
      /* resposta não-JSON */
    }
    throw new Error(detalhe);
  }
  const blob = await res.blob();
  if (!blob.size) throw new Error("O arquivo PDF está vazio ou indisponível.");
  return URL.createObjectURL(blob);
}

export function abrirPdfCotacao(estudoId, documentoId) {
  carregarPdfCotacaoBlob(estudoId, documentoId)
    .then((blobUrl) => {
      window.open(blobUrl, "_blank", "noopener,noreferrer");
    })
    .catch((err) => {
      window.alert(err.message || "Não foi possível abrir o PDF.");
    });
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

export async function obterHistoricoEstudo(estudoId) {
  const res = await fetch(`${API}/estudos/${estudoId}/historico`);
  return tratarResposta(res, "Não foi possível carregar o histórico.");
}

export async function listarClientes() {
  const res = await fetch(`${API}/clientes`);
  return tratarResposta(res, "Não foi possível listar clientes.");
}

export async function criarCliente(nome) {
  const res = await fetch(`${API}/clientes`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome }),
  });
  return tratarResposta(res, "Não foi possível criar cliente.");
}

export async function listarCiclosCliente(clienteId) {
  const res = await fetch(`${API}/clientes/${clienteId}/ciclos`);
  return tratarResposta(res, "Não foi possível listar ciclos.");
}

export async function vincularEstudoCliente(estudoId, body) {
  const res = await fetch(`${API}/estudos/${estudoId}/historico/vincular`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível vincular estudo.");
}

export async function confirmarVinculo(estudoId, body) {
  const res = await fetch(`${API}/estudos/${estudoId}/historico/vinculos/confirmar`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível confirmar vínculo.");
}

export async function confirmarVinculoLote(estudoId, body) {
  const res = await fetch(`${API}/estudos/${estudoId}/historico/vinculos/confirmar-lote`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível confirmar lote.");
}

export async function registrarPlanoContratado(estudoId, body) {
  const res = await fetch(`${API}/estudos/${estudoId}/plano-contratado`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return tratarResposta(res, "Não foi possível registrar plano contratado.");
}
