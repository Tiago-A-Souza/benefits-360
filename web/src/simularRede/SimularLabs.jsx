import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import {
  consultarRedePorLaboratorio,
  mensagemErroOperador,
  obterOpcoesSimulacaoLaboratorio,
} from "../api";
import { gruposDeOperadora, municipiosDaUf } from "./opcoesSimulacao";

function textoMunicipios(lista) {
  return (lista || []).join(", ");
}

function TabelaLabs({ resp }) {
  const colunas = resp.colunas;
  const grupos = gruposDeOperadora(colunas);
  const largura = 1 + colunas.length;
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
          {resp.blocos.map((bloco) => (
            <Fragment key={bloco.titulo || bloco.municipio || "labs"}>
              {bloco.titulo ? (
                <tr className="simular-bloco-linha">
                  <th colSpan={largura} scope="colgroup">
                    {bloco.titulo}
                    <span className="simular-bloco-n">{bloco.linhas.length}</span>
                  </th>
                </tr>
              ) : null}
              {bloco.linhas.map((ln) => (
                <tr key={ln.linha_id}>
                  <td className="nm rede-col-prestador">
                    <span className="cell-main">{ln.prestador_nome}</span>
                    {ln.municipios?.length ? (
                      <span className="bairro-rede">{textoMunicipios(ln.municipios)}</span>
                    ) : null}
                  </td>
                  {colunas.map((c) => {
                    const cob = ln.celulas[c.chave] || "";
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
        </tbody>
      </table>
    </div>
  );
}

export default function SimularLabs() {
  const [opcoes, setOpcoes] = useState(null);
  const [erroOpcoes, setErroOpcoes] = useState(null);

  const [texto, setTexto] = useState("");
  const [termo, setTermo] = useState("");
  const [operadorasSel, setOperadorasSel] = useState([]);
  const [uf, setUf] = useState("");
  const [municipio, setMunicipio] = useState("");

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
  const chaveConsulta = JSON.stringify(["laboratorio", termo, operadorasSel, uf, municipio]);
  const nOperadoras = opcoes?.operadoras?.length ?? 0;

  useEffect(() => {
    const minha = ++seq.current;
    const inicio = performance.now();
    setCarregando(true);
    setErro(null);
    consultarRedePorLaboratorio({
      termo,
      operadoras: operadorasSel,
      uf,
      municipio,
    })
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
  }, [chaveConsulta]);

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
        <button type="button" role="tab" aria-selected className="ativo">
          Por laboratório
          <small>Quais planos cobrem?</small>
        </button>
      </div>

      {erroOpcoes && <p className="erro">{erroOpcoes}</p>}

      <section className="panel panel-flat simular-filtros">
        <div className="panel-body">
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

          {nOperadoras > 0 && (
            <details className="simular-operadoras">
              <summary>
                Colunas por operadora
                <span className="muted">
                  {operadorasSel.length ? ` · ${operadorasSel.length} escolhida(s)` : " · todas"}
                </span>
              </summary>
              <div className="simular-operadoras-lista">
                {opcoes.operadoras.map((o) => (
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
        {erro && <p className="erro">{erro}</p>}
        {carregando && !resp && <p className="muted">Consultando…</p>}

        {resp && (
          <div className="panel simular-painel">
            <div className="panel-head">
              <div>
                <h2>Planos que cobrem os laboratórios</h2>
                <p>
                  {resp.total_linhas} {resp.total_linhas === 1 ? "marca" : "marcas"}
                  {ms != null ? <span className="simular-ms"> · {ms} ms</span> : null}
                  {opcoes?.data_base_rede ? ` · base de ${opcoes.data_base_rede}` : ""}
                </p>
              </div>
            </div>
            <div className="panel-body">
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
              {blocosVisiveis.length > 0 && <TabelaLabs resp={resp} />}
            </div>
          </div>
        )}
      </section>
    </>
  );
}
