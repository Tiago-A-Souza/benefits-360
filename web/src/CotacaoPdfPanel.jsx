import { useEffect, useState } from "react";
import {
  aplicarExtracaoCotacao,
  confirmarLoteExtracao,
  importarCotacaoPdf,
  listarExtracoesCotacao,
  obterExtracaoCotacao,
} from "./api";
import { centavosParaReaisExibicao } from "./money";

function CampoExtracao({ campo, onConfirmar }) {
  if (!campo || campo.estado === "ausente") return null;
  const valor =
    campo.centavos != null
      ? centavosParaReaisExibicao(campo.centavos)
      : campo.texto || campo.inteiro || campo.data || "—";
  return (
    <li className={`campo-extracao campo-extracao--${campo.estado}`}>
      <strong>{campo.rotulo}</strong>: {valor}
      {campo.evidencia?.trecho && (
        <p className="muted evidencia">Evidência: {campo.evidencia.trecho.slice(0, 120)}</p>
      )}
      {!campo.confirmado && (
        <button type="button" className="link" onClick={() => onConfirmar(campo.id)}>
          Confirmar
        </button>
      )}
      {campo.confirmado && <span className="ok"> ✓ confirmado</span>}
    </li>
  );
}

export default function CotacaoPdfPanel({ estudoId, onAplicado }) {
  const [extracoes, setExtracoes] = useState([]);
  const [sel, setSel] = useState(null);
  const [detalhe, setDetalhe] = useState(null);
  const [erro, setErro] = useState(null);
  const [msg, setMsg] = useState(null);
  const [carregando, setCarregando] = useState(false);

  function recarregar() {
    listarExtracoesCotacao(estudoId)
      .then((r) => setExtracoes(r.extracoes || []))
      .catch(() => setExtracoes([]));
  }

  useEffect(() => {
    if (!estudoId) return;
    recarregar();
  }, [estudoId]);

  useEffect(() => {
    if (!sel) {
      setDetalhe(null);
      return;
    }
    obterExtracaoCotacao(estudoId, sel)
      .then(setDetalhe)
      .catch((e) => setErro(e.message));
  }, [estudoId, sel]);

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setCarregando(true);
    setErro(null);
    try {
      const res = await importarCotacaoPdf(estudoId, file);
      setMsg(
        res.sucesso
          ? `PDF identificado (${res.operadora || res.estado}) — ${res.opcoes_encontradas} proposta(s).`
          : `PDF recebido (${res.estado}). Revise ou use entrada manual.`
      );
      recarregar();
      setSel(res.extracao_id);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCarregando(false);
      e.target.value = "";
    }
  }

  async function confirmarCampo(campoId) {
    await fetch(`/api/estudos/${estudoId}/extracao-cotacao/${sel}/campos/${campoId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmado: true }),
    });
    const d = await obterExtracaoCotacao(estudoId, sel);
    setDetalhe(d);
  }

  async function handleConfirmarLote() {
    await confirmarLoteExtracao(estudoId, sel);
    const d = await obterExtracaoCotacao(estudoId, sel);
    setDetalhe(d);
    setMsg("Campos sem alerta confirmados em lote.");
  }

  async function handleAplicar() {
    const res = await aplicarExtracaoCotacao(estudoId, sel);
    setMsg(`${res.opcoes_adicionadas} proposta(s) adicionada(s) ao estudo.`);
    onAplicado?.();
  }

  return (
    <section className="cartao cartao--interno">
      <h3>Importar cotações (PDF)</h3>
      <p className="muted">
        Envie PDFs de Porto, SulAmérica, Amil, Bradesco ou Omint. Nenhum valor é confirmado
        automaticamente.
      </p>
      <label className="upload-label">
        <input type="file" accept="application/pdf" onChange={handleUpload} disabled={carregando} />
        {carregando ? "Processando PDF…" : "Selecionar PDF de cotação"}
      </label>

      {extracoes.length > 0 && (
        <ul className="lista-extracoes">
          {extracoes.map((ex) => (
            <li key={ex.id}>
              <button type="button" className="link" onClick={() => setSel(ex.id)}>
                {ex.documento?.operadora_detectada || "Documento"} — {ex.estado} (v{ex.versao})
              </button>
            </li>
          ))}
        </ul>
      )}

      {detalhe && (
        <>
          {detalhe.alertas?.map((a, i) => (
            <p key={i} className="alerta">
              {a.mensagem}
            </p>
          ))}
          {detalhe.opcoes?.map((op) => (
            <div key={op.id} className="cartao cartao--interno">
              <h4>{op.plano_nome?.texto || "Proposta"}</h4>
              <ul className="campos-extracao">
                <CampoExtracao campo={op.premio_saude} onConfirmar={confirmarCampo} />
                <CampoExtracao campo={op.iof} onConfirmar={confirmarCampo} />
                <CampoExtracao campo={op.total_recorrente} onConfirmar={confirmarCampo} />
              </ul>
              {op.reconciliacao?.divergencias?.length > 0 && (
                <div className="pendencias-box">
                  <strong>Divergências financeiras</strong>
                  <ul>
                    {op.reconciliacao.divergencias.map((d, i) => (
                      <li key={i}>{d.descricao}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          ))}
          <div className="acoes-lote">
            <button type="button" className="secundario" onClick={handleConfirmarLote}>
              Confirmar lote (sem alerta)
            </button>
            <button type="button" onClick={handleAplicar}>
              Aplicar propostas confirmadas
            </button>
          </div>
        </>
      )}
      {msg && <p className="ok">{msg}</p>}
      {erro && <p className="erro">{erro}</p>}
    </section>
  );
}
