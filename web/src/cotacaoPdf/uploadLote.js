/** Upload em lote — cada arquivo isolado; falha parcial não aborta o restante. */

function mensagemSucesso(res) {
  const n = res.opcoes_encontradas ?? 0;
  const rotulo = n === 1 ? "plano" : "planos";
  if (res.sucesso && n > 0) {
    return `${n} ${rotulo}`;
  }
  if (res.estado) {
    return `recebido (${res.estado})`;
  }
  return "importado";
}

/**
 * @param {File[]} files
 * @param {(file: File) => Promise<object>} importarFn
 * @returns {Promise<Array<{nome: string, ok: boolean, extracao_id?: string, mensagem: string}>>}
 */
export async function executarUploadLote(files, importarFn) {
  const resultados = [];
  for (const file of files) {
    try {
      const res = await importarFn(file);
      resultados.push({
        nome: file.name,
        ok: true,
        extracao_id: res.extracao_id,
        mensagem: mensagemSucesso(res),
      });
    } catch (err) {
      resultados.push({
        nome: file.name,
        ok: false,
        mensagem: err?.message || "falhou",
      });
    }
  }
  return resultados;
}

/** @param {Array<{nome: string, ok: boolean, mensagem: string}>} resultados */
export function formatarResumoUploads(resultados) {
  return resultados
    .map((r) =>
      r.ok ? `${r.nome}: ${r.mensagem}` : `${r.nome}: falhou (${r.mensagem})`
    )
    .join(" · ");
}

/** @param {Array<{ok: boolean, extracao_id?: string}>} resultados */
export function primeiroUploadComSucesso(resultados) {
  const hit = resultados.find((r) => r.ok && r.extracao_id);
  return hit?.extracao_id ?? null;
}
