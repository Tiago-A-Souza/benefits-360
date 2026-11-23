import { useCallback, useEffect, useRef, useState } from "react";
import NavegacaoFerramentas from "../../NavegacaoFerramentas";
import { chamarRpa, ouvirEventosRpa, resumoVersaoRobo, urlBaseRpa } from "../rpaClient";
import Ajuda from "./Ajuda";
import Andamento from "./Andamento";
import AjustesRobos from "./AjustesRobos";
import BannerPendencias from "./BannerPendencias";
import ConfigRobo from "./ConfigRobo";
import Conexoes from "./Conexoes";
import { useConfirmacao } from "./Confirmacao";
import FaixaCodigo from "./FaixaCodigo";
import FaixaProblemaLogin from "./FaixaProblemaLogin";
import FaixaTrabalho from "./FaixaTrabalho";
import ImportarPlanilha from "./ImportarPlanilha";
import Inicio from "./Inicio";
import ListaCotacoes from "./ListaCotacoes";
import NovaCotacao from "./NovaCotacao";
import { TELAS_ROBO_NAO_PORTADAS } from "./regrasNova";
import { asArray } from "../../util/colecao";
import ErrorBoundary from "../../erro/ErrorBoundary";
import { HASH_ESTUDOS, HASH_SIMULAR, irPara } from "../../rotas";
import "./nativa.css";

