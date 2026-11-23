import { useEffect, useMemo, useState } from "react";
import { criarEstudo, listarEstudos } from "./api";
import NavegacaoFerramentas from "./NavegacaoFerramentas";

function formatarData(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("pt-BR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return "—";
  }
}

function chaveCliente(estudo) {
  return (estudo.empresa || "").trim();
}

function rotuloCliente(estudo) {
  const nome = chaveCliente(estudo);
  return nome || "Empresa não informada";
}

function estaAprovado(estudo) {
  return (estudo.status || "") === "aprovado";
}

/** Agrupa por nome de cliente exatamente como gravado; multi-estudo primeiro, singles em «Outros». */
function agruparPorCliente(estudos) {
  const mapa = new Map();
  for (const e of estudos || []) {
    const chave = chaveCliente(e);
    if (!mapa.has(chave)) mapa.set(chave, []);
    mapa.get(chave).push(e);
  }

  const multiplos = [];
  const singles = [];
  for (const [chave, itens] of mapa.entries()) {
    if (itens.length > 1) multiplos.push({ chave, titulo: rotuloCliente(itens[0]), itens });
    else singles.push(...itens);
  }

  multiplos.sort((a, b) => a.titulo.localeCompare(b.titulo, "pt-BR"));

  const grupos = multiplos.map((g) => ({
    id: `cli:${g.chave}`,
    titulo: g.titulo,
    contagem: g.itens.length,
    itens: g.itens,
  }));

  if (singles.length > 0) {
    if (multiplos.length > 0) {
      grupos.push({
        id: "outros",
        titulo: "Outros clientes",
        contagem: singles.length,
        itens: singles,
      });
    } else {
      grupos.push({
        id: "todos",
        titulo: null,
        contagem: singles.length,
        itens: singles,
      });
    }
  }

  return grupos;
}

/** Avisos: mesmo cliente + mesmo rótulo em mais de um estudo (na lista carregada). */
function avisosRotulosRepetidos(estudos) {
  const porClienteRotulo = new Map();
  for (const e of estudos || []) {
    const cli = chaveCliente(e);
    const rotulo = (e.titulo || "").trim();
    if (!cli || !rotulo) continue;
    const key = `${cli}\0${rotulo}`;
    if (!porClienteRotulo.has(key)) porClienteRotulo.set(key, { empresa: rotuloCliente(e), rotulo, n: 0 });
    porClienteRotulo.get(key).n += 1;
  }
  return [...porClienteRotulo.values()].filter((x) => x.n > 1);
}

