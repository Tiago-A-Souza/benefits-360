import { useCallback, useEffect, useState } from "react";
import NavegacaoFerramentas from "../../NavegacaoFerramentas";
import { chamarRpa, ouvirEventosRpa, urlBaseRpa } from "../rpaClient";
import Andamento from "./Andamento";
import BannerPendencias from "./BannerPendencias";
import Conexoes from "./Conexoes";
import FaixaCodigo from "./FaixaCodigo";
import FaixaProblemaLogin from "./FaixaProblemaLogin";
import FaixaTrabalho from "./FaixaTrabalho";
import ListaCotacoes from "./ListaCotacoes";
import NovaCotacao from "./NovaCotacao";
import { TELAS_ROBO_NAO_PORTADAS } from "./regrasNova";
import "./nativa.css";

function lerHash() {
  const h = (typeof window !== "undefined" && window.location.hash) || "";
  const qh = h.includes("?") ? h.slice(h.indexOf("?") + 1) : "";
  const qs = new URLSearchParams(qh);
  const mAnd = h.match(/^#\/andamento\/(\d+)/);
  if (mAnd) return { tela: "andamento", id: Number(mAnd[1]), cnpj: null, op: null };
  if (h.startsWith("#/conexoes")) return { tela: "conexoes", id: null, cnpj: null, op: qs.get("op") };
  if (h.startsWith("#/cotacoes")) return { tela: "cotacoes", id: null, cnpj: null, op: null };
  const mNova = h.match(/^#\/nova(?:\?(.*))?/);
  if (mNova) {
    const q = mNova[1] ? new URLSearchParams(mNova[1]) : new URLSearchParams();
    const cnpjQuery =
      typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("cnpj") : null;
    return { tela: "nova", id: null, cnpj: q.get("cnpj") || cnpjQuery, op: null };
  }
  return { tela: "cotacoes", id: null, cnpj: null, op: null };
}

export default function CotacoesNativa({
  onMeusEstudos,
  onSimularRede,
  onCotacoesIframe,
  onVoltarEstudo,
  rotuloEstudo,
}) {
  const [{ tela, id, cnpj, op }, setRota] = useState(lerHash);
  const [operadoras, setOperadoras] = useState(null);
  const [indisponiveis, setIndisponiveis] = useState([]);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [conexao, setConexao] = useState({});
  const [problemaLogin, setProblemaLogin] = useState(null);
  const [trabalhoAtual, setTrabalhoAtual] = useState(null);
  const [ultimaEtapa, setUltimaEtapa] = useState(null);
  const [naFila, setNaFila] = useState([]);
  const [reloadOps, setReloadOps] = useState(0);
  const [reloadLista, setReloadLista] = useState(0);
  const urlRobo = urlBaseRpa();

  const ir = useCallback((hash) => {
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      u.hash = hash.startsWith("#") ? hash.slice(1) : hash;
      window.history.replaceState({}, "", u);
    }
    setRota(lerHash());
  }, []);

  useEffect(() => {
    const onHash = () => setRota(lerHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    let vivo = true;
    setErro(null);
    Promise.all([chamarRpa("GET", "/api/operadoras"), chamarRpa("GET", "/api/estado").catch(() => null)])
      .then(([d, estado]) => {
        if (!vivo) return;
        setOperadoras(d);
        setIndisponiveis((estado && estado.operadoras_indisponiveis) || []);
        const cx = {};
        for (const o of d || []) cx[o.id] = o.conexao || "desconectado";
        setConexao((c) => ({ ...cx, ...c }));
        if (estado && estado.robo) {
          setTrabalhoAtual(estado.robo.atual || null);
          setNaFila(estado.robo.na_fila || []);
          if (estado.robo.ultima_etapa) setUltimaEtapa(estado.robo.ultima_etapa);
        }
      })
      .catch((e) => vivo && setErro(e.message || "O robô de cotações não está no ar."));
    return () => {
      vivo = false;
    };
  }, [reloadOps]);

  useEffect(() => {
    const { fechar } = ouvirEventosRpa((ev) => {
      if (ev.tipo === "conexao") {
        setConexao((c) => ({ ...c, [ev.operadora]: ev.status }));
      }
      if (ev.tipo === "codigo_necessario") {
        setConexao((c) => ({ ...c, [ev.operadora]: "aguardando_codigo" }));
      }
      if (ev.tipo === "login_problema") {
        setProblemaLogin({
          operadora: ev.operadora,
          motivo: ev.motivo,
          mensagem: ev.mensagem,
        });
      }
      if (ev.tipo === "login_ok") {
        setProblemaLogin((p) => (p && p.operadora === ev.operadora ? null : p));
      }
      if (ev.tipo === "etapa") setUltimaEtapa(ev);
      if (ev.tipo === "cotacao" || (ev.tipo === "trabalho" && ev.status !== "rodando")) {
        setReloadLista((n) => n + 1);
      }
      if (ev.tipo === "parando") {
        setTrabalhoAtual((t) => (t && t.id === ev.trabalho ? { ...t, parando: true } : t));
      }
      if (ev.tipo === "trabalho") {
        if (ev.status === "rodando") {
          setTrabalhoAtual({ id: ev.trabalho, titulo: ev.titulo, modo: ev.modo });
        }
        if (["concluido", "erro", "cancelado", "interrompido"].includes(ev.status)) {
          setTrabalhoAtual((t) => (t && t.id === ev.trabalho ? null : t));
        }
      }
    });
    return () => fechar();
  }, []);

  useEffect(() => {
    if (!aviso) return;
    const t = setTimeout(() => setAviso(null), aviso.tipo === "erro" ? 9000 : 5000);
    return () => clearTimeout(t);
  }, [aviso]);

  function mostrarAviso(texto, tipo) {
    setAviso({ texto, tipo: tipo || "info" });
  }

  function irIframe() {
    if (typeof window !== "undefined") {
      const u = new URL(window.location.href);
      u.searchParams.set("cotacoes-iframe", "1");
      u.hash = "";
      window.history.replaceState({}, "", u);
    }
    onCotacoesIframe?.();
  }

  const noAndamentoDeste = tela === "andamento" && trabalhoAtual && Number(id) === Number(trabalhoAtual.id);
  const ativoMenu =
    tela === "nova" || tela === "andamento" ? "nova" : tela === "conexoes" ? "conexoes" : "cotacoes";

  return (
    <div className="lista-shell nativa-shell">
      <aside className="lista-rail app-sidebar">
        <NavegacaoFerramentas
          ativo="cotacoes"
          onMeusEstudos={onMeusEstudos}
          onSimularRede={onSimularRede}
          onCotacoes={() => ir("#/cotacoes")}
          onVoltarEstudo={onVoltarEstudo}
          rotuloEstudo={rotuloEstudo}
        />
        <nav className="nav-ferramentas nativa-subnav" aria-label="Cotações">
          <p className="lista-rail-lb">Cotações</p>
          <ul className="lista-filtros">
            <li>
              <button type="button" aria-pressed={ativoMenu === "nova"} onClick={() => ir("#/nova")}>
                Nova cotação
              </button>
            </li>
            <li>
              <button type="button" aria-pressed={ativoMenu === "cotacoes"} onClick={() => ir("#/cotacoes")}>
                Cotações
              </button>
            </li>
            <li>
              <button type="button" aria-pressed={ativoMenu === "conexoes"} onClick={() => ir("#/conexoes")}>
                Conexões
              </button>
            </li>
          </ul>
          <p className="lista-rail-lb">No robô local</p>
          <ul className="lista-filtros">
            {TELAS_ROBO_NAO_PORTADAS.map((t) => (
              <li key={t.hash}>
                <a href={`${urlRobo}/${t.hash}`} target="_blank" rel="noreferrer" title={`Abre ${t.rotulo} no robô (127.0.0.1:8600) em outra aba`}>
                  {t.rotulo}
                </a>
              </li>
            ))}
          </ul>
          <p className="muted nativa-flag-hint">
            Telas ainda não portadas abrem o robô local em outra aba. Para comparar com o iframe antigo:{" "}
            <button type="button" className="link" onClick={irIframe}>
              ?cotacoes-iframe=1
            </button>
            .
          </p>
        </nav>
      </aside>

      <main className="lista-main nativa-main">
        {problemaLogin ? (
          <FaixaProblemaLogin
            problema={problemaLogin}
            operadoras={operadoras || []}
            onAbrirLogin={(opId) => {
              setProblemaLogin(null);
              ir(`#/conexoes?op=${opId}`);
            }}
            onFechar={() => setProblemaLogin(null)}
          />
        ) : (
          <FaixaCodigo conexao={conexao} operadoras={operadoras || []} aviso={mostrarAviso} />
        )}
        {!noAndamentoDeste ? (
          <FaixaTrabalho
            trabalho={trabalhoAtual}
            etapa={ultimaEtapa}
            operadoras={operadoras || []}
            onAcompanhar={(tid) => ir(`#/andamento/${tid}`)}
          />
        ) : null}
        {aviso ? (
          <div className={`nativa-toast${aviso.tipo === "erro" ? " nativa-toast--erro" : ""}`} role="status">
            {aviso.texto}
          </div>
        ) : null}

        {erro ? (
          <div className="cotacoes-rpa-off" role="status">
            <p>
              <strong>O robô de cotações não está ligado</strong> em <code>{urlRobo}</code>.
            </p>
            <p className="erro">{erro}</p>
            <button type="button" className="secundario" onClick={() => setReloadOps((n) => n + 1)}>
              Tentar de novo
            </button>
          </div>
        ) : null}

        {!operadoras && !erro ? <p className="lista-carregando">Carregando operadoras do robô…</p> : null}

        {operadoras && tela === "nova" ? <BannerPendencias aviso={mostrarAviso} recarregarSinal={reloadLista} /> : null}

        {operadoras && tela === "cotacoes" ? (
          <ListaCotacoes
            operadoras={operadoras}
            aviso={mostrarAviso}
            onNova={() => ir("#/nova")}
            onCotarEmpresa={(cnpjEmp) => ir(`#/nova?cnpj=${cnpjEmp}`)}
            recarregarSinal={reloadLista}
          />
        ) : null}

        {operadoras && tela === "conexoes" ? (
          <Conexoes
            operadoras={operadoras}
            indisponiveis={indisponiveis}
            conexao={conexao}
            urlRobo={urlRobo}
            aviso={mostrarAviso}
            onReloadOps={() => setReloadOps((n) => n + 1)}
            trabalhoAtual={trabalhoAtual}
            naFila={naFila}
            opLoginInicial={op}
          />
        ) : null}

        {operadoras && tela === "nova" ? (
          <NovaCotacao
            operadoras={operadoras}
            conexao={conexao}
            urlRobo={urlRobo}
            cnpjInicial={cnpj}
            onEnfileirado={(tid) => ir(`#/andamento/${tid}`)}
            onIrIframeCotacoes={irIframe}
            onCotarEmpresa={(cnpjEmp) => ir(`#/nova?cnpj=${cnpjEmp}`)}
            aviso={mostrarAviso}
          />
        ) : null}

        {operadoras && tela === "andamento" && id ? (
          <Andamento
            trabalhoId={id}
            operadoras={operadoras}
            conexaoExterna={conexao}
            onNovoTrabalho={(tid) => ir(`#/andamento/${tid}`)}
            onNova={(cnpjNovo) => ir(cnpjNovo ? `#/nova?cnpj=${cnpjNovo}` : "#/nova")}
            onIrIframeCotacoes={irIframe}
            onIrLogin={(opId) => ir(`#/conexoes?op=${opId}`)}
            urlRobo={urlRobo}
            aviso={mostrarAviso}
          />
        ) : null}
      </main>
    </div>
  );
}
