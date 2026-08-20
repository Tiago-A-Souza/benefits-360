import { useCallback, useEffect, useState } from "react";
import {
  aprovarSnapshot,
  gerarApresentacaoHtml,
  obterSnapshot,
  obterSnapshotAprovado,
  previewApresentacao,
} from "../api";

export function formatarDataAprovacao(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  return d.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
}

export function AvisoAprovacaoSuperada({ superado }) {
  if (!superado) return null;
  const quando = formatarDataAprovacao(superado.aprovado_em);
  const revisor = superado.revisor_nome || "revisor não informado";
  return (
    <section className="gov-banner gov-banner--superado" role="alert">
      <h3 className="gov-banner-titulo">A aprovação caiu</h3>
      <p>
        O rascunho mudou depois da aprovação de <strong>{revisor}</strong>
        {quando ? ` em ${quando}` : ""}. Confirme o comparativo de novo para
        congelar os valores atuais.
      </p>
    </section>
  );
}

export function StatusAprovacaoVigente({ status }) {
  const aprov = status?.aprovacao;
  if (!status?.aprovado || !aprov) return null;
  const quando = formatarDataAprovacao(aprov.aprovado_em);
  return (
    <section className="gov-banner gov-banner--aprovado">
      <h3 className="gov-banner-titulo">Aprovação em vigor</h3>
      <p>
        Revisado por <strong>{aprov.revisor_nome}</strong>
        {quando ? ` em ${quando}` : ""}.
        {aprov.auto_aprovacao ? " Autoaprovação provisória." : ""}
      </p>
      {status.hash_sha256 && (
        <p className="muted gov-hash">
          Hash do snapshot: {status.hash_sha256.slice(0, 16)}…
        </p>
      )}
    </section>
  );
}

export function AprovacaoLocalForm({
  snapshotId,
  hashSha256,
  estudoId,
  carregando,
  onAprovado,
  onErro,
}) {
  const [revisor, setRevisor] = useState("");
  const [justificativa, setJustificativa] = useState("");
  const [autoAprovacao, setAutoAprovacao] = useState(false);
  const [confirmo, setConfirmo] = useState(false);
  const [detalhesAbertos, setDetalhesAbertos] = useState(false);
  const [enviando, setEnviando] = useState(false);

  async function handleAprovar() {
    if (!snapshotId) return;
    setEnviando(true);
    onErro?.(null);
    try {
      await aprovarSnapshot(estudoId, snapshotId, {
        revisor_nome: revisor,
        justificativa: justificativa || null,
        confirmo_conteudo: confirmo,
        auto_aprovacao: autoAprovacao,
      });
      setConfirmo(false);
      onAprovado?.();
    } catch (e) {
      onErro?.(e.message);
    } finally {
      setEnviando(false);
    }
  }

  const ocupado = carregando || enviando;

  return (
    <section className="secao-inline cartao--aviso gov-secao">
      <h3>Aprovação local provisória</h3>
      <p className="muted">
        O comparativo foi congelado. Atestar a revisão libera a exportação ao
        cliente.
      </p>
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
      <button type="button" onClick={handleAprovar} disabled={ocupado}>
        {enviando ? "Aprovando…" : "Aprovar snapshot"}
      </button>
      {hashSha256 && (
        <>
          <button
            type="button"
            className="secundario"
            onClick={() => setDetalhesAbertos(!detalhesAbertos)}
          >
            {detalhesAbertos ? "Ocultar" : "Ver"} detalhes técnicos (hash)
          </button>
          {detalhesAbertos && (
            <pre className="json-preview">Hash: {hashSha256}</pre>
          )}
        </>
      )}
    </section>
  );
}