export default function MeusEstudos({ onContinuar, onSimularRede, onCotacoes }) {
  const [estudos, setEstudos] = useState([]);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState(null);
  const [modal, setModal] = useState(false);
  const [nomeEmpresa, setNomeEmpresa] = useState("");
  const [nomeEstudo, setNomeEstudo] = useState("");
  const [formato, setFormato] = useState("renovacao");
  const [criando, setCriando] = useState(false);
  const [busca, setBusca] = useState("");
  const [filtroEstado, setFiltroEstado] = useState("todos");
  const [filtroFormato, setFiltroFormato] = useState("todos");

  function recarregar() {
    setCarregando(true);
    listarEstudos()
      .then(setEstudos)
      .catch((e) => setErro(e.message))
      .finally(() => setCarregando(false));
  }

  useEffect(() => {
    recarregar();
  }, []);

  async function handleCriar(e) {
    e.preventDefault();
    if (!nomeEmpresa.trim() || !nomeEstudo.trim()) return;
    setCriando(true);
    setErro(null);
    try {
      const res = await criarEstudo({
        titulo: nomeEstudo.trim(),
        nome_empresa: nomeEmpresa.trim(),
        formato,
      });
      setModal(false);
      setNomeEmpresa("");
      setNomeEstudo("");
      setFormato("renovacao");
      onContinuar(res.id);
    } catch (err) {
      setErro(err.message);
    } finally {
      setCriando(false);
    }
  }

  const filtradosBusca = useMemo(() => {
    const q = busca.trim().toLowerCase();
    if (!q) return estudos;
    return estudos.filter((e) => {
      const empresa = (e.empresa || "").toLowerCase();
      const titulo = (e.titulo || "").toLowerCase();
      return empresa.includes(q) || titulo.includes(q);
    });
  }, [estudos, busca]);

  const contagens = useMemo(() => {
    const base = filtradosBusca;
    return {
      todos: base.length,
      em_andamento: base.filter((e) => !estaAprovado(e)).length,
      aprovado: base.filter((e) => estaAprovado(e)).length,
      renovacao: base.filter((e) => e.formato === "renovacao").length,
      novo: base.filter((e) => e.formato === "novo").length,
    };
  }, [filtradosBusca]);

  const filtrados = useMemo(() => {
    return filtradosBusca.filter((e) => {
      if (filtroEstado === "aprovado" && !estaAprovado(e)) return false;
      if (filtroEstado === "em_andamento" && estaAprovado(e)) return false;
      if (filtroFormato === "renovacao" && e.formato !== "renovacao") return false;
      if (filtroFormato === "novo" && e.formato !== "novo") return false;
      return true;
    });
  }, [filtradosBusca, filtroEstado, filtroFormato]);

  const grupos = useMemo(() => agruparPorCliente(filtrados), [filtrados]);
  const avisos = useMemo(() => avisosRotulosRepetidos(filtrados), [filtrados]);

  const emAndamentoTotal = estudos.filter((e) => !estaAprovado(e)).length;

  return (
    <div className="lista-shell">
      <aside className="lista-rail app-sidebar">
        {(onSimularRede || onCotacoes) && (
          <NavegacaoFerramentas
            ativo="estudos"
            onMeusEstudos={() => {}}
            onSimularRede={onSimularRede}
            onCotacoes={onCotacoes}
          />
        )}
        <div className="lista-busca">
          <span className="lista-busca-ic" aria-hidden="true">
            ⌕
          </span>
          <input
            type="search"
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Buscar por cliente…"
            aria-label="Buscar estudo por cliente"
          />
        </div>

        <p className="lista-rail-lb">Filtrar</p>
        <ul className="lista-filtros">
          <li>
            <button
              type="button"
              aria-pressed={filtroEstado === "todos"}
              onClick={() => setFiltroEstado("todos")}
            >
              Todos
              <span className="lista-filtros-c num">{contagens.todos}</span>
            </button>
          </li>
          <li>
            <button
              type="button"
              aria-pressed={filtroEstado === "em_andamento"}
              onClick={() => setFiltroEstado("em_andamento")}
            >
              <span className="lista-filtros-lb">
                <span className="lista-pt lista-pt--azul" aria-hidden="true" />
                Em andamento
              </span>
              <span className="lista-filtros-c num">{contagens.em_andamento}</span>
            </button>
          </li>
          <li>
            <button
              type="button"
              aria-pressed={filtroEstado === "aprovado"}
              onClick={() => setFiltroEstado("aprovado")}
            >
              <span className="lista-filtros-lb">
                <span className="lista-pt lista-pt--verde" aria-hidden="true" />
                Aprovados
              </span>
              <span className="lista-filtros-c num">{contagens.aprovado}</span>
            </button>
          </li>
        </ul>

        <p className="lista-rail-lb">Formato</p>
        <ul className="lista-filtros">
          <li>
            <button
              type="button"
              aria-pressed={filtroFormato === "todos"}
              onClick={() => setFiltroFormato("todos")}
            >
              Todos
              <span className="lista-filtros-c num">{contagens.todos}</span>
            </button>
          </li>
          <li>
            <button
              type="button"
              aria-pressed={filtroFormato === "renovacao"}
              onClick={() => setFiltroFormato("renovacao")}
            >
              Renovação
              <span className="lista-filtros-c num">{contagens.renovacao}</span>
            </button>
          </li>
          <li>
            <button
              type="button"
              aria-pressed={filtroFormato === "novo"}
              onClick={() => setFiltroFormato("novo")}
            >
              Seguro novo
              <span className="lista-filtros-c num">{contagens.novo}</span>
            </button>
          </li>
        </ul>
      </aside>

      <main className="lista-main">
        <header className="lista-head">
          <div>
            <h1>Meus estudos</h1>
            <p>
              Renovações e comparativos de planos de saúde empresariais
              {!carregando && estudos.length > 0 && (
                <>
                  {" "}
                  · {estudos.length} {estudos.length === 1 ? "estudo" : "estudos"}
                  {emAndamentoTotal > 0 && ` · ${emAndamentoTotal} em andamento`}
                </>
              )}
            </p>
          </div>
          <button type="button" className="lista-btn-criar" onClick={() => setModal(true)}>
            Criar novo estudo
          </button>
        </header>

        {carregando && (
          <div className="lista-estado">
            <p className="muted">Carregando estudos…</p>
          </div>
        )}

        {!carregando && estudos.length === 0 && (
          <div className="lista-estado lista-vazio">
            <h2>Nenhum estudo ainda</h2>
            <p className="muted">Crie o primeiro comparativo para começar a análise financeira.</p>
            <button type="button" onClick={() => setModal(true)}>
              Criar novo estudo
            </button>
          </div>
        )}

        {!carregando && estudos.length > 0 && filtrados.length === 0 && (
          <div className="lista-estado">
            <p className="muted">Nenhum estudo corresponde aos filtros.</p>
          </div>
        )}

        {!carregando && avisos.length > 0 && (
          <div className="lista-aviso" role="status">
            <div>
              <b>
                {avisos.length === 1
                  ? `Estudos de ${avisos[0].empresa} com o mesmo rótulo`
                  : `${avisos.length} clientes com rótulos repetidos`}
              </b>
              <p>
                {avisos.length === 1
                  ? `Dois ou mais estudos têm o rótulo «${avisos[0].rotulo}». Renomeie para não conferir números contra o estudo errado.`
                  : "Há estudos do mesmo cliente com o mesmo rótulo. Renomeie para não conferir números contra o estudo errado."}
              </p>
            </div>
          </div>
        )}

        {!carregando && filtrados.length > 0 && (
          <div className="lista-painel">
            {grupos.map((grupo) => (
              <section key={grupo.id} className="lista-grupo-bloco">
                {grupo.titulo && (
                  <div className="lista-grupo">
                    <span>{grupo.titulo}</span>
                    <span className="lista-grupo-qt num">
                      {grupo.contagem} {grupo.contagem === 1 ? "estudo" : "estudos"}
                    </span>
                  </div>
                )}
                <ul className="lista-linhas">
                  {grupo.itens.map((e) => {
                    const aprovado = estaAprovado(e);
                    const tipo = (e.formato_exibicao || "Renovação").toLowerCase();
                    const vidas =
                      typeof e.beneficiarios_incluidos === "number"
                        ? e.beneficiarios_incluidos
                        : null;
                    return (
                      <li key={e.id}>
                        <div className="lista-linha">
                          <div className="lista-ident">
                            <span className="lista-cli">{rotuloCliente(e)}</span>
                            <span className="lista-sub">
                              <span className="lista-rotulo">{e.titulo || "—"}</span>
                              <span className="lista-meta num">
                                {tipo} ·{" "}
                                <time dateTime={e.ultima_alteracao}>
                                  {formatarData(e.ultima_alteracao)}
                                </time>
                              </span>
                            </span>
                          </div>
                          <div className="lista-dado lista-col-oculta num">
                            <b>{vidas != null ? vidas : "—"}</b>
                            <span>vidas</span>
                          </div>
                          <div
                            className={`lista-dado lista-col-oculta num${
                              e.total_reajustado_reais ? "" : " lista-dado--vazio"
                            }`}
                          >
                            <b>{e.total_reajustado_reais || "—"}</b>
                            <span>
                              {e.total_reajustado_reais ? "base reajustada" : "sem contrato"}
                            </span>
                          </div>
                          <div className="lista-col-oculta">
                            <span
                              className={`lista-estado-pill ${
                                aprovado ? "lista-estado-pill--apr" : "lista-estado-pill--and"
                              }`}
                            >
                              {e.status_exibicao || (aprovado ? "Aprovado" : "Em andamento")}
                            </span>
                          </div>
                          <div className="lista-acao">
                            <button
                              type="button"
                              className="secundario btn-compacto"
                              onClick={() => onContinuar(e.id)}
                            >
                              {aprovado ? "Abrir" : "Continuar"}
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </div>
        )}

        <p className="lista-nota">
          «Aprovação caiu» significa que a base, o reajuste ou as cotações mudaram depois do
          aceite. Nesta listagem só distinguimos Em andamento e Aprovado.
        </p>

        {erro && <p className="erro lista-erro">{erro}</p>}
      </main>

      {modal && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-novo-estudo-titulo">
          <form className="modal-cartao estudos-modal" onSubmit={handleCriar}>
            <header className="modal-cabecalho">
              <h2 id="modal-novo-estudo-titulo">Novo estudo</h2>
              <p className="muted">Comparativo de planos de saúde empresariais.</p>
            </header>

            <div className="modal-secao">
              <p className="modal-secao-titulo">Tipo de estudo</p>
              <div className="cartoes-escolha cartoes-escolha--empilhados">
                <label
                  className={`cartao-escolha${formato === "renovacao" ? " cartao-escolha--ativo" : ""}`}
                >
                  <input
                    type="radio"
                    name="formato"
                    value="renovacao"
                    checked={formato === "renovacao"}
                    onChange={() => setFormato("renovacao")}
                  />
                  <strong>Renovação</strong>
                  <span className="muted">Há contrato vigente (fatura por vida).</span>
                </label>
                <label
                  className={`cartao-escolha${formato === "novo" ? " cartao-escolha--ativo" : ""}`}
                >
                  <input
                    type="radio"
                    name="formato"
                    value="novo"
                    checked={formato === "novo"}
                    onChange={() => setFormato("novo")}
                  />
                  <strong>Seguro novo</strong>
                  <span className="muted">Sem plano vigente (valores de fatura opcionais).</span>
                </label>
              </div>
            </div>

            <label className="field">
              Nome da empresa
              <input
                required
                value={nomeEmpresa}
                onChange={(ev) => setNomeEmpresa(ev.target.value)}
                placeholder="Ex.: Acme Indústria Ltda."
                autoFocus
              />
            </label>
            <label className="field">
              Nome do estudo
              <input
                required
                value={nomeEstudo}
                onChange={(ev) => setNomeEstudo(ev.target.value)}
                placeholder={
                  formato === "novo"
                    ? "Ex.: Seguro novo 2026 — 12 vidas"
                    : "Ex.: Renovação 2026 — 18 vidas"
                }
              />
            </label>

            <div className="modal-acoes">
              <button type="button" className="secundario" onClick={() => setModal(false)}>
                Cancelar
              </button>
              <button type="submit" disabled={criando}>
                {criando ? "Criando…" : "Criar estudo"}
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