function lerHash() {
  const h = (typeof window !== "undefined" && window.location.hash) || "";
  const qh = h.includes("?") ? h.slice(h.indexOf("?") + 1) : "";
  const qs = new URLSearchParams(qh);
  const mAnd = h.match(/^#\/andamento\/(\d+)/);
  if (mAnd) return { tela: "andamento", id: Number(mAnd[1]), cnpj: null, op: null };
  if (h.startsWith("#/conexoes")) return { tela: "conexoes", id: null, cnpj: null, op: qs.get("op") };
  if (h.startsWith("#/cotacoes")) return { tela: "cotacoes", id: null, cnpj: null, op: null };
  if (h.startsWith("#/inicio")) return { tela: "inicio", id: null, cnpj: null, op: null };
  if (h.startsWith("#/ajuda")) return { tela: "ajuda", id: null, cnpj: null, op: null };
  if (h.startsWith("#/importar")) return { tela: "importar", id: null, cnpj: null, op: null };
  if (h.startsWith("#/robos")) return { tela: "robos", id: null, cnpj: null, op: null };
  const mRobo = h.match(/^#\/robo\/([^/?]+)/);
  if (mRobo) {
    if (qs.get("login")) return { tela: "conexoes", id: null, cnpj: null, op: mRobo[1] };
    return { tela: "robo", id: null, cnpj: null, op: mRobo[1] };
  }
  const mNova = h.match(/^#\/nova(?:\?(.*))?/);
  if (mNova) {
    const q = mNova[1] ? new URLSearchParams(mNova[1]) : new URLSearchParams();
    const cnpjQuery =
      typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("cnpj") : null;
    return { tela: "nova", id: null, cnpj: q.get("cnpj") || cnpjQuery, op: null };
  }
  return { tela: "cotacoes", id: null, cnpj: null, op: null };
}

function hashAtual() {
  if (typeof window === "undefined") return "#/cotacoes";
  return window.location.hash || "#/cotacoes";
}

export default function CotacoesNativa({
  onMeusEstudos,
  onSimularRede,
  onVoltarEstudo,
  rotuloEstudo,
  hashVoltarEstudo,
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
  const [simulador, setSimulador] = useState(false);
  const [retencaoDias, setRetencaoDias] = useState(90);
  const [versaoRobo, setVersaoRobo] = useState(null);
  const urlRobo = urlBaseRpa();
  const [confirmar, modal] = useConfirmacao();
  const sujoRef = useRef(() => "");
  const hashMostrado = useRef(hashAtual());

  const marcarSujo = useCallback((fn) => {
    sujoRef.current = typeof fn === "function" ? fn : () => "";
  }, []);

  const aplicarHash = useCallback((hash, { replace = false } = {}) => {
    irPara(hash, { replace });
    const alvo = String(hash || "").startsWith("#") ? String(hash) : `#${hash}`;
    hashMostrado.current = alvo;
    setRota(lerHash());
  }, []);

  const ir = useCallback(
    async (hash) => {
      const msg = sujoRef.current?.() || "";
      if (msg) {
        const ok = await confirmar({
          titulo: "Sair sem salvar?",
          texto: [msg],
          ok: "Sair sem salvar",
          cancelar: "Continuar aqui",
          principal: false,
        });
        if (!ok) return;
        sujoRef.current = () => "";
      }
      aplicarHash(hash, { replace: false });
    },
    [aplicarHash, confirmar],
  );

  useEffect(() => {
    const onHash = async () => {
      const destino = hashAtual();
      if (destino === hashMostrado.current) {
        setRota(lerHash());
        return;
      }
      const msg = sujoRef.current?.() || "";
      if (!msg) {
        hashMostrado.current = destino;
        setRota(lerHash());
        return;
      }
      irPara(hashMostrado.current, { replace: true });
      const ok = await confirmar({
        titulo: "Sair sem salvar?",
        texto: [msg],
        ok: "Sair sem salvar",
        cancelar: "Continuar aqui",
        principal: false,
      });
      if (ok) {
        sujoRef.current = () => "";
        aplicarHash(destino);
      }
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [aplicarHash, confirmar]);

  useEffect(() => {
    let vivo = true;
    setErro(null);
    Promise.all([chamarRpa("GET", "/api/operadoras"), chamarRpa("GET", "/api/estado").catch(() => null)])
      .then(([d, estado]) => {
        if (!vivo) return;
        const lista = asArray(d);
        if (!Array.isArray(d) && d && typeof d === "object" && !d.operadoras) {
          setErro("O robô devolveu um formato inesperado de operadoras. Atualize o robô ou tente de novo.");
          setOperadoras([]);
          return;
        }
        setOperadoras(lista);
        setIndisponiveis(asArray(estado && estado.operadoras_indisponiveis));
        setSimulador(!!(estado && estado.simulador));
        setVersaoRobo(resumoVersaoRobo(estado));
        if (estado && estado.retencao_dias) setRetencaoDias(estado.retencao_dias);
        const cx = {};
        for (const o of lista) cx[o.id] = o.conexao || "desconectado";
        setConexao((c) => ({ ...cx, ...(c || {}) }));
        const robo = estado && estado.robo;
        if (robo && typeof robo === "object") {
          setTrabalhoAtual(robo.atual || null);
          setNaFila(asArray(robo.na_fila));
          if (robo.ultima_etapa) setUltimaEtapa(robo.ultima_etapa);
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
      if (ev.tipo === "cotacao" || ev.tipo === "conexao" || (ev.tipo === "trabalho" && ev.status !== "rodando")) {
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

  const noAndamentoDeste = tela === "andamento" && trabalhoAtual && Number(id) === Number(trabalhoAtual.id);
  const ativoMenu =
    tela === "nova" || tela === "andamento"
      ? "nova"
      : tela === "conexoes"
        ? "conexoes"
        : tela === "inicio"
          ? "inicio"
          : tela === "ajuda"
            ? "ajuda"
            : tela === "importar"
              ? "importar"
              : tela === "robos" || tela === "robo"
                ? "robos"
                : "cotacoes";

  const itensMenu = [
    { id: "inicio", rotulo: "Início", hash: "#/inicio" },
    { id: "nova", rotulo: "Nova cotação", hash: "#/nova" },
    { id: "cotacoes", rotulo: "Cotações", hash: "#/cotacoes" },
    { id: "importar", rotulo: "Importar planilha", hash: "#/importar" },
    { id: "conexoes", rotulo: "Conexões", hash: "#/conexoes" },
    { id: "robos", rotulo: "Ajustes dos robôs", hash: "#/robos" },
    { id: "ajuda", rotulo: "Ajuda", hash: "#/ajuda" },
  ];

  return (
    <div className="lista-shell nativa-shell">
      {modal}
      <aside className="lista-rail app-sidebar">
        <NavegacaoFerramentas
          ativo="cotacoes"
          onMeusEstudos={() => ir(HASH_ESTUDOS)}
          onSimularRede={() => ir(HASH_SIMULAR)}
          onCotacoes={() => ir("#/cotacoes")}
          onVoltarEstudo={
            hashVoltarEstudo || onVoltarEstudo
              ? () => (hashVoltarEstudo ? ir(hashVoltarEstudo) : onVoltarEstudo())
              : undefined
          }
          rotuloEstudo={rotuloEstudo}
        />
        <nav className="nav-ferramentas nativa-subnav" aria-label="Cotações">
          <p className="lista-rail-lb">Cotações</p>
          <ul className="lista-filtros">
            {itensMenu.map((item) => (
              <li key={item.id}>
                <button type="button" aria-pressed={ativoMenu === item.id} onClick={() => ir(item.hash)}>
                  {item.rotulo}
                </button>
              </li>
            ))}
          </ul>
          {TELAS_ROBO_NAO_PORTADAS.length ? (
            <>
              <p className="lista-rail-lb">No robô local</p>
              <ul className="lista-filtros">
                {TELAS_ROBO_NAO_PORTADAS.map((t) => (
                  <li key={t.hash}>
                    <a
                      href={`${urlRobo}/${t.hash}`}
                      target="_blank"
                      rel="noreferrer"
                      title={`Abre ${t.rotulo} no robô (127.0.0.1:8600) em outra aba`}
                    >
                      {t.rotulo}
                    </a>
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          {TELAS_ROBO_NAO_PORTADAS.length ? (
            <p className="muted nativa-flag-hint">
              Telas ainda não portadas abrem o robô local em outra aba.
            </p>
          ) : null}
          {versaoRobo ? (
            <p
              className={
                versaoRobo.antigo
                  ? "muted nativa-versao-robo nativa-versao-robo--aviso"
                  : "muted nativa-versao-robo"
              }
            >
              {versaoRobo.texto}
            </p>
          ) : null}
        </nav>
      </aside>

      <main className="lista-main nativa-main">
        <ErrorBoundary contexto={`Cotações · ${tela}`} modo="painel" resetKey={tela} onVoltarEstudos={onMeusEstudos}>
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

        {operadoras && tela === "inicio" ? (
          <Inicio
            operadoras={operadoras}
            trabalhoAtual={trabalhoAtual}
            aviso={mostrarAviso}
            onAcompanhar={(tid) => ir(`#/andamento/${tid}`)}
            onCotacoes={() => ir("#/cotacoes")}
            onNova={() => ir("#/nova")}
            onImportar={() => ir("#/importar")}
            onLogin={(opId) => ir(`#/conexoes?op=${opId}`)}
            onCotarEmpresa={(cnpjEmp) => ir(`#/nova?cnpj=${cnpjEmp}`)}
            recarregarSinal={reloadLista}
          />
        ) : null}

        {operadoras && tela === "ajuda" ? (
          <Ajuda operadoras={operadoras} retencaoDias={retencaoDias} simulador={simulador} />
        ) : null}

        {operadoras && tela === "importar" ? (
          <ImportarPlanilha
            operadoras={operadoras}
            aviso={mostrarAviso}
            onEnfileirado={(tid) => ir(`#/andamento/${tid}`)}
          />
        ) : null}

        {operadoras && tela === "robos" ? (
          <AjustesRobos
            operadoras={operadoras}
            indisponiveis={indisponiveis}
            conexao={conexao}
            aviso={mostrarAviso}
            onConfigurar={(opId) => ir(`#/robo/${opId}`)}
            onLogin={(opId) => ir(`#/conexoes?op=${opId}`)}
          />
        ) : null}

        {operadoras && tela === "robo" && op ? (
          <ConfigRobo
            opId={op}
            operadoras={operadoras}
            conexao={conexao}
            aviso={mostrarAviso}
            onVoltar={() => ir("#/robos")}
            onLogin={(opId) => ir(`#/conexoes?op=${opId}`)}
            onSujo={marcarSujo}
          />
        ) : null}

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
            onConfigurar={(opId) => ir(`#/robo/${opId}`)}
          />
        ) : null}

        {operadoras && tela === "nova" ? (
          <NovaCotacao
            operadoras={operadoras}
            conexao={conexao}
            urlRobo={urlRobo}
            cnpjInicial={cnpj}
            onEnfileirado={(tid) => ir(`#/andamento/${tid}`)}
            onIrIframeCotacoes={() => ir("#/cotacoes")}
            onCotarEmpresa={(cnpjEmp) => ir(`#/nova?cnpj=${cnpjEmp}`)}
            onConfigurar={(opId) => ir(`#/robo/${opId}`)}
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
            onIrIframeCotacoes={() => ir("#/cotacoes")}
            onIrLogin={(opId) => ir(`#/conexoes?op=${opId}`)}
            urlRobo={urlRobo}
            aviso={mostrarAviso}
          />
        ) : null}
        </ErrorBoundary>
      </main>
    </div>
  );
}
