import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { obterRedeSelecao, salvarRedeSelecao } from "../api";
import { tituloPasso } from "../fluxo/passos";
import { filtrarLinhasRede } from "./redeSelecaoFiltros.js";

function linhasFlat(secoes) {
  const out = [];
  for (const sec of secoes || []) {
    for (const bloco of sec.blocos || []) {
      for (const ln of bloco.linhas || []) {
        out.push({
          linha_id: ln.linha_id,
          prestador: ln.prestador || "",
          municipio: ln.municipio || "",
          bairro: ln.bairro || "",
          zona: ln.zona || "",
          secao: sec.rotulo,
          bloco: bloco.titulo,
        });
      }
    }
  }
  return out;
}

function rotuloMunicipio(chave) {
  if (!chave) return "—";
  const ponto = chave.indexOf(".");
  if (ponto >= 0 && ponto < chave.length - 1) return chave.slice(ponto + 1).trim();
  return chave;
}

function rotuloZona(z) {
  if (!z) return "—";
  return z;
}

export default function RedeSelecaoPanel({
  estudoId,
  etapaIndice,
  totalEtapas,
  onRegistrarAvanco,
}) {
  const [dados, setDados] = useState(null);
  const [excluidos, setExcluidos] = useState(new Set());
  const [revisada, setRevisada] = useState(false);
  const [filtroZona, setFiltroZona] = useState("");
  const [filtroMun, setFiltroMun] = useState("");
  const [filtroNome, setFiltroNome] = useState("");
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(true);

  const excluidosRef = useRef(excluidos);
  const revisadaRef = useRef(revisada);
  excluidosRef.current = excluidos;
  revisadaRef.current = revisada;

  const recarregar = useCallback(async () => {
    setCarregando(true);
    setErro(null);
    try {
      const r = await obterRedeSelecao(estudoId);
      setDados(r);
      setExcluidos(new Set(r.excluidos || []));
      setRevisada(Boolean(r.revisada));
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }, [estudoId]);

  useEffect(() => {
    recarregar();
  }, [recarregar]);

  const linhas = useMemo(() => linhasFlat(dados?.secoes), [dados]);

  const zonas = useMemo(() => {
    const s = new Set();
    linhas.forEach((ln) => {
      if (ln.zona) s.add(ln.zona);
    });
    return [...s].sort((a, b) => rotuloZona(a).localeCompare(rotuloZona(b), "pt-BR"));
  }, [linhas]);

  const municipios = useMemo(() => {
    const s = new Set();
    linhas.forEach((ln) => {
      if (ln.municipio) s.add(ln.municipio);
    });
    return [...s].sort((a, b) =>
      rotuloMunicipio(a).localeCompare(rotuloMunicipio(b), "pt-BR")
    );
  }, [linhas]);

  const linhasVisiveis = useMemo(
    () =>
      filtrarLinhasRede(linhas, {
        zona: filtroZona,
        municipio: filtroMun,
        nome: filtroNome,
      }),
    [linhas, filtroZona, filtroMun, filtroNome]
  );

  const filtrosAtivos =
    (filtroZona ? 1 : 0) + (filtroMun ? 1 : 0) + (filtroNome.trim() ? 1 : 0);

  const incluidos = useMemo(
    () => linhas.filter((ln) => !excluidos.has(ln.linha_id)).length,
    [linhas, excluidos]
  );

  const toggle = (linhaId) => {
    revisadaRef.current = true;
    setRevisada(true);
    setExcluidos((prev) => {
      const next = new Set(prev);
      if (next.has(linhaId)) next.delete(linhaId);
      else next.add(linhaId);
      excluidosRef.current = next;
      return next;
    });
  };

  function limparFiltros() {
    setFiltroZona("");
    setFiltroMun("");
    setFiltroNome("");
  }

  useEffect(() => {
    if (!onRegistrarAvanco) return undefined;
    return onRegistrarAvanco(async () => {
      await salvarRedeSelecao(
        estudoId,
        [...excluidosRef.current],
        revisadaRef.current
      );
      return true;
    });
  }, [onRegistrarAvanco, estudoId]);

  const rotulo = tituloPasso(null, "rede");

  if (carregando) {
    return (
      <section className="etapa-fluxo">
        <p className="muted">Carregando rede credenciada…</p>
      </section>
    );
  }
  if (erro && !dados) {
    return (
      <section className="etapa-fluxo">
        <p className="erro">{erro}</p>
      </section>
    );
  }

  const aviso = dados?.aviso_sem_localizacao;

  return (
    <section className="etapa-fluxo rede-selecao-etapa">
      <div className="page-head">
        <div>
          <div className="page-kicker">
            Etapa {etapaIndice} de {totalEtapas}
          </div>
          <h1>{rotulo}</h1>
          <p className="lead">
            Marque os hospitais que entram no documento. O padrão são os principais
            da base; desmarque o que não deve aparecer para o cliente.
          </p>
        </div>
        <div className="page-head-acoes">
          {revisada ? (
            <span className="badge badge--ok">Seleção revisada</span>
          ) : (
            <span className="badge badge--alerta">Revise antes de avançar</span>
          )}
          <span className="badge badge--blue">
            {incluidos} de {linhas.length} incluído(s)
          </span>
        </div>
      </div>

      {aviso && (
        <div className="notice notice--amber" role="status">
          <div className="notice-icon" aria-hidden="true">
            !
          </div>
          <div>
            <b>Localização dos beneficiários</b>
            <p>{aviso}</p>
          </div>
        </div>
      )}

      {erro && <p className="erro">{erro}</p>}

      {!aviso && linhas.length > 0 && (
        <>
          <section className="panel panel-flat cmp-filtros">
            <div className="panel-head">
              <div>
                <h2>Filtros</h2>
                <p>
                  {linhasVisiveis.length} de {linhas.length} prestador(es) visível(is)
                  {filtrosAtivos > 0 ? ` · ${filtrosAtivos} filtro(s) ativo(s)` : ""}
                </p>
              </div>
              {filtrosAtivos > 0 && (
                <button type="button" className="secundario btn-compacto" onClick={limparFiltros}>
                  Limpar filtros
                </button>
              )}
            </div>
            <div className="panel-body">
              <div className="cmp-filtros-grid catalog-filters">
                <div className="cmp-filtro field">
                  <label className="cmp-filtro-label" htmlFor="rede-filtro-zona">
                    Zona
                  </label>
                  <select
                    id="rede-filtro-zona"
                    value={filtroZona}
                    onChange={(e) => setFiltroZona(e.target.value)}
                  >
                    <option value="">Todas</option>
                    {zonas.map((z) => (
                      <option key={z} value={z}>
                        {rotuloZona(z)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="cmp-filtro field">
                  <label className="cmp-filtro-label" htmlFor="rede-filtro-mun">
                    Município
                  </label>
                  <select
                    id="rede-filtro-mun"
                    value={filtroMun}
                    onChange={(e) => setFiltroMun(e.target.value)}
                  >
                    <option value="">Todos</option>
                    {municipios.map((m) => (
                      <option key={m} value={m}>
                        {rotuloMunicipio(m)}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="cmp-filtro cmp-filtro--ordem field">
                  <label className="cmp-filtro-label" htmlFor="rede-filtro-nome">
                    Busca por nome
                  </label>
                  <input
                    id="rede-filtro-nome"
                    type="search"
                    value={filtroNome}
                    onChange={(e) => setFiltroNome(e.target.value)}
                    placeholder="Nome do prestador"
                    autoComplete="off"
                  />
                </div>
              </div>
            </div>
          </section>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Prestadores</h2>
                <p>
                  Desmarque os que não devem aparecer no HTML entregue ao cliente.
                </p>
              </div>
            </div>
            <div className="panel-body">
              <div className="tabela-scroll">
                <table className="conferencia rede-selecao-tabela">
                  <thead>
                    <tr>
                      <th className="rede-col-incl">Incl.</th>
                      <th>Prestador</th>
                      <th>Município</th>
                      <th>Bairro</th>
                      <th>Zona</th>
                    </tr>
                  </thead>
                  <tbody>
                    {linhasVisiveis.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="muted">
                          Nenhum prestador corresponde aos filtros — limpe ou ajuste a busca.
                        </td>
                      </tr>
                    ) : (
                      linhasVisiveis.map((ln) => {
                        const incl = !excluidos.has(ln.linha_id);
                        return (
                          <tr key={ln.linha_id}>
                            <td>
                              <input
                                type="checkbox"
                                checked={incl}
                                onChange={() => toggle(ln.linha_id)}
                                aria-label={`Incluir ${ln.prestador}`}
                              />
                            </td>
                            <td>
                              <span className="cell-main">{ln.prestador}</span>
                            </td>
                            <td>{rotuloMunicipio(ln.municipio)}</td>
                            <td>{ln.bairro || "—"}</td>
                            <td>{rotuloZona(ln.zona)}</td>
                          </tr>
                        );
                      })
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </>
      )}

      {!aviso && linhas.length === 0 && (
        <p className="muted">Nenhum prestador disponível para este estudo.</p>
      )}
    </section>
  );
}
