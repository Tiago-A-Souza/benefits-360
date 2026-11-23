import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  consultarRedePorLaboratorio,
  consultarRedePorPlanoLaboratorio,
  mensagemErroOperador,
  obterOpcoesSimulacaoLaboratorio,
} from "../api";
import {
  gruposDeOperadora,
  haFiltroGeografico,
  municipiosDaUf,
  planosDaOperadora,
  textoContagemLabs,
} from "./opcoesSimulacao";

function textoMunicipios(lista) {
  return (lista || []).join(", ");
}

export function TabelaLabs({ resp }) {
  if (!resp) return <p className="muted">Nenhum resultado para mostrar.</p>;
  const colunas = resp.colunas || [];
  const blocos = resp.blocos || [];
  const grupos = gruposDeOperadora(colunas);
  const largura = 1 + colunas.length;
  const contagem = resp.contagem_por_coluna || {};
  return (
    <div className="tabela-scroll">
      <table className="conferencia rede-selecao-tabela tabela-rede simular-tabela">
        <thead>
          <tr>
            <th className="rede-col-prestador" scope="col">
              Laboratório
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
            <Fragment key={bloco.titulo || bloco.municipio || "labs"}>
              {bloco.titulo ? (
                <tr className="simular-bloco-linha">
                  <th colSpan={largura} scope="colgroup">
                    {bloco.titulo}
                    <span className="simular-bloco-n">{(bloco.linhas || []).length}</span>
                  </th>
                </tr>
              ) : null}
              {(bloco.linhas || []).map((ln) => (
                <tr
                  key={ln.linha_id}
                  className={ln.principal ? "" : "simular-linha-nao-principal"}
                >
                  <td className="nm rede-col-prestador">
                    <span className="cell-main">{ln.prestador_nome}</span>
                    {ln.municipios?.length ? (
                      <span className="bairro-rede">{textoMunicipios(ln.municipios)}</span>
                    ) : null}
                    {!ln.principal ? (
                      <span className="simular-pill simular-pill--muted">Não curado</span>
                    ) : null}
                  </td>
                  {colunas.map((c) => {
                    const cob = (ln.celulas && ln.celulas[c.chave]) || "";
                    return (
                      <td key={c.chave} className={`rede-col-plano ${cob ? "on" : "off"}`}>
                        {cob}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </Fragment>
          ))}
          {colunas.length > 0 && (
            <tr className="cont-rede">
              <td>Cobertos</td>
              {colunas.map((c) => (
                <td key={c.chave}>{contagem[c.chave] ?? 0}</td>
              ))}
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}

export default function SimularLabs() {
  const [opcoes, setOpcoes] = useState(null);
  const [erroOpcoes, setErroOpcoes] = useState(null);

  const [modo, setModo] = useState("laboratorio");
  const [texto, setTexto] = useState("");
  const [termo, setTermo] = useState("");
  const [operadorasSel, setOperadorasSel] = useState([]);
  const [opPlano, setOpPlano] = useState("");
  const [plano, setPlano] = useState("");
  const [uf, setUf] = useState("");
  const [municipio, setMunicipio] = useState("");
  const [todos, setTodos] = useState(false);
  const [confirmadoPara, setConfirmadoPara] = useState("");

  const [resp, setResp] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [ms, setMs] = useState(null);
  const seq = useRef(0);

  useEffect(() => {
    let vivo = true;
    obterOpcoesSimulacaoLaboratorio()
      .then((o) => vivo && setOpcoes(o))
      .catch((e) =>
        vivo && setErroOpcoes(mensagemErroOperador(e, "Falha ao carregar os laboratórios."))
      );
    return () => {
      vivo = false;
    };
  }, []);

  const municipios = useMemo(() => municipiosDaUf(opcoes, uf), [opcoes, uf]);
  const planos = useMemo(() => planosDaOperadora(opcoes, opPlano), [opcoes, opPlano]);
  const filtros = { uf, municipio, todos };
  const semFiltroGeo = !haFiltroGeografico(filtros);

  const chaveConsulta = JSON.stringify(
    modo === "laboratorio"
      ? ["laboratorio", termo, operadorasSel, uf, municipio, todos]
      : ["plano", plano, uf, municipio, todos]
  );
  const confirmar = confirmadoPara === chaveConsulta;
  const consultaAtiva = modo === "laboratorio" || Boolean(plano);
  const nOperadoras = opcoes?.operadoras?.length ?? 0;

  useEffect(() => {
    if (!consultaAtiva) {
      setResp(null);
      setErro(null);
      setMs(null);
      return;
    }
    const minha = ++seq.current;
    const inicio = performance.now();
    setCarregando(true);
    setErro(null);
    const chamada =
      modo === "laboratorio"
        ? consultarRedePorLaboratorio({
            termo,
            operadoras: operadorasSel,
            uf,
            municipio,
            todos,
            confirmar,
          })
        : consultarRedePorPlanoLaboratorio({
            plano,
            uf,
            municipio,
            todos,
            confirmar,
          });
    chamada
      .then((r) => {
        if (seq.current !== minha) return;
        setResp(r);
        setMs(Math.round(performance.now() - inicio));
      })
      .catch((e) => {
        if (seq.current !== minha) return;
        setResp(null);
        setErro(mensagemErroOperador(e, "Falha na consulta."));
      })
      .finally(() => {
        if (seq.current === minha) setCarregando(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chaveConsulta, confirmar, consultaAtiva]);

  function submeter(e) {
    e.preventDefault();
    setTermo(texto.trim());
  }

  function escolherUf(valor) {
    setUf(valor);
    setMunicipio("");
  }

  function alternarOperadora(nome) {
    setOperadorasSel((atual) =>
      atual.includes(nome) ? atual.filter((o) => o !== nome) : [...atual, nome]
    );
  }

  const blocosVisiveis = resp && !resp.requer_confirmacao ? resp.blocos : [];

  return (
    <>
      <div className="simular-modos" role="tablist" aria-label="Tipo de consulta de laboratório">
        <button
          type="button"
          role="tab"
          aria-selected={modo === "laboratorio"}
          className={modo === "laboratorio" ? "ativo" : ""}
          onClick={() => setModo("laboratorio")}
        >
          Por laboratório
          <small>Quais planos cobrem?</small>
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={modo === "plano"}
          className={modo === "plano" ? "ativo" : ""}
          onClick={() => setModo("plano")}
        >
          Por plano
          <small>Onde o plano atende?</small>
        </button>
      </div>

      {erroOpcoes && <p className="erro">{erroOpcoes}</p>}

      <section className="panel panel-flat simular-filtros">
        <div className="panel-body">
          {modo === "laboratorio" ? (
            <form className="simular-busca" onSubmit={submeter}>
              <div className="field simular-busca-campo">
                <label className="cmp-filtro-label" htmlFor="simular-lab">
                  Marca ou prestador
                </label>
                <input
                  id="simular-lab"
                  type="search"
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  placeholder="Ex.: Delboni; Lavoisier; A+"
                  autoComplete="off"
                />
                <span className="hint">
                  Várias marcas separadas por «;» ou vírgula. Vazio lista as marcas da base.
                </span>
              </div>
              <button type="submit">Consultar</button>
            </form>
          ) : (
            <div className="catalog-filters simular-plano">
              <div className="field">
                <label className="cmp-filtro-label" htmlFor="simular-lab-operadora">
                  Operadora
                </label>
                <select
                  id="simular-lab-operadora"
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
                <label className="cmp-filtro-label" htmlFor="simular-lab-plano">
                  Plano
                </label>
                <select
                  id="simular-lab-plano"
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
              <label className="cmp-filtro-label" htmlFor="simular-lab-uf">
                Estado
              </label>
              <select
                id="simular-lab-uf"
                value={uf}
                onChange={(e) => escolherUf(e.target.value)}
              >
                <option value="">Todos</option>
                {(opcoes?.ufs || []).map((u) => (
                  <option key={u.uf} value={u.uf}>
                    {u.uf}
                  </option>
                ))}
              </select>
            </div>
            <div className="field">
              <label className="cmp-filtro-label" htmlFor="simular-lab-municipio">
                Município
              </label>
              <select
                id="simular-lab-municipio"
                value={municipio}
                onChange={(e) => setMunicipio(e.target.value)}
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
          </div>

          <div className="simular-opcoes">
            <label className="simular-check">
              <input
                type="checkbox"
                checked={todos}
                onChange={(e) => setTodos(e.target.checked)}
              />
              Ver todos os laboratórios
              <small>
                {opcoes
                  ? `padrão: só as ${opcoes.total_principais} marcas de ${opcoes.total_prestadores}`
                  : ""}
              </small>
            </label>
            {(uf || municipio) && (
              <button
                type="button"
                className="secundario btn-compacto"
                onClick={() => escolherUf("")}
              >
                Limpar localização
              </button>
            )}
          </div>

          {modo === "laboratorio" && nOperadoras > 0 && (
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
              <b>Escolha operadora e plano</b>
              <p>A tabela lista as marcas cobertas pelo plano na geografia escolhida.</p>
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
                  {resp.modo === "laboratorio"
                    ? "Planos que cobrem os laboratórios"
                    : `Onde atende — ${resp.colunas[0]?.plano || ""}`}
                </h2>
                <p>
                  {resp.requer_confirmacao ? "Volume alto" : textoContagemLabs(resp)}
                  {ms != null && !resp.requer_confirmacao ? (
                    <span className="simular-ms"> · {ms} ms</span>
                  ) : null}
                  {opcoes?.data_base_rede ? ` · base de ${opcoes.data_base_rede}` : ""}
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
                    <b>Muitos laboratórios</b>
                    <p>{resp.aviso}</p>
                    <div className="simular-acoes-aviso">
                      <button
                        type="button"
                        className="btn-compacto"
                        onClick={() => setConfirmadoPara(chaveConsulta)}
                      >
                        Listar os {resp.total_encontrado} laboratórios
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

              {resp.aviso_porto && (
                <div className="notice notice--amber" role="status">
                  <div className="notice-icon" aria-hidden="true">
                    !
                  </div>
                  <div>
                    <b>Porto Seguro / Medservice</b>
                    <p>{resp.aviso_porto}</p>
                  </div>
                </div>
              )}

              {blocosVisiveis.length > 0 && <TabelaLabs resp={resp} />}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
