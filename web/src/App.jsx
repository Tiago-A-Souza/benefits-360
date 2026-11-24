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
import HistoricoPanel from "./HistoricoPanel";
import AppChrome from "./layout/AppChrome";
import BarraLateral from "./layout/BarraLateral";
import { RotuloNav } from "./layout/IconeNav";
import MeusEstudos from "./MeusEstudos";
import PlanosSelecionadosPanel from "./PlanosSelecionadosPanel";
import RedeSelecaoPanel from "./rede/RedeSelecaoPanel";
import NavegacaoFerramentas from "./NavegacaoFerramentas";
import SimularRede from "./simularRede/SimularRede";
import CotacoesNativa from "./cotacoes/nativa/CotacoesNativa";
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
import TelaNaoEncontrado from "./erro/TelaNaoEncontrado";
import { asArray } from "./util/colecao";
import {
  EVENTO_NAO_AUTORIZADO,
  obterSessao,
  ouvirSessao,
  sairSessao,
} from "./login/sessao";
import {
  HASH_COTACOES_LISTA,
  HASH_ESTUDOS,
  HASH_SIMULAR,
  ehErroSemAcesso,
  hashEstudo,
  irPara,
  normalizarHashInicial,
  parseHashAtual,
} from "./rotas";

const CTX_VAZIO = {
  conferencia: null,
  rascunho: null,
  extracoes: [],
  pendencias: [],
  resumoPlanoAtual: null,
};

