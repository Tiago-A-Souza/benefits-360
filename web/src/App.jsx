import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  listarExtracoesCotacao,
  obterConferenciaSiscor,
  obterEstudo,
  obterPendencias,
  obterRascunho,
  obterResumoPlanoAtual,
} from "./api";
import { textoReajusteContrato } from "./fluxo/resumoPlanoUi";
import ComparativoPanel from "./ComparativoPanel";
import ConfigEstudo from "./ConfigEstudo";
import EstudoCabecalho from "./EstudoCabecalho";
import HistoricoPanel from "./HistoricoPanel";
import MeusEstudos from "./MeusEstudos";
import PlanosSelecionadosPanel from "./PlanosSelecionadosPanel";
import RedeSelecaoPanel from "./rede/RedeSelecaoPanel";
import NavegacaoFerramentas from "./NavegacaoFerramentas";
import SimularRede from "./simularRede/SimularRede";
import CotacoesRpa from "./cotacoes/CotacoesRpa";
import CotacoesNativa from "./cotacoes/nativa/CotacoesNativa";
import { nativaLigada } from "./cotacoes/nativa/regrasNova";
import ProvaRpaDireto from "./cotacoes/ProvaRpaDireto";
import PropostaPanel from "./PropostaPanel";
import SiscorPanel from "./SiscorPanel";
import { avisoAvancoCotacoesPendentes } from "./fluxo/cotacoesPendentes";
import { linhaEstadoPasso } from "./fluxo/linhasEstado";
import { passosVisiveis } from "./fluxo/passos";
import { proximaEtapaClicavel } from "./fluxo/avancoEtapa";
import { proximaEtapaDisponivel, statusEtapa } from "./fluxo/stepStatus";
import TelaLogin from "./login/TelaLogin";
import ErrorBoundary from "./erro/ErrorBoundary";
import { asArray } from "./util/colecao";
import {
  EVENTO_NAO_AUTORIZADO,
  obterSessao,
  ouvirSessao,
  sairSessao,
} from "./login/sessao";

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
    resumoPlanoAtual: null,
  });
  const [historicoAberto, setHistoricoAberto] = useState(false);
  // Simular Rede é uma consulta avulsa: não cria nem altera estudo.
  const [simulando, setSimulando] = useState(false);
  const [cotacoesRpa, setCotacoesRpa] = useState(false);
  const [provaRpa, setProvaRpa] = useState(() => {
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("prova-rpa") === "1";
  });
  const [cotacoesNativa, setCotacoesNativa] = useState(() => nativaLigada());
  const [logado, setLogado] = useState(false);
  const [sessaoPronta, setSessaoPronta] = useState(false);

  function abrirCotacoes() {
    setCotacoesRpa(false);
    setCotacoesNativa(true);
  }
  const [cestaGlobal, setCestaGlobal] = useState([]);
  const avancarEtapaRef = useRef(null);
  const registrarAvancoEtapa = useCallback((fn) => {
    avancarEtapaRef.current = fn;
    return () => {
      if (avancarEtapaRef.current === fn) avancarEtapaRef.current = null;
    };
  }, []);

  const recarregarContexto = useCallback(async () => {
    if (!estudoId) return;
    const [r, p, c, e, res, resumoPlano] = await Promise.all([
      obterRascunho(estudoId).catch(() => null),
      obterPendencias(estudoId).catch(() => []),
      obterConferenciaSiscor(estudoId).catch(() => null),
      listarExtracoesCotacao(estudoId).catch(() => ({ extracoes: [] })),
      obterEstudo(estudoId).catch(() => null),
      obterResumoPlanoAtual(estudoId).catch(() => null),
    ]);
    if (res) setResumo(res);
    const resumoPlanoAtual = r?.formato === "novo" ? null : resumoPlano;
    setCtxFluxo({
      rascunho: r && typeof r === "object" ? r : null,
      pendencias: asArray(p),
      conferencia: c && typeof c === "object" ? c : null,
      extracoes: asArray(e && e.extracoes ? e.extracoes : e),
      resumoPlanoAtual,
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

  async function irProximo() {
    if (passo >= passos.length) return;
    const confirmar = avancarEtapaRef.current;
    if (typeof confirmar === "function") {
      const ok = await confirmar();
      if (!ok) return;
      await recarregarContexto();
    } else if (!proximaEtapaDisponivel(passo, ctxFluxo)) {
      return;
    }
    if (chavePassoAtual === "cotacoes") {
      const aviso = avisoAvancoCotacoesPendentes(
        ctxFluxo.extracoes,
        ctxFluxo.rascunho?.opcoes_proposta || []
      );
      if (aviso && !window.confirm(aviso)) return;
    }
    setPasso((atual) => atual + 1);
  }

  function irAnterior() {
    if (passo > 1) setPasso(passo - 1);
  }

  const nPlanosVigentes = ctxFluxo.rascunho?.subgrupos_atuais?.length || 0;
  const totalBaseComparacao = ctxFluxo.resumoPlanoAtual?.total_reajustado_reais;
  const legendaReajusteBase = textoReajusteContrato(ctxFluxo.resumoPlanoAtual);

  useEffect(() => {
    let vivo = true;
    obterSessao()
      .then((s) => {
        if (!vivo) return;
        setLogado(Boolean(s));
        setSessaoPronta(true);
      })
      .catch(() => {
        if (!vivo) return;
        setLogado(false);
        setSessaoPronta(true);
      });
    const parar = ouvirSessao((s) => setLogado(Boolean(s)));
    function aoNaoAutorizado() {
      void sairSessao().then(() => {
        if (vivo) setLogado(false);
      });
    }
    window.addEventListener(EVENTO_NAO_AUTORIZADO, aoNaoAutorizado);
    return () => {
      vivo = false;
      parar();
      window.removeEventListener(EVENTO_NAO_AUTORIZADO, aoNaoAutorizado);
    };
  }, []);

  const sair = useCallback(() => {
    void sairSessao().then(() => setLogado(false));
  }, []);

  if (!sessaoPronta) {
    return (
      <div className="app-shell app-shell-carregando">
        <p className="lista-carregando">Carregando o Benefits…</p>
      </div>
    );
  }

  if (!logado) {
    return <TelaLogin onEntrar={() => setLogado(true)} />;
  }

  if (provaRpa) {
    return (
      <div className="lista-shell">
        <ProvaRpaDireto
          onFechar={() => {
            setProvaRpa(false);
            const u = new URL(window.location.href);
            u.searchParams.delete("prova-rpa");
            window.history.replaceState({}, "", u.pathname + u.search);
          }}
        />
      </div>
    );
  }

  if (cotacoesNativa) {
    const emEstudo = tela === "fluxo" && estudoId;
    const irEstudos = () => {
      if (emEstudo) voltarLista();
      setCotacoesNativa(false);
    };
    return (
      <div className="app-shell">
        <EstudoCabecalho resumo={null} onSair={sair} />
        <ErrorBoundary
          contexto="Cotações"
          modo="painel"
          onVoltarEstudos={irEstudos}
          onSair={sair}
          resetKey="cotacoes"
        >
          <CotacoesNativa
            onMeusEstudos={irEstudos}
            onSimularRede={() => {
              setCotacoesNativa(false);
              setSimulando(true);
            }}
            onVoltarEstudo={emEstudo ? () => setCotacoesNativa(false) : undefined}
            rotuloEstudo={emEstudo ? resumo?.empresa || resumo?.titulo : undefined}
          />
        </ErrorBoundary>
      </div>
    );
  }

  if (cotacoesRpa) {
    const emEstudo = tela === "fluxo" && estudoId;
    return (
      <div className="app-shell">
        <EstudoCabecalho resumo={null} onSair={sair} />
        <ErrorBoundary contexto="Cotações (iframe)" modo="painel" onVoltarEstudos={voltarLista} onSair={sair}>
          <CotacoesRpa
            onMeusEstudos={() => {
              if (emEstudo) voltarLista();
              setCotacoesRpa(false);
            }}
            onSimularRede={() => {
              setCotacoesRpa(false);
              setSimulando(true);
            }}
            onVoltarEstudo={emEstudo ? () => setCotacoesRpa(false) : undefined}
            rotuloEstudo={emEstudo ? resumo?.empresa || resumo?.titulo : undefined}
          />
        </ErrorBoundary>
      </div>
    );
  }

  if (simulando) {
    const emEstudo = tela === "fluxo" && estudoId;
    return (
      <div className="app-shell">
        <EstudoCabecalho resumo={null} onSair={sair} />
        <ErrorBoundary contexto="Simular rede" modo="painel" onVoltarEstudos={voltarLista} onSair={sair}>
          <SimularRede
            onMeusEstudos={() => {
              if (emEstudo) voltarLista();
              setSimulando(false);
            }}
            onCotacoes={() => {
              setSimulando(false);
              abrirCotacoes();
            }}
            onVoltarEstudo={emEstudo ? () => setSimulando(false) : undefined}
            rotuloEstudo={emEstudo ? resumo?.empresa || resumo?.titulo : undefined}
          />
        </ErrorBoundary>
      </div>
    );
  }

  if (tela === "lista") {
    return (
      <div className="app-shell">
        <EstudoCabecalho resumo={null} onSair={sair} />
        <ErrorBoundary contexto="Meus estudos" modo="painel" onVoltarEstudos={voltarLista} onSair={sair}>
          <MeusEstudos
            onContinuar={entrarEstudo}
            onSimularRede={() => setSimulando(true)}
            onCotacoes={abrirCotacoes}
          />
        </ErrorBoundary>
      </div>
    );
  }

  return (
    <div className="app-shell">
      <EstudoCabecalho
        resumo={resumo}
        onTrocarEstudo={voltarLista}
        onHistorico={() => setHistoricoAberto((v) => !v)}
        onSair={sair}
      />

      <div className="app-body">
        <aside className="app-sidebar">
          {resumo && (
            <div className="side-card">
              <div className="study-eyebrow">
                {resumo.formato_exibicao || "Renovação"}
                {resumo.titulo ? ` · ${resumo.titulo}` : ""}
              </div>
              <div className="side-title">{resumo.empresa || resumo.titulo}</div>
              <div className="side-meta">
                {resumo.beneficiarios_rotulo || "0 beneficiários"}
                {nPlanosVigentes
                  ? ` · ${nPlanosVigentes} ${nPlanosVigentes === 1 ? "plano vigente" : "planos vigentes"}`
                  : ""}
              </div>
              {totalBaseComparacao && (
                <div className="side-value">
                  <small>Base para comparação</small>
                  <strong className="num">{totalBaseComparacao}</strong>
                  {legendaReajusteBase && (
                    <span className="side-meta">{legendaReajusteBase}</span>
                  )}
                </div>
              )}
            </div>
          )}

          <div className="steps-label">Etapas do estudo</div>
          <nav className="wizard wizard--operacional" aria-label="Etapas do estudo">
            <ol className="steps">
              {passos.map((p) => {
                const st = statusPassos[p.ordem];
                const estado = linhaEstadoPasso(p.chave, { ...ctxFluxo, resumo });
                return (
                  <li
                    key={p.chave}
                    className={[
                      "step",
                      passo === p.ordem ? "active" : "",
                      st?.concluida ? "done" : "",
                    ]
                      .filter(Boolean)
                      .join(" ")}
                  >
                    <button
                      type="button"
                      className={[
                        "wizard-passo",
                        passo === p.ordem ? "ativo" : "",
                        st?.concluida ? "concluida" : "",
                      ]
                        .filter(Boolean)
                        .join(" ")}
                      onClick={() => setPasso(p.ordem)}
                      aria-current={passo === p.ordem ? "step" : undefined}
                    >
                      <span className="wizard-num">{p.ordem}</span>
                      <span className="wizard-copy">
                        <span className="wizard-titulo">{p.titulo}</span>
                        {estado && <small className="wizard-estado">{estado}</small>}
                      </span>
                    </button>
                  </li>
                );
              })}
            </ol>
          </nav>

          <div className="side-bottom">
            <NavegacaoFerramentas
              ativo={null}
              onMeusEstudos={voltarLista}
              onSimularRede={() => setSimulando(true)}
              onCotacoes={abrirCotacoes}
            />
          </div>
        </aside>

        <div className="app-main">
          <main className="fluxo-conteudo">
            {chavePassoAtual === "base" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (base)`}
                modo="painel"
                resetKey={`${estudoId}-base`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <SiscorPanel
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  resumoPlanoAtual={ctxFluxo.resumoPlanoAtual}
                  onAtualizado={recarregarContexto}
                  onRegistrarAvanco={registrarAvancoEtapa}
                />
              </ErrorBoundary>
            )}
            {chavePassoAtual === "plano" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (plano)`}
                modo="painel"
                resetKey={`${estudoId}-plano`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <ConfigEstudo
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  onSalvo={recarregarContexto}
                  onRegistrarAvanco={registrarAvancoEtapa}
                />
              </ErrorBoundary>
            )}
            {chavePassoAtual === "cotacoes" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (cotacoes)`}
                modo="painel"
                resetKey={`${estudoId}-cotacoes`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <PropostaPanel
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  cestaGlobal={cestaGlobal}
                  setCestaGlobal={setCestaGlobal}
                  opcoesComparativo={ctxFluxo.rascunho?.opcoes_proposta || []}
                  extracoes={ctxFluxo.extracoes || []}
                  subgruposAtuais={ctxFluxo.rascunho?.subgrupos_atuais || []}
                  onSalvo={recarregarContexto}
                  onRegistrarAvanco={registrarAvancoEtapa}
                />
              </ErrorBoundary>
            )}
            {chavePassoAtual === "selecionados" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (selecionados)`}
                modo="painel"
                resetKey={`${estudoId}-selecionados`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <PlanosSelecionadosPanel
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  onSalvo={recarregarContexto}
                  onRegistrarAvanco={registrarAvancoEtapa}
                />
              </ErrorBoundary>
            )}
            {chavePassoAtual === "rede" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (rede)`}
                modo="painel"
                resetKey={`${estudoId}-rede`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <RedeSelecaoPanel
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  onRegistrarAvanco={registrarAvancoEtapa}
                />
              </ErrorBoundary>
            )}
            {chavePassoAtual === "comparativo" && (
              <ErrorBoundary
                contexto={`Etapa ${passo} (comparativo)`}
                modo="painel"
                resetKey={`${estudoId}-comparativo`}
                onVoltarEstudos={voltarLista}
                onSair={sair}
              >
                <ComparativoPanel
                  estudoId={estudoId}
                  etapaIndice={passo}
                  totalEtapas={passos.length}
                  rascunhoFluxo={ctxFluxo.rascunho}
                  onAtualizado={recarregarContexto}
                />
              </ErrorBoundary>
            )}

            <footer className="wizard-nav" aria-label="Navegação entre etapas">
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
                    disabled={
                      !proximaEtapaClicavel(
                        chavePassoAtual,
                        passo,
                        ctxFluxo,
                        proximaEtapaDisponivel
                      )
                    }
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
            </footer>
          </main>

          {historicoAberto && (
            <aside className="painel-complementar">
              <ErrorBoundary contexto="Histórico" modo="painel" resetKey={estudoId} onVoltarEstudos={voltarLista} onSair={sair}>
                <HistoricoPanel estudoId={estudoId} />
              </ErrorBoundary>
            </aside>
          )}
        </div>
      </div>
    </div>
  );
}
