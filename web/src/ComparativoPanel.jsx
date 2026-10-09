import { useEffect, useMemo, useState } from "react";
import {
  calcularEstudo,
  confirmarComparativo,
  obterPendencias,
  obterRascunho,
  obterSnapshotAprovado,
  salvarSelecaoApresentacao,
} from "./api";
import ComparativoExperiencia from "./comparativo/ComparativoExperiencia";
import BloqueiosComparativo from "./comparativo/BloqueiosComparativo";
import GovernancaComparativo from "./apresentacao/GovernancaComparativo";
import { comparativoConfirmado, confirmacaoEmVigor, confirmacaoPrecisaRefazer } from "./fluxo/stepStatus";
import { tituloPasso } from "./fluxo/passos";

export default function ComparativoPanel({ estudoId, etapaIndice = 5, totalEtapas = 5, onAtualizado }) {
  const [pendencias, setPendencias] = useState([]);
  const [rascunho, setRascunho] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [confirmando, setConfirmando] = useState(false);
  const [formatoIncompativel, setFormatoIncompativel] = useState(false);
  const [statusGov, setStatusGov] = useState(null);
  const [avisoSelecaoAlterada, setAvisoSelecaoAlterada] = useState(false);

  async function recarregarContextoLocal() {
    if (!estudoId) return;
    const [p, r, st] = await Promise.all([
      obterPendencias(estudoId).catch(() => []),
      obterRascunho(estudoId).catch(() => null),
      obterSnapshotAprovado(estudoId).catch(() => null),
    ]);
    setPendencias(p);
    setRascunho(r);
    setStatusGov(st);
    setFormatoIncompativel(Boolean(st?.formato_incompativel));
  }

  useEffect(() => {
    recarregarContextoLocal();
  }, [estudoId, etapaIndice]);

  const rotuloEtapa = useMemo(
    () => tituloPasso(rascunho, "comparativo"),
    [rascunho]
  );

  const precisaReconfirmar = confirmacaoPrecisaRefazer(rascunho, statusGov);
  const jaConfirmado = confirmacaoEmVigor(rascunho, statusGov);

  async function handleSelecaoSalva() {
    const estavaConfirmado = comparativoConfirmado(rascunho) && !formatoIncompativel;
    await recarregarContextoLocal();
    if (estavaConfirmado) {
      setAvisoSelecaoAlterada(true);
    }
    onAtualizado?.();
  }

  async function handleCalcular() {
    setCarregando(true);
    setErro(null);
    setResultado(null);
    setAvisoSelecaoAlterada(false);
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
      const st = await obterSnapshotAprovado(estudoId).catch(() => null);
      setStatusGov(st);
      setFormatoIncompativel(Boolean(st?.formato_incompativel));
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
      setAvisoSelecaoAlterada(false);
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
  const redeNaoRevisada = !rascunho?.selecao_rede?.revisada;

  return (
    <section className="etapa-fluxo cmp-pagina">
      {redeNaoRevisada && (
        <div className="notice notice--amber" role="status">
          <div className="notice-icon" aria-hidden="true">
            !
          </div>
          <div>
            <b>Rede credenciada não revisada</b>
            <p>
              Aviso informativo — não bloqueia cálculo nem exportação. Vale a lista padrão
              (principais da base) até você confirmar a seleção na etapa Rede.
            </p>
          </div>
        </div>
      )}
      {!resultado?.calculo_realizado && (
        <>
          <div className="page-head">
            <div>
              <div className="page-kicker">
                Etapa {etapaIndice} de {totalEtapas}
              </div>
              <h1>Comparativo</h1>
              <p className="lead">
                Revise as propostas calculadas, escolha o que entra no documento e confirme o
                comparativo antes da exportação.
              </p>
            </div>
            <div className="page-head-acoes">
              {jaConfirmado && (
                <span className="badge badge--ok">Comparativo confirmado</span>
              )}
              {!jaConfirmado && pronto && alertas.length === 0 && (
                <span className="badge badge--ok">Pronto para calcular</span>
              )}
              {!jaConfirmado && pronto && alertas.length > 0 && (
                <span className="badge badge--alerta">
                  {alertas.length} alerta(s) — cálculo permitido
                </span>
              )}
              {!jaConfirmado && !pronto && (
                <span className="badge badge--alerta">
                  {bloqueios.length} pendência(s) bloqueante(s)
                </span>
              )}
            </div>
          </div>

          {!jaConfirmado && !pronto && (
            <div className="notice notice--amber">
              <div className="notice-icon" aria-hidden="true">
                !
              </div>
              <div>
                <b>Pendências bloqueantes</b>
                <ul className="cmp-pre-lista">
                  {bloqueios.slice(0, 4).map((p, i) => (
                    <li key={i}>
                      {p.codigo ? `${p.codigo} · ` : ""}
                      {p.titulo}
                    </li>
                  ))}
                  {bloqueios.length > 4 && (
                    <li className="muted">+ {bloqueios.length - 4} outra(s)</li>
                  )}
                </ul>
              </div>
            </div>
          )}

          <div className="action-bar">
            <div className="action-left">
              <span className="action-note">
                Processa todas as propostas dos cenários · selecione, confirme e aprove para exportar
              </span>
            </div>
            <div className="action-right">
              <button
                type="button"
                className="cmp-btn-principal"
                onClick={handleCalcular}
                disabled={carregando || !pronto}
              >
                {carregando ? "Calculando…" : "Calcular comparativo"}
              </button>
            </div>
          </div>
        </>
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
          Comparativo confirmado — aprove abaixo para liberar a exportação, ou recalcule para revisar
          a matriz.
        </p>
      )}

      {precisaReconfirmar && !resultado?.calculo_realizado && (
        <p className="aviso cmp-confirmacao-banner" role="status">
          A aprovação caiu. Calcule e confirme o comparativo de novo para congelar os valores
          atuais e reaprovar.
        </p>
      )}

      {resultado?.calculo_realizado && (
        <ComparativoExperiencia
          estudoId={estudoId}
          resultado={resultado}
          rascunho={rascunho}
          etapaIndice={etapaIndice}
          totalEtapas={totalEtapas}
          rotuloEtapa={rotuloEtapa}
          confirmado={jaConfirmado}
          precisaReconfirmar={precisaReconfirmar}
          confirmando={confirmando}
          onConfirmar={handleConfirmar}
          onRecalcular={handleCalcular}
          onSelecaoSalva={handleSelecaoSalva}
          avisoSelecaoAlterada={avisoSelecaoAlterada}
          recalculando={carregando}
        />
      )}

      <GovernancaComparativo
        estudoId={estudoId}
        rascunho={rascunho}
        confirmado={jaConfirmado}
        onAtualizado={onAtualizado}
      />
    </section>
  );
}