export function ExportarHtmlApresentacao({
  estudoId,
  snapshotId,
  propostas,
  propostasSel,
  carregando,
  onErro,
}) {
  const [modo, setModo] = useState("resumo");
  const [preview, setPreview] = useState(null);
  const [entregavel, setEntregavel] = useState(null);
  const [ocupado, setOcupado] = useState(false);

  async function handlePreview() {
    if (!snapshotId) {
      onErro?.("Aprove o snapshot antes de pré-visualizar a apresentação.");
      return;
    }
    setOcupado(true);
    onErro?.(null);
    try {
      const vm = await previewApresentacao(estudoId, snapshotId, {
        modo,
        propostas_selecionadas: [],
        ressalvas: [],
      });
      setPreview(vm);
    } catch (e) {
      onErro?.(e.message);
    } finally {
      setOcupado(false);
    }
  }

  async function handleGerarHtml() {
    if (!snapshotId) {
      onErro?.("Snapshot aprovado necessário.");
      return;
    }
    if (modo === "beneficiario") {
      const ok = window.confirm(
        "O arquivo HTML conterá nomes de beneficiários. Confirma a geração para armazenamento privado local?"
      );
      if (!ok) return;
    }
    setOcupado(true);
    onErro?.(null);
    try {
      const res = await gerarApresentacaoHtml(estudoId, snapshotId, {
        modo,
        propostas_selecionadas: [],
        ressalvas: [],
      });
      setEntregavel(res);
    } catch (e) {
      onErro?.(e.message);
    } finally {
      setOcupado(false);
    }
  }

  const busy = carregando || ocupado;

  return (
    <section className="secao-inline gov-secao">
      <h3>Exportar HTML</h3>
      <fieldset>
        <legend>Visão do documento</legend>
        <label className="radio">
          <input
            type="radio"
            name={`modo-html-${snapshotId || "gov"}`}
            value="resumo"
            checked={modo === "resumo"}
            onChange={() => setModo("resumo")}
          />
          Resumo executivo
        </label>
        <label className="radio">
          <input
            type="radio"
            name={`modo-html-${snapshotId || "gov"}`}
            value="faixas"
            checked={modo === "faixas"}
            onChange={() => setModo("faixas")}
          />
          Faixas etárias (sem nomes)
        </label>
        <label className="radio">
          <input
            type="radio"
            name={`modo-html-${snapshotId || "gov"}`}
            value="beneficiario"
            checked={modo === "beneficiario"}
            onChange={() => setModo("beneficiario")}
          />
          Por beneficiário (contém nomes)
        </label>
      </fieldset>

      <fieldset>
        <legend>Propostas no material</legend>
        <p className="muted cmp-previa-lead">
          Seleção definida na confirmação do comparativo. Para alterar planos ou
          ordem, volte à matriz e confirme de novo.
        </p>
        {propostasSel.length ? (
          <ol className="cmp-lista-apresentacao">
            {propostasSel.map((id) => {
              const op = propostas.find((o) => o.id === id);
              return (
                <li key={id}>{op ? `${op.operadora} — ${op.plano_nome}` : id}</li>
              );
            })}
          </ol>
        ) : (
          <p className="erro">Nenhuma proposta selecionada no Comparativo.</p>
        )}
      </fieldset>

      <div className="acoes-linha">
        <button type="button" className="secundario" onClick={handlePreview} disabled={busy}>
          Pré-visualizar modelo
        </button>
        <button type="button" onClick={handleGerarHtml} disabled={busy || !propostasSel.length}>
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
  );
}

export default function GovernancaComparativo({ estudoId, rascunho, confirmado, onAtualizado }) {
  const [status, setStatus] = useState(null);
  const [erro, setErro] = useState(null);

  const recarregar = useCallback(async () => {
    if (!estudoId) return;
    try {
      const st = await obterSnapshotAprovado(estudoId);
      setStatus(st);
      if (st?.estado === "candidato" && st.snapshot_id && !st.hash_sha256) {
        const snap = await obterSnapshot(estudoId, st.snapshot_id);
        setStatus({ ...st, hash_sha256: snap.hash_sha256 });
      }
    } catch (e) {
      setErro(e.message);
    }
  }, [estudoId]);

  useEffect(() => {
    recarregar();
  }, [recarregar, confirmado]);

  const propostas = rascunho?.opcoes_proposta || [];
  const propostasSel =
    rascunho?.confirmacao_comparativo?.ordem ||
    rascunho?.selecao_apresentacao?.ordem ||
    [];

  const mostrarSuperado = status?.estado === "superado" || (!status?.aprovado && status?.superado && !confirmado);
  const mostrarForma =
    confirmado && status?.estado === "candidato" && status?.snapshot_id;
  const mostrarAprovado = Boolean(status?.aprovado) && Boolean(confirmado);

  async function handleAprovado() {
    await recarregar();
    onAtualizado?.();
  }

  return (
    <div className="gov-comparativo">
      {erro && <p className="erro">{erro}</p>}
      {mostrarSuperado && <AvisoAprovacaoSuperada superado={status.superado || status} />}
      {mostrarAprovado && <StatusAprovacaoVigente status={status} />}
      {mostrarForma && (
        <AprovacaoLocalForm
          estudoId={estudoId}
          snapshotId={status.snapshot_id}
          hashSha256={status.hash_sha256}
          carregando={false}
          onAprovado={handleAprovado}
          onErro={setErro}
        />
      )}
      {mostrarAprovado && (
        <ExportarHtmlApresentacao
          estudoId={estudoId}
          snapshotId={status.snapshot_id}
          propostas={propostas}
          propostasSel={propostasSel}
          carregando={false}
          onErro={setErro}
        />
      )}
    </div>
  );
}
