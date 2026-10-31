import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { obterRedeSelecao, removerRedeManual, salvarRedeSelecao } from "../api";
import CelulaCobertura from "./CelulaCobertura.jsx";
import InclusaoManual from "./InclusaoManual.jsx";
import { tituloPasso } from "../fluxo/passos";
import { filtrarLinhasRede } from "./redeSelecaoFiltros.js";

function todasLinhas(secoes) {
  const out = [];
  for (const sec of secoes || []) {
    for (const bloco of sec.blocos || []) {
      for (const ln of bloco.linhas || []) {
        out.push({
          ...ln,
          secao: sec.rotulo,
          bloco: bloco.titulo,
        });
      }
    }
  }
  return out;
}

function celulaCobertura(val) {
  const t = (val || "").trim();
  return t && t !== "—" ? t : "";
}

function rotuloPlanoColuna(col) {
  if (col.contrato_atual) return { op: "Contrato atual", pl: col.plano_nome };
  return { op: col.operadora, pl: col.plano_nome };
}

function idsLinhasSecao(sec) {
  const ids = [];
  for (const bloco of sec.blocos || []) {
    for (const ln of bloco.linhas || []) {
      ids.push(ln.linha_id);
    }
  }
  return ids;
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
  const [removendo, setRemovendo] = useState(null);

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

  const linhas = useMemo(() => todasLinhas(dados?.secoes), [dados]);

  const filtros = useMemo(
    () => ({ zona: filtroZona, municipio: filtroMun, nome: filtroNome }),
    [filtroZona, filtroMun, filtroNome]
  );

  const idsVisiveis = useMemo(() => {
    const vis = filtrarLinhasRede(linhas, filtros);
    return new Set(vis.map((ln) => ln.linha_id));
  }, [linhas, filtros]);

  const zonas = useMemo(() => {
    const s = new Set();
    linhas.forEach((ln) => {
      if (ln.zona) s.add(ln.zona);
    });
    return [...s].sort((a, b) => a.localeCompare(b, "pt-BR"));
  }, [linhas]);

  const municipios = useMemo(() => {
    const s = new Set();
    linhas.forEach((ln) => {
      if (ln.municipio) s.add(ln.municipio);
    });
    return [...s].sort((a, b) => {
      const la = a.includes(".") ? a.slice(a.indexOf(".") + 1) : a;
      const lb = b.includes(".") ? b.slice(b.indexOf(".") + 1) : b;
      return la.localeCompare(lb, "pt-BR");
    });
  }, [linhas]);

  const rotuloMunicipio = (chave) => {
    if (!chave) return "—";
    const ponto = chave.indexOf(".");
    if (ponto >= 0 && ponto < chave.length - 1) return chave.slice(ponto + 1).trim();
    return chave;
  };

  const linhasVisiveisCount = idsVisiveis.size;

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

  const marcarRevisada = () => {
    revisadaRef.current = true;
    setRevisada(true);
  };

  const alternarInclusaoSecao = (sec) => {
    const ids = idsLinhasSecao(sec);
    if (!ids.length) return;
    marcarRevisada();
    setExcluidos((prev) => {
      const todosIncluidos = ids.every((id) => !prev.has(id));
      const next = new Set(prev);
      if (todosIncluidos) {
        ids.forEach((id) => next.add(id));
      } else {
        ids.forEach((id) => next.delete(id));
      }
      excluidosRef.current = next;
      return next;
    });
  };

  // Incluir/remover à mão grava na hora; só a tabela é recarregada — as marcações
  // locais (excluídos, revisada) seguem como estão até avançar.
  async function removerManual(sec, ln) {
    setRemovendo(ln.linha_id);
    setErro(null);
    try {
      const nova = await removerRedeManual(estudoId, {
        prestador: ln.prestador,
        municipio: ln.municipio,
        bairro: ln.bairro,
      });
      setDados(nova);
    } catch (e) {
      setErro(e.message);
    } finally {
      setRemovendo(null);
    }
  }

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
  const temSecaoComBusca = (dados?.secoes || []).some(
    (s) => s.subgrupo_id && !s.sem_localizacao
  );

  function painelFiltros(sufixo) {
    return (
              <section className="panel panel-flat cmp-filtros">
                <div className="panel-head">
                  <div>
                    <h2>Filtros</h2>
                    <p>
                      {linhasVisiveisCount} de {linhas.length} prestador(es) visível(is)
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
                      <label className="cmp-filtro-label" htmlFor={`rede-filtro-zona-${sufixo}`}>
                        Zona
                      </label>
                      <select
                        id={`rede-filtro-zona-${sufixo}`}
                        value={filtroZona}
                        onChange={(e) => setFiltroZona(e.target.value)}
                      >
                        <option value="">Todas</option>
                        {zonas.map((z) => (
                          <option key={z} value={z}>
                            {z}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="cmp-filtro field">
                      <label className="cmp-filtro-label" htmlFor={`rede-filtro-mun-${sufixo}`}>
                        Município
                      </label>
                      <select
                        id={`rede-filtro-mun-${sufixo}`}
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
                      <label className="cmp-filtro-label" htmlFor={`rede-filtro-nome-${sufixo}`}>
                        Busca por nome
                      </label>
                      <input
                        id={`rede-filtro-nome-${sufixo}`}
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
    );
  }
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
            da base; desmarque o que não deve aparecer para o cliente. Para um hospital
            fora dos principais, use o campo «Incluir hospital fora dos principais».
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

      {!aviso && (linhas.length > 0 || temSecaoComBusca) && (
        <>
          {temSecaoComBusca && (
            <InclusaoManual estudoId={estudoId} onAtualizado={(nova) => setDados(nova)} />
          )}

          {(dados?.secoes || []).map((sec) => {
            const colunas = sec.colunas || [];
            let secaoTemLinha = false;
            const blocosRender = (sec.blocos || []).map((bloco) => {
              const linhasBloco = (bloco.linhas || []).filter((ln) =>
                idsVisiveis.has(ln.linha_id)
              );
              if (linhasBloco.length) secaoTemLinha = true;
              return { bloco, linhasBloco };
            }).filter((x) => x.linhasBloco.length > 0);

            const idsSec = idsLinhasSecao(sec);
            // Com filtro ativo, some a seção sem linha visível; seção sem nenhuma
            // linha (ainda) continua aparecendo, para permitir a busca.
            const aceitaInclusao = Boolean(sec.subgrupo_id) && !sec.sem_localizacao;
            if (!secaoTemLinha && !(idsSec.length === 0 && aceitaInclusao)) return null;
            const incluidosSec = idsSec.filter((id) => !excluidos.has(id)).length;
            const todosIncluidosSec =
              idsSec.length > 0 && incluidosSec === idsSec.length;

            return (
              <div className="panel rede-secao-panel" key={sec.rotulo}>
                <div className="panel-head">
                  <div>
                    <h2>{sec.rotulo}</h2>
                    <p>Cobertura por plano — mesma base da aba Rede do documento.</p>
                  </div>
                  <button
                    type="button"
                    className="secundario btn-compacto"
                    onClick={() => alternarInclusaoSecao(sec)}
                  >
                    {todosIncluidosSec ? "Desmarcar todos" : "Marcar todos"}
                  </button>
                </div>
                <div className="panel-body">
                  {painelFiltros(sec.subgrupo_id || sec.rotulo)}
                  {blocosRender.map(({ bloco, linhasBloco }) => (
                    <div className="rede-bloco-municipio" key={bloco.titulo}>
                      <div className="rede-bloco-titulo">{bloco.titulo}</div>
                      <div className="tabela-scroll">
                        <table className="conferencia rede-selecao-tabela tabela-rede">
                          <thead>
                            <tr>
                              <th className="rede-col-incl" scope="col">
                                Incl.
                              </th>
                              <th className="rede-col-prestador" scope="col">
                                Prestador
                              </th>
                              {colunas.map((col) => {
                                const { op, pl } = rotuloPlanoColuna(col);
                                return (
                                  <th
                                    key={col.chave}
                                    className={
                                      col.contrato_atual
                                        ? "rede-col-plano atual"
                                        : "rede-col-plano"
                                    }
                                    scope="col"
                                  >
                                    <span className="op">{op}</span>
                                    <span className="pl">{pl}</span>
                                  </th>
                                );
                              })}
                            </tr>
                          </thead>
                          <tbody>
                            {linhasBloco.map((ln) => {
                              const incl = !excluidos.has(ln.linha_id);
                              return (
                                <tr key={ln.linha_id}>
                                  <td className="rede-col-incl">
                                    <input
                                      type="checkbox"
                                      checked={incl}
                                      onChange={() => toggle(ln.linha_id)}
                                      aria-label={`Incluir ${ln.prestador}`}
                                    />
                                  </td>
                                  <td className="nm rede-col-prestador">
                                    <span className="cell-main">{ln.prestador_nome || ln.prestador}</span>
                                    {ln.bairro ? (
                                      <span className="bairro-rede">{ln.bairro}</span>
                                    ) : null}
                                    {ln.manual && (
                                      <span className="selos-linha">
                                        <span className="selo selo--manual">Manual</span>
                                        {ln.fora_criterio && (
                                          <span
                                            className="selo selo--fora"
                                            title="Sem HGER, HD, PSGER ou MAT em nenhum plano"
                                          >
                                            Fora do critério padrão
                                          </span>
                                        )}
                                        <button
                                          type="button"
                                          className="secundario btn-compacto btn-remover-manual"
                                          disabled={removendo === ln.linha_id}
                                          onClick={() => removerManual(sec, ln)}
                                        >
                                          Remover
                                        </button>
                                      </span>
                                    )}
                                  </td>
                                  {colunas.map((col) => {
                                    const cod = celulaCobertura(ln.celulas?.[col.chave]);
                                    const cls = cod ? "on" : "off";
                                    return (
                                      <td key={col.chave} className={`rede-col-plano ${cls}`}>
                                        {cod ? <CelulaCobertura texto={cod} /> : ""}
                                      </td>
                                    );
                                  })}
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}

          {linhasVisiveisCount === 0 && (
            <p className="muted">Nenhum prestador corresponde aos filtros — limpe ou ajuste a busca.</p>
          )}
        </>
      )}

      {!aviso && linhas.length === 0 && !temSecaoComBusca && (
        <p className="muted">Nenhum prestador disponível para este estudo.</p>
      )}
    </section>
  );
}