export default function App() {
  const [rota, setRota] = useState(parseHashAtual);
  const [resumo, setResumo] = useState(null);
  const [estudoStatus, setEstudoStatus] = useState("idle");
  const [recargaEstudo, setRecargaEstudo] = useState(0);
  const [ctxFluxo, setCtxFluxo] = useState(CTX_VAZIO);
  const [historicoAberto, setHistoricoAberto] = useState(false);
  const [provaRpa, setProvaRpa] = useState(() => {
    if (typeof window === "undefined") return false;
    return new URLSearchParams(window.location.search).get("prova-rpa") === "1";
  });
  const [logado, setLogado] = useState(false);
  const [sessaoPronta, setSessaoPronta] = useState(false);
  const [cestaGlobal, setCestaGlobal] = useState([]);
  const [retornoEstudo, setRetornoEstudo] = useState(null);
  const avancarEtapaRef = useRef(null);

  const estudoId = rota.area === "estudo" ? rota.estudoId : null;
  const passo = rota.area === "estudo" ? rota.passo : 1;

  function abrirCotacoes() {
    irPara(HASH_COTACOES_LISTA);
  }

  const registrarAvancoEtapa = useCallback((fn) => {
    avancarEtapaRef.current = fn;
    return () => {
      if (avancarEtapaRef.current === fn) avancarEtapaRef.current = null;
    };
  }, []);

  const recarregarContexto = useCallback(async (id) => {
    const alvo = id || estudoId;
    if (!alvo) return;
    const [r, p, c, e, res, resumoPlano] = await Promise.all([
      obterRascunho(alvo).catch(() => null),
      obterPendencias(alvo).catch(() => []),
      obterConferenciaSiscor(alvo).catch(() => null),
      listarExtracoesCotacao(alvo).catch(() => ({ extracoes: [] })),
      obterEstudo(alvo).catch(() => null),
      obterResumoPlanoAtual(alvo).catch(() => null),
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
  const recarregarRef = useRef(recarregarContexto);
  recarregarRef.current = recarregarContexto;

  useEffect(() => {
    const sync = () => {
      const proxima = parseHashAtual();
      setRota((atual) => {
        if (
          atual.area === proxima.area &&
          atual.estudoId === proxima.estudoId &&
          atual.passo === proxima.passo &&
          atual.motivo === proxima.motivo
        ) {
          return atual;
        }
        return proxima;
      });
    };
    window.addEventListener("hashchange", sync);
    normalizarHashInicial();
    return () => window.removeEventListener("hashchange", sync);
  }, []);

  useEffect(() => {
    if (rota.area === "estudos") {
      setRetornoEstudo(null);
      setHistoricoAberto(false);
      setCestaGlobal([]);
    }
  }, [rota.area]);

  useEffect(() => {
    if (rota.area !== "estudo" || !estudoId) return;
    const rotulo = resumo?.empresa || resumo?.titulo || "";
    setRetornoEstudo((atual) => {
      if (
        atual &&
        atual.id === estudoId &&
        atual.passo === passo &&
        (rotulo ? atual.rotulo === rotulo : Boolean(atual.rotulo))
      ) {
        return atual;
      }
      return { id: estudoId, passo, rotulo: rotulo || atual?.rotulo || "" };
    });
  }, [rota.area, estudoId, passo, resumo]);

  useEffect(() => {
    if (rota.area !== "estudo" || !estudoId) {
      if (rota.area !== "estudo") {
        setEstudoStatus("idle");
        setResumo(null);
        setCtxFluxo(CTX_VAZIO);
      }
      return undefined;
    }
    let vivo = true;
    setEstudoStatus("carregando");
    setResumo(null);
    setCtxFluxo(CTX_VAZIO);
    obterEstudo(estudoId)
      .then(async (r) => {
        if (!vivo) return;
        setResumo(r);
        await recarregarRef.current(estudoId);
        if (!vivo) return;
        setEstudoStatus("ok");
      })
      .catch((err) => {
        if (!vivo) return;
        setResumo(null);
        setCtxFluxo(CTX_VAZIO);
        setEstudoStatus(ehErroSemAcesso(err) ? "sem_acesso" : "erro");
      });
    return () => {
      vivo = false;
    };
  }, [rota.area, estudoId, recargaEstudo]);

  const passos = useMemo(
    () => passosVisiveis(ctxFluxo.rascunho),
    [ctxFluxo.rascunho]
  );

  useEffect(() => {
    if (rota.area !== "estudo" || !estudoId || estudoStatus !== "ok") return;
    if (passo > passos.length && passos.length > 0) {
      irPara(hashEstudo(estudoId, passos.length), { replace: true });
    }
  }, [rota.area, estudoId, passo, passos.length, estudoStatus]);

  function entrarEstudo(id) {
    setHistoricoAberto(false);
    setCestaGlobal([]);
    irPara(hashEstudo(id, 1));
  }

  function voltarLista() {
    irPara(HASH_ESTUDOS);
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
    if (!estudoId || passo >= passos.length) return;
    const confirmar = avancarEtapaRef.current;
    if (typeof confirmar === "function") {
      const ok = await confirmar();
      if (!ok) return;
      await recarregarContexto(estudoId);
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
    irPara(hashEstudo(estudoId, passo + 1));
  }

  function irAnterior() {
    if (estudoId && passo > 1) irPara(hashEstudo(estudoId, passo - 1));
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

  const irSimular = () => irPara(HASH_SIMULAR);
  const hashRetorno = retornoEstudo ? hashEstudo(retornoEstudo.id, retornoEstudo.passo) : null;

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
      <AppChrome onSair={sair}>
        <div className="lista-shell">
          <BarraLateral />
          <div className="lista-main">
            <ProvaRpaDireto
              onFechar={() => {
                setProvaRpa(false);
                const u = new URL(window.location.href);
                u.searchParams.delete("prova-rpa");
                window.history.replaceState({}, "", u.pathname + u.search);
              }}
            />
          </div>
        </div>
      </AppChrome>
    );
  }

  if (rota.area === "invalida") {
    return (
      <AppChrome onSair={sair}>
        <TelaNaoEncontrado
          tipo="rota"
          onVoltarEstudos={voltarLista}
          onSimularRede={irSimular}
          onCotacoes={abrirCotacoes}
        />
      </AppChrome>
    );
  }

  if (rota.area === "estudo" && estudoStatus === "sem_acesso") {
    return (
      <AppChrome onSair={sair}>
        <TelaNaoEncontrado
          tipo="estudo"
          onVoltarEstudos={voltarLista}
          onSimularRede={irSimular}
          onCotacoes={abrirCotacoes}
        />
      </AppChrome>
    );
  }

  if (rota.area === "estudo" && estudoStatus === "erro") {
    return (
      <AppChrome onSair={sair}>
        <TelaNaoEncontrado
          tipo="erro"
          onVoltarEstudos={voltarLista}
          onSimularRede={irSimular}
          onCotacoes={abrirCotacoes}
          onTentar={() => setRecargaEstudo((n) => n + 1)}
        />
      </AppChrome>
    );
  }

  if (rota.area === "cotacoes") {
    return (
      <AppChrome onSair={sair}>
        <ErrorBoundary
          contexto="Cotações"
          modo="painel"
          onVoltarEstudos={voltarLista}
          onSair={sair}
          resetKey="cotacoes"
        >
          <CotacoesNativa
            hashVoltarEstudo={hashRetorno}
            rotuloEstudo={retornoEstudo?.rotulo}
          />
        </ErrorBoundary>
      </AppChrome>
    );
  }

  if (rota.area === "simular") {
    return (
      <AppChrome onSair={sair}>
        <ErrorBoundary contexto="Simular rede" modo="painel" onVoltarEstudos={voltarLista} onSair={sair}>
          <SimularRede
            onMeusEstudos={voltarLista}
            onCotacoes={abrirCotacoes}
            onVoltarEstudo={hashRetorno ? () => irPara(hashRetorno) : undefined}
            rotuloEstudo={retornoEstudo?.rotulo}
          />
        </ErrorBoundary>
      </AppChrome>
    );
  }

  if (rota.area === "estudos" || rota.area !== "estudo") {
    return (
      <AppChrome onSair={sair}>
        <ErrorBoundary contexto="Meus estudos" modo="painel" onVoltarEstudos={voltarLista} onSair={sair}>
          <MeusEstudos
            onContinuar={entrarEstudo}
            onSimularRede={irSimular}
            onCotacoes={abrirCotacoes}
          />
        </ErrorBoundary>
      </AppChrome>
    );
  }

  if (estudoStatus === "carregando" || estudoStatus === "idle") {
    return (
      <AppChrome onSair={sair}>
        <div className="app-body app-shell-carregando">
          <BarraLateral />
          <p className="lista-carregando">Carregando o estudo…</p>
        </div>
      </AppChrome>
    );
  }

  return (
    <AppChrome onSair={sair}>
      <div className="app-body">
        <BarraLateral>
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
                      onClick={() => irPara(hashEstudo(estudoId, p.ordem))}
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
              onSimularRede={irSimular}
              onCotacoes={abrirCotacoes}
            />
            <ul className="lista-filtros">
              <li>
                <button
                  type="button"
                  aria-pressed={historicoAberto}
                  onClick={() => setHistoricoAberto((v) => !v)}
                >
                  <RotuloNav icone="historico">Histórico</RotuloNav>
                </button>
              </li>
            </ul>
          </div>
        </BarraLateral>

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
                  onAtualizado={() => recarregarContexto(estudoId)}
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
                  onSalvo={() => recarregarContexto(estudoId)}
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
                  onSalvo={() => recarregarContexto(estudoId)}
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
                  onSalvo={() => recarregarContexto(estudoId)}
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
                  onAtualizado={() => recarregarContexto(estudoId)}
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
    </AppChrome>
  );
}
