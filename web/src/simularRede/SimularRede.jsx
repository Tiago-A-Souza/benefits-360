import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  consultarRedePorHospital,
  consultarRedePorPlano,
  mensagemErroOperador,
  obterOpcoesSimulacaoRede,
} from "../api";
import BarraLateral from "../layout/BarraLateral";
import NavegacaoFerramentas from "../NavegacaoFerramentas";
import SimularLabs from "./SimularLabs";
import {
  LEGENDA_COBERTURA,
  gruposDeOperadora,
  haFiltroGeografico,
  haRedeVerticalizada,
  municipiosDaUf,
  planosDaOperadora,
  temTermoConsulta,
  textoContagem,
  zonasDoMunicipio,
} from "./opcoesSimulacao";

function PillVerticalizada({ operadora }) {
  return (
    <span
      className="simular-pill simular-pill--vert"
      title="Rede própria de uma operadora: aparece coberto nos planos dela e vazio nos demais."
    >
      Rede própria · {operadora}
    </span>
  );
}

export function TabelaResultado({ resp }) {
  if (!resp) return <p className="muted">Nenhum resultado para mostrar.</p>;
  const colunas = resp.colunas || [];
  const blocos = resp.blocos || [];
  const grupos = gruposDeOperadora(colunas);
  const largura = 1 + colunas.length;
  return (
    <div className="tabela-scroll">
      <table className="conferencia rede-selecao-tabela tabela-rede simular-tabela">
        <thead>
          <tr>
            <th className="rede-col-prestador" scope="col">
              Prestador
            </th>
            {grupos.flatMap((g) =>
              g.colunas.map((c) => (
                <th key={c.chave} className="rede-col-plano" scope="col">
                  <span className="op">{c.operadora}</span>
                  <span className="pl">{c.plano}</span>
                </th>
              ))
            )}
          </tr>
        </thead>
        <tbody>
          {blocos.map((bloco) => (
            <Fragment key={bloco.municipio}>
              <tr className="simular-bloco-linha">
                <th colSpan={largura} scope="colgroup">
                  {bloco.titulo}
                  <span className="simular-bloco-n">{(bloco.linhas || []).length}</span>
                </th>
              </tr>
                  {(bloco.linhas || []).map((ln) => (
                <tr key={ln.linha_id} className={ln.principal ? "" : "simular-linha-nao-principal"}>
                  <td className="nm rede-col-prestador">
                    <span className="cell-main">
                      {ln.zona_sigla ? `${ln.zona_sigla} ` : ""}
                      {ln.prestador_nome}
                    </span>
                    {ln.bairro ? <span className="bairro-rede">{ln.bairro}</span> : null}
                    {ln.rede_verticalizada ? (
                      <PillVerticalizada operadora={ln.rede_verticalizada} />
                    ) : null}
                    {!ln.principal ? (
                      <span className="simular-pill simular-pill--muted">Não principal</span>
                    ) : null}
                  </td>
                  {colunas.map((c) => {
                    const cod = (ln.celulas && ln.celulas[c.chave]) || "";
                    return (
                      <td key={c.chave} className={`rede-col-plano ${cod ? "on" : "off"}`}>
                        {cod}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function SimularRede({ onMeusEstudos, onSimularRede, onCotacoes, onVoltarEstudo, rotuloEstudo }) {
  const [tipoRede, setTipoRede] = useState("hospitais");
  const [opcoes, setOpcoes] = useState(null);
  const [erroOpcoes, setErroOpcoes] = useState(null);

  const [modo, setModo] = useState("hospital");
  const [texto, setTexto] = useState("");
  const [termo, setTermo] = useState("");
  const [operadorasSel, setOperadorasSel] = useState([]);
  const [opPlano, setOpPlano] = useState("");
  const [plano, setPlano] = useState("");
  const [uf, setUf] = useState("");
  const [municipio, setMunicipio] = useState("");
  const [zona, setZona] = useState("");
  const [todos, setTodos] = useState(false);
  const [confirmadoPara, setConfirmadoPara] = useState("");

  const [resp, setResp] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [ms, setMs] = useState(null);
  const seq = useRef(0);

  useEffect(() => {
    let vivo = true;
    obterOpcoesSimulacaoRede()
      .then((o) => vivo && setOpcoes(o))
      .catch((e) => vivo && setErroOpcoes(mensagemErroOperador(e, "Falha ao carregar a rede.")));
    return () => {
      vivo = false;
    };
  }, []);

  const municipios = useMemo(() => municipiosDaUf(opcoes, uf), [opcoes, uf]);
  const zonas = useMemo(() => zonasDoMunicipio(opcoes, uf, municipio), [opcoes, uf, municipio]);
  const planos = useMemo(() => planosDaOperadora(opcoes, opPlano), [opcoes, opPlano]);

  const filtros = { uf, municipio, zona, todos };
  const semFiltroGeo = !haFiltroGeografico(filtros);

  // Chave de tudo que define a consulta, exceto a confirmação de volume.
  const chaveConsulta = JSON.stringify(
    modo === "hospital"
      ? ["hospital", termo, operadorasSel, uf, municipio, zona, todos]
      : ["plano", plano, uf, municipio, zona, todos]
  );
  const confirmar = confirmadoPara === chaveConsulta;

  const consultaAtiva = modo === "hospital" ? temTermoConsulta(termo) : Boolean(plano);

  useEffect(() => {
    if (!consultaAtiva) {
      seq.current += 1;
      setResp(null);
      setErro(null);
      setMs(null);
      setCarregando(false);
      return undefined;
    }
    const ac = new AbortController();
    const minha = ++seq.current;
    const inicio = performance.now();
    setCarregando(true);
    setErro(null);
    const chamada =
      modo === "hospital"
        ? consultarRedePorHospital({
            termo,
            operadoras: operadorasSel,
            uf,
            municipio,
            zona,
            todos,
            signal: ac.signal,
          })
        : consultarRedePorPlano({
            plano,
            uf,
            municipio,
            zona,
            todos,
            confirmar,
            signal: ac.signal,
          });
    chamada
      .then((r) => {
        if (seq.current !== minha || ac.signal.aborted) return;
        setResp(r);
        setMs(Math.round(performance.now() - inicio));
      })
      .catch((e) => {
        if (seq.current !== minha || ac.signal.aborted || e?.codigo === "ABORTADO") return;
        setResp(null);
        setErro(mensagemErroOperador(e, "Falha na consulta."));
      })
      .finally(() => {
        if (seq.current === minha) setCarregando(false);
      });
    return () => ac.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveConsulta, confirmar, consultaAtiva]);

  function resetarConsulta() {
    setTexto("");
    setTermo("");
    setOperadorasSel([]);
    setOpPlano("");
    setPlano("");
    setUf("");
    setMunicipio("");
    setZona("");
    setTodos(false);
    setConfirmadoPara("");
    setResp(null);
    setErro(null);
    setMs(null);
  }

  function escolherTipo(tipo) {
    if (tipo === tipoRede) return;
    resetarConsulta();
    setModo("hospital");
    setTipoRede(tipo);
  }

  function escolherModo(proximo) {
    if (proximo === modo) return;
    resetarConsulta();
    setModo(proximo);
  }

  function submeterHospital(e) {
    e.preventDefault();
    const t = texto.trim();
    if (!temTermoConsulta(t)) return;
    setTermo(t);
  }

  function escolherUf(valor) {
    setUf(valor);
    setMunicipio("");
    setZona("");
  }

  function escolherMunicipio(valor) {
    setMunicipio(valor);
    setZona("");
  }

  function alternarOperadora(nome) {
    setOperadorasSel((atual) =>
      atual.includes(nome) ? atual.filter((o) => o !== nome) : [...atual, nome]
    );
  }

  const nOperadoras = opcoes?.operadoras?.length ?? 0;
  const blocosVisiveis = resp && !resp.requer_confirmacao ? resp.blocos : [];

  return (
    <div className="lista-shell">
      <BarraLateral>
        <NavegacaoFerramentas
          ativo="simular"
          onMeusEstudos={onMeusEstudos}
          onSimularRede={onSimularRede || (() => {})}
          onCotacoes={onCotacoes}
          onVoltarEstudo={onVoltarEstudo}
          rotuloEstudo={rotuloEstudo}
        />
      </BarraLateral>

      <main className="lista-main simular-rede">
        <header className="lista-head">
          <div>
            <h1>Simular rede</h1>
            <p>
              Consulte a rede credenciada durante a conversa com o cliente — sem abrir estudo.
              Nada é salvo.
              {tipoRede === "hospitais" && opcoes?.data_base_rede
                ? ` Base de ${opcoes.data_base_rede}.`
                : ""}
            </p>
          </div>
        </header>

        {erroOpcoes && tipoRede === "hospitais" && <p className="erro">{erroOpcoes}</p>}

        <div className="simular-tipo" role="tablist" aria-label="Tipo de rede">
          <button
            type="button"
            role="tab"
            aria-selected={tipoRede === "hospitais"}
            className={tipoRede === "hospitais" ? "ativo" : ""}
            onClick={() => escolherTipo("hospitais")}
          >
            Hospitais
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tipoRede === "laboratorios"}
            className={tipoRede === "laboratorios" ? "ativo" : ""}
            onClick={() => escolherTipo("laboratorios")}
          >
            Laboratórios
          </button>
        </div>

        {tipoRede === "laboratorios" ? (
          <SimularLabs key="laboratorios" />
        ) : (
          <>
        <div className="simular-modos" role="tablist" aria-label="Tipo de consulta">
          <button
            type="button"
            role="tab"
            aria-selected={modo === "hospital"}
            className={modo === "hospital" ? "ativo" : ""}
            onClick={() => escolherModo("hospital")}
          >
            Por hospital
            <small>Quais planos cobrem?</small>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={modo === "plano"}
            className={modo === "plano" ? "ativo" : ""}
            onClick={() => escolherModo("plano")}
          >
            Por plano
            <small>Onde o plano atende?</small>
          </button>
        </div>

        <section className="panel panel-flat simular-filtros">
          <div className="panel-body">
            {modo === "hospital" ? (
              <form className="simular-busca" onSubmit={submeterHospital}>
                <div className="field simular-busca-campo">
                  <label className="cmp-filtro-label" htmlFor="simular-hospital">
                    Hospital
                  </label>
                  <input
                    id="simular-hospital"
                    type="search"
                    value={texto}
                    onChange={(e) => setTexto(e.target.value)}
                    placeholder="Ex.: Einstein; Sírio-Libanês; Samaritano"
                    autoComplete="off"
                  />
                  <span className="hint">
                    Vários hospitais separados por «;» ou vírgula. Busca por parte do nome.
                  </span>
                </div>
                <button type="submit" disabled={!temTermoConsulta(texto)}>
                  Consultar
                </button>
              </form>
            ) : (
              <div className="catalog-filters simular-plano">
                <div className="field">
                  <label className="cmp-filtro-label" htmlFor="simular-operadora">
                    Operadora
                  </label>
                  <select
                    id="simular-operadora"
                    value={opPlano}
                    onChange={(e) => {
                      setOpPlano(e.target.value);
                      setPlano("");
                    }}
                  >
                    <option value="">Escolha…</option>
                    {(opcoes?.operadoras || []).map((o) => (
                      <option key={o.nome} value={o.nome}>
                        {o.nome}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="field simular-plano-campo">
                  <label className="cmp-filtro-label" htmlFor="simular-plano">
                    Plano
                  </label>
                  <select
                    id="simular-plano"
                    value={plano}
                    onChange={(e) => setPlano(e.target.value)}
                    disabled={!opPlano}
                  >
                    <option value="">{opPlano ? "Escolha…" : "Escolha a operadora"}</option>
                    {planos.map((p) => (
                      <option key={p.chave} value={p.chave}>
                        {p.rotulo}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            )}

            <div className="catalog-filters simular-geo">
              <div className="field">
                <label className="cmp-filtro-label" htmlFor="simular-uf">
                  Estado
                </label>
                <select id="simular-uf" value={uf} onChange={(e) => escolherUf(e.target.value)}>
                  <option value="">Todos</option>
                  {(opcoes?.ufs || []).map((u) => (
                    <option key={u.uf} value={u.uf}>
                      {u.uf}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="cmp-filtro-label" htmlFor="simular-municipio">
                  Município
                </label>
                <select
                  id="simular-municipio"
                  value={municipio}
                  onChange={(e) => escolherMunicipio(e.target.value)}
                  disabled={!uf}
                >
                  <option value="">{uf ? "Todos" : "Escolha o estado"}</option>
                  {municipios.map((m) => (
                    <option key={m.chave} value={m.chave}>
                      {m.rotulo}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label className="cmp-filtro-label" htmlFor="simular-zona">
                  Zona
                </label>
                <select
                  id="simular-zona"
                  value={zona}
                  onChange={(e) => setZona(e.target.value)}
                  disabled={zonas.length === 0}
                >
                  <option value="">
                    {municipio && zonas.length === 0 ? "Sem zonas" : "Todas"}
                  </option>
                  {zonas.map((z) => (
                    <option key={z} value={z}>
                      {z}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="simular-opcoes">
              <label className="simular-check">
                <input
                  type="checkbox"
                  checked={todos}
                  onChange={(e) => setTodos(e.target.checked)}
                />
                Ver todos os prestadores
                <small>
                  {opcoes
                    ? `padrão: só os ${opcoes.total_principais} principais de ${opcoes.total_prestadores}`
                    : ""}
                </small>
              </label>
              {(uf || municipio || zona) && (
                <button
                  type="button"
                  className="secundario btn-compacto"
                  onClick={() => escolherUf("")}
                >
                  Limpar localização
                </button>
              )}
            </div>

            {modo === "hospital" && nOperadoras > 0 && (
              <details className="simular-operadoras">
                <summary>
                  Colunas por operadora
                  <span className="muted">
                    {operadorasSel.length ? ` · ${operadorasSel.length} escolhida(s)` : " · todas"}
                  </span>
                </summary>
                <div className="simular-operadoras-lista">
                  {(opcoes.operadoras || []).map((o) => (
                    <label key={o.nome} className="simular-check">
                      <input
                        type="checkbox"
                        checked={operadorasSel.includes(o.nome)}
                        onChange={() => alternarOperadora(o.nome)}
                      />
                      {o.nome}
                    </label>
                  ))}
                  {operadorasSel.length > 0 && (
                    <button
                      type="button"
                      className="secundario btn-compacto"
                      onClick={() => setOperadorasSel([])}
                    >
                      Todas
                    </button>
                  )}
                </div>
              </details>
            )}
          </div>
        </section>

        <section className="simular-resultado" aria-live="polite">
          {!consultaAtiva && (
            <div className="notice notice--green">
              <div className="notice-icon" aria-hidden="true">
                i
              </div>
              <div>
                <b>
                  {modo === "hospital" ? "Digite um ou mais hospitais" : "Escolha operadora e plano"}
                </b>
                <p>
                  {modo === "hospital"
                    ? "A tabela mostra uma linha por unidade e uma coluna por plano que a cobre."
                    : "A tabela lista onde o plano atende, agrupado por município."}
                </p>
              </div>
            </div>
          )}

          {erro && <p className="erro">{erro}</p>}
          {carregando && !resp && <p className="muted">Consultando…</p>}

          {resp && (
            <div className="panel simular-painel">
              <div className="panel-head">
                <div>
                  <h2>
                    {resp.modo === "hospital"
                      ? "Planos que cobrem os hospitais"
                      : `Onde atende — ${resp.colunas[0]?.plano}`}
                  </h2>
                  <p>
                    {resp.requer_confirmacao ? "Volume alto" : textoContagem(resp)}
                    {ms != null && !resp.requer_confirmacao ? (
                      <span className="simular-ms"> · {ms} ms</span>
                    ) : null}
                  </p>
                </div>
                {resp.ocultos_nao_principais > 0 && !resp.mostrando_todos && (
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    onClick={() => setTodos(true)}
                  >
                    Ver todos (+{resp.ocultos_nao_principais})
                  </button>
                )}
              </div>
              <div className="panel-body">
                {resp.requer_confirmacao && (
                  <div className="notice notice--amber" role="status">
                    <div className="notice-icon" aria-hidden="true">
                      !
                    </div>
                    <div>
                      <b>Muitos prestadores</b>
                      <p>{resp.aviso}</p>
                      <div className="simular-acoes-aviso">
                        <button
                          type="button"
                          className="btn-compacto"
                          onClick={() => setConfirmadoPara(chaveConsulta)}
                        >
                          Listar os {resp.total_encontrado - resp.ocultos_nao_principais} prestadores
                        </button>
                        {semFiltroGeo && <span className="muted">ou escolha um estado acima</span>}
                      </div>
                    </div>
                  </div>
                )}

                {!resp.requer_confirmacao && resp.aviso && (
                  <div className="notice notice--amber" role="status">
                    <div className="notice-icon" aria-hidden="true">
                      !
                    </div>
                    <div>
                      <p>{resp.aviso}</p>
                    </div>
                  </div>
                )}

                {resp.sem_cobertura && (
                  <div className="notice notice--amber" role="status">
                    <div className="notice-icon" aria-hidden="true">
                      !
                    </div>
                    <div>
                      <b>Nenhum plano da base cobre estes prestadores</b>
                      <p>
                        Eles estão na base, mas sem cobertura hospitalar nos planos
                        (hospital geral, hospital-dia, pronto-socorro ou maternidade).
                      </p>
                    </div>
                  </div>
                )}

                {haRedeVerticalizada(blocosVisiveis) && (
                  <div className="notice notice--green" role="note">
                    <div className="notice-icon" aria-hidden="true">
                      i
                    </div>
                    <div>
                      <b>Rede própria de operadora</b>
                      <p>
                        Hospitais marcados como «Rede própria» pertencem à rede de uma operadora:
                        aparecem cobertos nos planos dela e vazios nos demais. Isso é esperado — não
                        é falha da base.
                      </p>
                    </div>
                  </div>
                )}

                {blocosVisiveis.length > 0 && <TabelaResultado resp={resp} />}

                {blocosVisiveis.length > 0 && (
                  <p className="simular-legenda">
                    {LEGENDA_COBERTURA.map(([cod, nome]) => (
                      <span key={cod}>
                        <b>{cod}</b> {nome}
                      </span>
                    ))}
                  </p>
                )}
              </div>
            </div>
          )}
        </section>
          </>
        )}
      </main>
    </div>
  );
}
