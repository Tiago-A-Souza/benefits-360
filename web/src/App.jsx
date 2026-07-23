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
import SiscorPanel from "./SiscorPanel";
import { PASSOS } from "./constants";
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
    const [r, p, c, e] = await Promise.all([
      obterRascunho(estudoId).catch(() => null),
      obterPendencias(estudoId).catch(() => []),
      obterConferenciaSiscor(estudoId).catch(() => null),
      listarExtracoesCotacao(estudoId).catch(() => ({ extracoes: [] })),
    ]);
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
    for (const p of PASSOS) {
      map[p.id] = statusEtapa(p.id, ctxFluxo);
    }
    return map;
  }, [ctxFluxo]);

  function irProximo() {
    if (passo < PASSOS.length && proximaEtapaDisponivel(passo, ctxFluxo)) {
      setPasso(passo + 1);
    }
  }

  function irAnterior() {
    if (passo > 1) setPasso(passo - 1);
  }

  if (tela === "lista") {
    return (
      <div className="pagina pagina--fluxo pagina--larga">
        <MeusEstudos onContinuar={entrarEstudo} />
      </div>
    );
  }

  return (
    <div className="pagina pagina--fluxo pagina--larga">
      <EstudoCabecalho
        resumo={resumo}
        onTrocarEstudo={voltarLista}
        onHistorico={() => setHistoricoAberto((v) => !v)}
      />

      <nav className="wizard wizard--operacional" aria-label="Etapas do estudo">
        {PASSOS.map((p) => {
          const st = statusPassos[p.id];
          return (
            <button
              key={p.id}
              type="button"
              className={[
                "wizard-passo",
                passo === p.id ? "ativo" : "",
                st?.concluida ? "concluida" : "",
              ]
                .filter(Boolean)
                .join(" ")}
              onClick={() => setPasso(p.id)}
            >
              <span className="wizard-num">{p.id}</span>
              <span className="wizard-titulo">{p.titulo}</span>
              {st?.pendencia && !st.concluida && (
                <span className="wizard-pendencia">{st.pendencia}</span>
              )}
            </button>
          );
        })}
      </nav>

      {passo === 1 && (
        <SiscorPanel estudoId={estudoId} onAtualizado={recarregarContexto} />
      )}
      {passo === 2 && (
        <ConfigEstudo estudoId={estudoId} onSalvo={recarregarContexto} />
      )}
      {passo === 3 && (
        <PropostaPanel
          estudoId={estudoId}
          cestaGlobal={cestaGlobal}
          setCestaGlobal={setCestaGlobal}
          opcoesComparativo={ctxFluxo.rascunho?.opcoes_proposta || []}
          onSalvo={recarregarContexto}
        />
      )}
      {passo === 4 && (
        <PlanosSelecionadosPanel estudoId={estudoId} onSalvo={recarregarContexto} />
      )}
      {passo === 5 && <ComparativoPanel estudoId={estudoId} />}
      {passo === 6 && <RevisaoApresentacaoPanel estudoId={estudoId} />}

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
        {passo < PASSOS.length && (
          <button
            type="button"
            onClick={irProximo}
            disabled={!proximaEtapaDisponivel(passo, ctxFluxo)}
            title={
              !proximaEtapaDisponivel(passo, ctxFluxo)
                ? statusPassos[passo]?.pendencia || "Conclua esta etapa primeiro"
                : undefined
            }
          >
            Próxima etapa →
          </button>
        )}
      </div>
    </div>
  );
}
