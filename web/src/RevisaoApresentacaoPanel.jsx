import { useCallback, useEffect, useState } from "react";
import {
  gerarSnapshot,
  listarSnapshots,
  obterComparativoSnapshot,
  obterRascunho,
  obterSnapshot,
  obterSnapshotAprovado,
} from "./api";
import ComparativoExperiencia from "./comparativo/ComparativoExperiencia";
import {
  AprovacaoLocalForm,
  AvisoAprovacaoSuperada,
  ExportarHtmlApresentacao,
  StatusAprovacaoVigente,
} from "./apresentacao/GovernancaComparativo";

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
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [detalhesAbertos, setDetalhesAbertos] = useState(false);
  const [matrizCongelada, setMatrizCongelada] = useState(null);

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
      setMatrizCongelada(null);
      setErro(null);
      const ops = rascunho.opcoes_proposta || [];
      setPropostas(ops);
      const candidato = lista.find((s) => s.estado === "candidato");
      const snapId = status.aprovado
        ? status.snapshot_id
        : status.estado === "candidato"
          ? status.snapshot_id || candidato?.id
          : candidato?.id;
      if (snapId) {
        const snap = await obterSnapshot(estudoId, snapId);
        setSnapshotAtual(snap);
        try {
          const congelado = await obterComparativoSnapshot(estudoId, snapId);
          setMatrizCongelada(congelado);
          const ordemSnap =
            congelado.propostas_apresentacao ||
            snap.payload?.propostas_apresentacao ||
            rascunho.selecao_apresentacao?.ordem ||
            [];
          if (ordemSnap.length) {
            setPropostasSel(ordemSnap);
          } else if (!propostasSel.length && ops.length) {
            setPropostasSel(ops.map((o) => o.id));
          }
        } catch (eCmp) {
          setMatrizCongelada(null);
          const ordemSnap =
            snap.payload?.propostas_apresentacao ||
            rascunho.selecao_apresentacao?.ordem ||
            [];
          if (ordemSnap.length) {
            setPropostasSel(ordemSnap);
          }
          setErro(eCmp.message);
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

  const comparativo = matrizCongelada;

  return (
    <div className="cartao">
      <h2>Revisão e apresentação</h2>
      <p className="sub">
        Gere snapshot candidato, revise o conteúdo congelado, aprove localmente e produza HTML
        autocontido. Aprovação provisória — ainda não substitui autenticação corporativa.
      </p>

      {erro && <p className="erro">{erro}</p>}
      {aprovado?.estado === "superado" && (
        <AvisoAprovacaoSuperada superado={aprovado.superado || aprovado} />
      )}
      {aprovado?.aprovado && <StatusAprovacaoVigente status={aprovado} />}

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
                  {comparativo.formato === "novo" || !comparativo.totais.atual_mensal_reais
                    ? `Proposta: ${comparativo.totais.proposta_mensal_reais}`
                    : `Total atual: ${comparativo.totais.atual_mensal_reais} · Proposta: ${comparativo.totais.proposta_mensal_reais} · Diferença: ${comparativo.totais.diferenca_mensal_reais}`}
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
        <AprovacaoLocalForm
          estudoId={estudoId}
          snapshotId={snapshotAtual.id}
          hashSha256={snapshotAtual.hash_sha256}
          carregando={carregando}
          onAprovado={recarregar}
          onErro={setErro}
        />
      )}

      {aprovado?.aprovado && matrizCongelada && (
        <section className="secao-inline">
          <h3>4. Comparativo congelado</h3>
          <p className="muted">
            Esta matriz lê o payload do snapshot aprovado. Alterar o rascunho ao vivo não
            muda estes valores até gerar e aprovar um novo snapshot.
          </p>
          <ComparativoExperiencia
            resultado={matrizCongelada}
            rotuloEtapa="Apresentação — snapshot aprovado"
            origemCongelada
          />
        </section>
      )}

      {aprovado?.aprovado && (
        <ExportarHtmlApresentacao
          estudoId={estudoId}
          snapshotId={aprovado.snapshot_id}
          propostas={propostas}
          propostasSel={propostasSel}
          carregando={carregando}
          onErro={setErro}
        />
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
