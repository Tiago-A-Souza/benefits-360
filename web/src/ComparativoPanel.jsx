import { useEffect, useMemo, useState } from "react";
import {
  calcularEstudo,
  confirmarComparativo,
  obterPendencias,
  obterRascunho,
  salvarSelecaoApresentacao,
} from "./api";
import ComparativoExperiencia from "./comparativo/ComparativoExperiencia";
import BloqueiosComparativo from "./comparativo/BloqueiosComparativo";
import { comparativoConfirmado } from "./fluxo/stepStatus";
import { tituloPasso } from "./fluxo/passos";

export default function ComparativoPanel({ estudoId, onAtualizado }) {
  const [pendencias, setPendencias] = useState([]);
  const [rascunho, setRascunho] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);

  async function recarregarContextoLocal() {
    if (!estudoId) return;
    const [p, r] = await Promise.all([
      obterPendencias(estudoId).catch(() => []),
      obterRascunho(estudoId).catch(() => null),
    ]);
    setPendencias(p);
    setRascunho(r);
  }

  useEffect(() => {
    recarregarContextoLocal();
  }, [estudoId]);

  const rotuloEtapa = useMemo(
    () => tituloPasso(rascunho, "comparativo"),
    [rascunho]
  );

  const jaConfirmado = comparativoConfirmado(rascunho);

  async function handleCalcular() {
    setCarregando(true);
    setErro(null);
    setResultado(null);
    try {
      const p = await obterPendencias(estudoId);
      setPendencias(p);
      const bloqueios = p.filter((x) => x.tipo === "bloqueio");
      if (bloqueios.length) {
        setErro("Complete as pendências indicadas antes de calcular.");
        return;
      }
      const data = await calcularEstudo(estudoId);
      const r = await obterRascunho(estudoId);
      setRascunho(r);
      const idsCalculados = (data.propostas || []).map((p) => p.opcao_id).filter(Boolean);
      const ordemSalva = r?.selecao_apresentacao?.ordem || [];
      if (data.calculo_realizado && idsCalculados.length && !ordemSalva.length) {
        await salvarSelecaoApresentacao(estudoId, idsCalculados);
        data.propostas_apresentacao = idsCalculados;
        const r2 = await obterRascunho(estudoId);
        setRascunho(r2);
      } else if (ordemSalva.length) {
        data.propostas_apresentacao = ordemSalva;
      }
      setResultado(data);
      onAtualizado?.();
      if (data.consistencia && !data.consistencia.consistente) {
        if (!data.consistencia.bloqueios?.length) {
          setErro(data.consistencia.mensagem);
        }
      }
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  async function handleConfirmar(opcaoIds) {
    if (!opcaoIds?.length) return;
    setConfirmando(true);
    setErro(null);
    try {
      await confirmarComparativo(
        estudoId,
        resultado?.hash_comparativo || null,
        opcaoIds
      );
      await recarregarContextoLocal();
      onAtualizado?.();
    } catch (e) {
      setErro(e.message);
    } finally {
      setConfirmando(false);
    }
  }

  const bloqueios = pendencias.filter((p) => p.tipo === "bloqueio");
  const alertas = pendencias.filter((p) => p.tipo === "alerta");
  const pronto = bloqueios.length === 0;

  return (
    <section className="cmp-pagina">
      {!resultado?.calculo_realizado && (
        <header className="cmp-hero cmp-hero--pre cmp-hero--compact">
          <div className="cmp-hero-linha cmp-hero-linha--titulo">
            <div className="cmp-hero-identidade">
              <span className="cmp-etapa">{rotuloEtapa}</span>
              <h2 className="cmp-hero-titulo">Comparativo financeiro</h2>
            </div>
          </div>

          <div className="cmp-hero-linha cmp-hero-linha--pre">
            <div className="cmp-pre-status">
              {jaConfirmado && (
                <span className="cmp-pre-badge cmp-pre-badge--ok">
                  Comparativo confirmado — pode avançar para Apresentação
                </span>
              )}
              {!jaConfirmado && pronto && alertas.length === 0 && (
                <span className="cmp-pre-badge cmp-pre-badge--ok">Pronto para calcular</span>
              )}
              {!jaConfirmado && pronto && alertas.length > 0 && (
                <span className="cmp-pre-badge cmp-pre-badge--alerta">
                  {alertas.length} alerta(s) — cálculo permitido
                </span>
              )}
              {!jaConfirmado && !pronto && (
                <div className="cmp-pre-bloqueios">
                  <span className="cmp-pre-badge cmp-pre-badge--erro">
                    {bloqueios.length} pendência(s) bloqueante(s)
                  </span>
                  <ul className="cmp-pre-lista">
                    {bloqueios.slice(0, 2).map((p, i) => (
                      <li key={i}>{p.titulo}</li>
                    ))}
                    {bloqueios.length > 2 && (
                      <li className="muted">+ {bloqueios.length - 2} outra(s)</li>
                    )}
                  </ul>
                </div>
              )}
            </div>
            <button
              type="button"
              className="cmp-btn-principal cmp-btn-calcular"
              onClick={handleCalcular}
              disabled={carregando || !pronto}
            >
              {carregando ? "Calculando…" : "Calcular comparativo"}
            </button>
          </div>

          <p className="cmp-pre-hint muted">
            Processa todas as propostas dos cenários · selecione e confirme para liberar Apresentação
          </p>
        </header>
      )}

      {erro && <p className="erro cmp-erro-global">{erro}</p>}

      {resultado?.consistencia && !resultado.calculo_realizado && (
        <BloqueiosComparativo consistencia={resultado.consistencia} rascunho={rascunho} />
      )}

      {resultado && !resultado.calculo_realizado && !resultado.consistencia?.bloqueios?.length && (
        <p className="erro cmp-erro-global">
          O comparativo não está completo — corrija a inconsistência antes de avançar.
        </p>
      )}

      {jaConfirmado && !resultado?.calculo_realizado && (
        <p className="ok cmp-confirmacao-banner">
          Comparativo confirmado — use «Próxima etapa» para ir à Apresentação.
        </p>
      )}

      {resultado?.calculo_realizado && (
        <ComparativoExperiencia
          estudoId={estudoId}
          resultado={resultado}
          rascunho={rascunho}
          rotuloEtapa={rotuloEtapa}
          confirmado={jaConfirmado}
          confirmando={confirmando}
          onConfirmar={handleConfirmar}
          onRecalcular={handleCalcular}
          recalculando={carregando}
        />
      )}
    </section>
  );
}
