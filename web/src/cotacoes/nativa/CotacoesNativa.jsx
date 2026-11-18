import { useCallback, useEffect, useState } from "react";
import NavegacaoFerramentas from "../../NavegacaoFerramentas";
import { chamarRpa, ouvirEventosRpa, urlBaseRpa } from "../rpaClient";
import Andamento from "./Andamento";
import BannerPendencias from "./BannerPendencias";
import FaixaCodigo from "./FaixaCodigo";
import FaixaProblemaLogin from "./FaixaProblemaLogin";
import FaixaTrabalho from "./FaixaTrabalho";
import NovaCotacao from "./NovaCotacao";
import "./nativa.css";

function lerHash() {
  const h = (typeof window !== "undefined" && window.location.hash) || "";
  const mAnd = h.match(/^#\/andamento\/(\d+)/);
  if (mAnd) return { tela: "andamento", id: Number(mAnd[1]), cnpj: null };
  const mNova = h.match(/^#\/nova(?:\?(.*))?/);
  const q = mNova && mNova[1] ? new URLSearchParams(mNova[1]) : new URLSearchParams();
  const cnpjHash = q.get("cnpj");
  const cnpjQuery =
    typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("cnpj") : null;
  return { tela: "nova", id: null, cnpj: cnpjHash || cnpjQuery };
}

export default function CotacoesNativa({
  onMeusEstudos,
  onSimularRede,
  onCotacoesIframe,
  onVoltarEstudo,
  rotuloEstudo,
}) {
  const [{ tela, id, cnpj }, setRota] = useState(lerHash);
  const [operadoras, setOperadoras] = useState(null);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const [conexao, setConexao] = useState({});
  const [problemaLogin, setProblemaLogin] = useState(null);
  const [trabalhoAtual, setTrabalhoAtual] = useState(null);
  const [ultimaEtapa, setUltimaEtapa] = useState(null);
  const [reloadOps, setReloadOps] = useState(0);
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
    chamarRpa("GET", "/api/operadoras")
      .then((d) => {
        if (!vivo) return;
        setOperadoras(d);
        const cx = {};
        for (const op of d || []) cx[op.id] = op.conexao || "desconectado";
        setConexao((c) => ({ ...cx, ...c }));
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

  const noAndamentoDeste = tela === "andamento" && trabalhoAtual && Number(id) === Number(trabalhoAtual.id);

  return (
    <div className="lista-shell nativa-shell">
      <aside className="lista-rail app-sidebar">
        <NavegacaoFerramentas
          ativo={null}
          onMeusEstudos={onMeusEstudos}
          onSimularRede={onSimularRede}
          onCotacoes={onCotacoesIframe}
          onVoltarEstudo={onVoltarEstudo}
          rotuloEstudo={rotuloEstudo}
        />
        <nav className="nav-ferramentas nativa-subnav" aria-label="Cotações nativas">
          <p className="lista-rail-lb">Prova nativa</p>
          <ul className="lista-filtros">
            <li>
              <button type="button" aria-pressed={tela === "nova"} onClick={() => ir("#/nova")}>
                Nova cotação
              </button>
            </li>
          </ul>
          <p className="muted nativa-flag-hint">
            Fora do menu. Abra <code>?cotacoes-nativa=1</code> (ou flag <code>VITE_COTACOES_NATIVA=1</code> com{" "}
            <code>#/nova</code>). A aba Cotações continua no iframe.
          </p>
        </nav>
      </aside>

      <main className="lista-main nativa-main">
        {problemaLogin ? (
          <FaixaProblemaLogin
            problema={problemaLogin}
            operadoras={operadoras || []}
            urlRobo={urlRobo}
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

        {operadoras ? <BannerPendencias aviso={mostrarAviso} /> : null}

        {operadoras && tela === "nova" ? (
          <NovaCotacao
            operadoras={operadoras}
            conexao={conexao}
            urlRobo={urlRobo}
            cnpjInicial={cnpj}
            onEnfileirado={(tid) => ir(`#/andamento/${tid}`)}
            onIrIframeCotacoes={onCotacoesIframe}
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
            onIrIframeCotacoes={onCotacoesIframe}
            urlRobo={urlRobo}
            aviso={mostrarAviso}
          />
        ) : null}
      </main>
    </div>
  );
}
