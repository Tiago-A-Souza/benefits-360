import { useCallback, useEffect, useState } from "react";
import {
  aprovarSnapshot,
  gerarApresentacaoHtml,
  gerarSnapshot,
  listarSnapshots,
  obterRascunho,
  obterSnapshot,
  obterSnapshotAprovado,
  previewApresentacao,
} from "./api";

function formatarJson(obj) {
  try {
    return JSON.stringify(obj, null, 2);
  } catch {
    return String(obj);
  }
}

export default function RevisaoApresentacaoPanel({ estudoId }) {
  const [snapshots, setSnapshots] = useState([]);
  const [snapshotAtual, setSnapshotAtual] = useState(null);
  const [aprovado, setAprovado] = useState(null);
  const [propostas, setPropostas] = useState([]);
  const [propostasSel, setPropostasSel] = useState([]);
  const [modo, setModo] = useState("faixas");
  const [revisor, setRevisor] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [autoAprovacao, setAutoAprovacao] = useState(false);
  const [confirmo, setConfirmo] = useState(false);
  const [preview, setPreview] = useState(null);
  const [entregavel, setEntregavel] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [detalhesAbertos, setDetalhesAbertos] = useState(false);

  const recarregar = useCallback(async () => {
    if (!estudoId) return;
    try {
      const [lista, status, rascunho] = await Promise.all([
        listarSnapshots(estudoId),
        obterSnapshotAprovado(estudoId),
        obterRascunho(estudoId),
      ]);
      setSnapshots(lista);
      setAprovado(status);
      const ops = rascunho.opcoes_proposta || [];
      setPropostas(ops);
      const candidato = lista.find((s) => s.estado === "candidato");
      const snapId = status.aprovado ? status.snapshot_id : candidato?.id;
      if (snapId) {
        const snap = await obterSnapshot(estudoId, snapId);
        setSnapshotAtual(snap);
        const ordemSnap =
          snap.payload?.propostas_apresentacao ||
          snap.payload?.comparativo?.propostas_apresentacao ||
          rascunho.selecao_apresentacao?.ordem ||
          [];
        if (ordemSnap.length) {
          setPropostasSel(ordemSnap);
        } else if (!propostasSel.length && ops.length) {
          setPropostasSel(ops.map((o) => o.id));
        }
      } else {
        setSnapshotAtual(null);
        const ordemRascunho = rascunho.selecao_apresentacao?.ordem || [];
        if (ordemRascunho.length) {
          setPropostasSel(ordemRascunho);
        } else if (!propostasSel.length && ops.length) {
          setPropostasSel(ops.map((o) => o.id));
        }
      }
    } catch (e) {
      setErro(e.message);
    }
  }, [estudoId, propostasSel.length]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  async function handleGerarSnapshot() {
    setCarregando(true);
    setErro(null);
    try {
      await gerarSnapshot(estudoId);
      await recarregar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleAprovar() {
    if (!snapshotAtual || snapshotAtual.estado !== "candidato") return;
    setCarregando(true);
    setErro(null);
    try {
      await aprovarSnapshot(estudoId, snapshotAtual.id, {
        revisor_nome: revisor,
        justificativa: justificativa || null,
        confirmo_conteudo: confirmo,
        auto_aprovacao: autoAprovacao,
      });
      await recarregar();
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handlePreview() {
    const snapId = aprovado?.aprovado ? aprovado.snapshot_id : snapshotAtual?.id;
    if (!snapId || !aprovado?.aprovado) {
      setErro("Aprove o snapshot antes de pré-visualizar a apresentação.");
      return;
    }
    setCarregando(true);
    setErro(null);
    try {
      const vm = await previewApresentacao(estudoId, snapId, {
        modo,
        propostas_selecionadas: [],
        ressalvas: [],
      });
      setPreview(vm);
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleGerarHtml() {
    const snapId = aprovado?.snapshot_id;
    if (!snapId) {
      setErro("Snapshot aprovado necessário.");
      return;
    }
    if (modo === "beneficiario") {
      const ok = window.confirm(
        "O arquivo HTML conterá nomes de beneficiários. Confirma a geração para armazenamento privado local?"
      );
      if (!ok) return;
    }
    setCarregando(true);
    setErro(null);
    try {
      const res = await gerarApresentacaoHtml(estudoId, snapId, {
        modo,
        propostas_selecionadas: [],
        ressalvas: [],
      });
      setEntregavel(res);
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  const comparativo = snapshotAtual?.payload?.comparativo;

  return (
    <div className="cartao">
      <h2>Revisão e apresentação</h2>
      <p className="sub">
        Gere snapshot candidato, revise o conteúdo congelado, aprove localmente e produza HTML
        autocontido. Aprovação provisória — ainda não substitui autenticação corporativa.
      </p>

      {erro && <p className="erro">{erro}</p>}

      <section className="secao-inline">
        <h3>1. Snapshot candidato</h3>
        <button type="button" onClick={handleGerarSnapshot} disabled={carregando}>
          Gerar snapshot candidato
        </button>
        {snapshotAtual && (
          <p className="ok">
            Estado: <strong>{snapshotAtual.estado}</strong>
            {aprovado?.aprovado && " (aprovado)"}
          </p>
        )}
      </section>

      {snapshotAtual && (
        <section className="secao-inline">
          <h3>2. Conteúdo do snapshot</h3>
          {comparativo && (
            <div className="resumo-snapshot">
              <p>
                Beneficiários calculados: {comparativo.beneficiarios_calculados} · Seções:{" "}
                {comparativo.secoes?.length ?? 0}
              </p>
              {comparativo.totais && (
                <p>
                  Total atual: {comparativo.totais.atual_mensal_reais} · Proposta:{" "}
                  {comparativo.totais.proposta_mensal_reais} · Diferença:{" "}
                  {comparativo.totais.diferenca_mensal_reais}
                </p>
              )}
            </div>
          )}
          <button
            type="button"
            className="secundario"
            onClick={() => setDetalhesAbertos(!detalhesAbertos)}
          >
            {detalhesAbertos ? "Ocultar" : "Ver"} detalhes técnicos (hash, payload)
          </button>
          {detalhesAbertos && (
            <pre className="json-preview">
              Hash: {snapshotAtual.hash_sha256}
              {"\n\n"}
              {formatarJson(snapshotAtual.payload)}
            </pre>
          )}
        </section>
      )}

      {snapshotAtual?.estado === "candidato" && !aprovado?.aprovado && (
        <section className="secao-inline cartao--aviso">
          <h3>3. Aprovação local provisória</h3>
          <label>
            Nome do revisor
            <input
              type="text"
              value={revisor}
              onChange={(e) => setRevisor(e.target.value)}
              placeholder="Seu nome"
            />
          </label>
          <label>
            Justificativa (obrigatória se autoaprovação)
            <textarea
              value={justificativa}
              onChange={(e) => setJustificativa(e.target.value)}
              rows={2}
            />
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={autoAprovacao}
              onChange={(e) => setAutoAprovacao(e.target.checked)}
            />
            Estou aprovando meu próprio estudo (autoaprovação provisória)
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={confirmo}
              onChange={(e) => setConfirmo(e.target.checked)}
            />
            Confirmo que revisei integralmente o conteúdo do snapshot
          </label>
          <button type="button" onClick={handleAprovar} disabled={carregando || !confirmo}>
            Aprovar snapshot
          </button>
        </section>
      )}

      {aprovado?.aprovado && (
        <section className="secao-inline">
          <h3>4. Apresentação HTML</h3>
          <fieldset>
            <legend>Modo</legend>
            <label className="radio">
              <input
                type="radio"
                name="modo"
                value="faixas"
                checked={modo === "faixas"}
                onChange={() => setModo("faixas")}
              />
              Resumo por faixas etárias (recomendado — sem nomes)
            </label>
            <label className="radio">
              <input
                type="radio"
                name="modo"
                value="beneficiario"
                checked={modo === "beneficiario"}
                onChange={() => setModo("beneficiario")}
              />
              Detalhado por beneficiário (contém nomes)
            </label>
          </fieldset>

          <fieldset>
            <legend>Propostas no material</legend>
            <p className="muted cmp-previa-lead">
              Seleção definida na etapa Comparativo. Para alterar planos ou ordem, volte ao
              comparativo financeiro.
            </p>
            {propostasSel.length ? (
              <ol className="cmp-lista-apresentacao">
                {propostasSel.map((id) => {
                  const op = propostas.find((o) => o.id === id);
                  return (
                    <li key={id}>
                      {op ? `${op.operadora} — ${op.plano_nome}` : id}
                    </li>
                  );
                })}
              </ol>
            ) : (
              <p className="erro">Nenhuma proposta selecionada no Comparativo.</p>
            )}
          </fieldset>

          <div className="acoes-linha">
            <button type="button" className="secundario" onClick={handlePreview} disabled={carregando}>
              Pré-visualizar modelo
            </button>
            <button type="button" onClick={handleGerarHtml} disabled={carregando || !propostasSel.length}>
              Gerar HTML
            </button>
          </div>

          {preview && (
            <div className="preview-apresentacao">
              <h4>Pré-visualização ({preview.modo})</h4>
              <p>Seções: {preview.secoes_regime?.length ?? 0}</p>
              {preview.modo === "beneficiario" && (
                <p>Beneficiários: {preview.beneficiarios?.length ?? 0}</p>
              )}
            </div>
          )}

          {entregavel && (
            <div className="ok">
              <p>HTML gerado — hash: {entregavel.hash_conteudo.slice(0, 16)}…</p>
              {entregavel.aviso_dados_pessoais && (
                <p className="aviso">{entregavel.aviso_dados_pessoais}</p>
              )}
              <a
                href={`/api/estudos/${estudoId}/entregaveis/${entregavel.entregavel_id}/html`}
                target="_blank"
                rel="noreferrer"
              >
                Abrir / baixar HTML
              </a>
            </div>
          )}
        </section>
      )}

      {snapshots.length > 1 && (
        <details className="historico-snapshots">
          <summary>Histórico de snapshots ({snapshots.length})</summary>
          <ul>
            {snapshots.map((s) => (
              <li key={s.id}>
                {s.estado} — {s.id.slice(0, 8)}… — {s.criado_em}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
