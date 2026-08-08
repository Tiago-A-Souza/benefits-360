import { useCallback, useEffect, useMemo, useState } from "react";
import {
  listarExtracoesCotacao,
  obterConferenciaSiscor,
  obterEstudo,
  obterPendencias,
  obterRascunho,
} from "./api";
import ComparativoPanel from "./ComparativoPanel";
import ConfigEstudo from "./ConfigEstudo";
import EstudoCabecalho from "./EstudoCabecalho";
import HistoricoPanel from "./HistoricoPanel";
import MeusEstudos from "./MeusEstudos";
import PlanosSelecionadosPanel from "./PlanosSelecionadosPanel";
import PropostaPanel from "./PropostaPanel";
import RevisaoApresentacaoPanel from "./RevisaoApresentacaoPanel";
import DiagnosticoPanel from "./DiagnosticoPanel";
import SiscorPanel from "./SiscorPanel";
import { avisoAvancoCotacoesPendentes } from "./fluxo/cotacoesPendentes";
import { passosVisiveis } from "./fluxo/passos";
import { proximaEtapaDisponivel, statusEtapa } from "./fluxo/stepStatus";

export default function App() {
  const [tela, setTela] = useState("lista");
  const [estudoId, setEstudoId] = useState(null);
  const [passo, setPasso] = useState(1);
  const [resumo, setResumo] = useState(null);
  const [ctxFluxo, setCtxFluxo] = useState({
    conferencia: null,
    rascunho: null,
    extracoes: [],
    pendencias: [],
  });
  const [historicoAberto, setHistoricoAberto] = useState(false);
  const [cestaGlobal, setCestaGlobal] = useState([]);

  const recarregarContexto = useCallback(async () => {
    if (!estudoId) return;
    const [r, p, c, e, res] = await Promise.all([
      obterRascunho(estudoId).catch(() => null),
      obterPendencias(estudoId).catch(() => []),
      obterConferenciaSiscor(estudoId).catch(() => null),
      listarExtracoesCotacao(estudoId).catch(() => ({ extracoes: [] })),
      obterEstudo(estudoId).catch(() => null),
    ]);
    if (res) setResumo(res);
    setCtxFluxo({
      rascunho: r,
      pendencias: p,
      conferencia: c,
      extracoes: e.extracoes || [],
    });
  }, [estudoId]);

  useEffect(() => {
    if (!estudoId || tela !== "fluxo") return;
    obterEstudo(estudoId)
      .then(setResumo)
      .catch(() => setResumo(null));
    recarregarContexto();
  }, [estudoId, tela, recarregarContexto]);

  const passos = useMemo(
    () => passosVisiveis(ctxFluxo.rascunho),
    [ctxFluxo.rascunho]
  );

  useEffect(() => {
    if (passo > passos.length && passos.length > 0) {
      setPasso(passos.length);
    }
  }, [passo, passos.length]);

  function entrarEstudo(id) {
    setEstudoId(id);
    setPasso(1);
    setTela("fluxo");
    setHistoricoAberto(false);
    setCestaGlobal([]);
  }

  function voltarLista() {
    setTela("lista");
    setEstudoId(null);
    setResumo(null);
    setPasso(1);
  }

  const statusPassos = useMemo(() => {
    const map = {};
    for (let i = 1; i <= passos.length; i += 1) {
      map[i] = statusEtapa(i, ctxFluxo);
    }
    return map;
  }, [ctxFluxo, passos.length]);

  const chavePassoAtual = passos[passo - 1]?.chave;

  function irProximo() {
    if (passo >= passos.length || !proximaEtapaDisponivel(passo, ctxFluxo)) return;
    if (chavePassoAtual === "cotacoes") {
      const aviso = avisoAvancoCotacoesPendentes(
        ctxFluxo.extracoes,
        ctxFluxo.rascunho?.opcoes_proposta || []
      );
      if (aviso && !window.confirm(aviso)) return;
    }
    setPasso(passo + 1);
  }

  function irAnterior() {
    if (passo > 1) setPasso(passo - 1);
  }

  if (tela === "lista") {
    return (
      <div className="pagina pagina--larga pagina--lista">
        <MeusEstudos onContinuar={entrarEstudo} />
        <DiagnosticoPanel />
      </div>
    );
  }

  return (
    <div className="pagina pagina--fluxo pagina--larga">
      <div className="fluxo-shell">
        <EstudoCabecalho
          resumo={resumo}
          onTrocarEstudo={voltarLista}
          onHistorico={() => setHistoricoAberto((v) => !v)}
        />

        <nav className="wizard wizard--operacional" aria-label="Etapas do estudo">
          {passos.map((p) => {
            const st = statusPassos[p.ordem];
            return (
              <button
                key={p.chave}
                type="button"
                className={[
                  "wizard-passo",
                  passo === p.ordem ? "ativo" : "",
                  st?.concluida ? "concluida" : "",
                ]
                  .filter(Boolean)
                  .join(" ")}
                onClick={() => setPasso(p.ordem)}
              >
                <span className="wizard-num">{p.ordem}</span>
                <span className="wizard-titulo">{p.titulo}</span>
                {st?.pendencia && !st.concluida && (
                  <span className="wizard-pendencia">{st.pendencia}</span>
                )}
              </button>
            );
          })}
        </nav>

        <main className="fluxo-conteudo">
          {chavePassoAtual === "base" && (
            <SiscorPanel estudoId={estudoId} onAtualizado={recarregarContexto} />
          )}
          {chavePassoAtual === "plano" && (
            <ConfigEstudo estudoId={estudoId} onSalvo={recarregarContexto} />
          )}
          {chavePassoAtual === "cotacoes" && (
            <PropostaPanel
              estudoId={estudoId}
              cestaGlobal={cestaGlobal}
              setCestaGlobal={setCestaGlobal}
              opcoesComparativo={ctxFluxo.rascunho?.opcoes_proposta || []}
              subgruposAtuais={ctxFluxo.rascunho?.subgrupos_atuais || []}
              onSalvo={recarregarContexto}
            />
          )}
          {chavePassoAtual === "selecionados" && (
            <PlanosSelecionadosPanel estudoId={estudoId} onSalvo={recarregarContexto} />
          )}
          {chavePassoAtual === "comparativo" && (
            <ComparativoPanel estudoId={estudoId} onAtualizado={recarregarContexto} />
          )}
          {chavePassoAtual === "apresentacao" && (
            <RevisaoApresentacaoPanel estudoId={estudoId} />
          )}
        </main>

        {historicoAberto && (
          <aside className="painel-complementar">
            <HistoricoPanel estudoId={estudoId} />
          </aside>
        )}

        <div className="wizard-nav">
          {passo > 1 && (
            <button type="button" className="secundario" onClick={irAnterior}>
              ← Etapa anterior
            </button>
          )}
          <div className="wizard-nav-direita">
            {!proximaEtapaDisponivel(passo, ctxFluxo) && statusPassos[passo]?.pendencia && (
              <p className="wizard-nav-pendencia">{statusPassos[passo].pendencia}</p>
            )}
            {proximaEtapaDisponivel(passo, ctxFluxo) && statusPassos[passo]?.aviso && (
              <p className="wizard-nav-aviso">{statusPassos[passo].aviso}</p>
            )}
            {passo < passos.length && (
              <button
                type="button"
                onClick={irProximo}
                disabled={!proximaEtapaDisponivel(passo, ctxFluxo)}
                title={
                  !proximaEtapaDisponivel(passo, ctxFluxo)
                    ? statusPassos[passo]?.pendencia || "Conclua esta etapa primeiro"
                    : statusPassos[passo]?.aviso || undefined
                }
              >
                Próxima etapa →
              </button>
            )}
          </div>
        </div>
        <DiagnosticoPanel />
      </div>
    </div>
  );
}
