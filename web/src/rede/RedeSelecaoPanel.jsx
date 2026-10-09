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
    return [...s].sort();
  }, [linhas]);

  const municipios = useMemo(() => {
    const s = new Set();
    linhas.forEach((ln) => {
      if (ln.municipio) s.add(ln.municipio);
    });
    return [...s].sort();
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
    return <p className="carregando">Carregando rede credenciada…</p>;
  }
  if (erro) {
    return <p className="erro">{erro}</p>;
  }

  const aviso = dados?.aviso_sem_localizacao;

  return (
    <section className="painel-etapa rede-selecao-etapa">
      <header className="cabecalho-etapa">
        <p className="etapa-kicker">
          Etapa {etapaIndice} de {totalEtapas}
        </p>
        <h1>{rotulo}</h1>
        <p className="lead">
          Marque os hospitais que entram no documento. O padrão são os principais
          da base; desmarque o que não deve aparecer para o cliente.
        </p>
      </header>

      {aviso && (
        <div className="aviso-acomodacao aviso-acomodacao--info" role="status">
          {aviso}
        </div>
      )}

      {!aviso && (
        <>
          <div className="rede-selecao-filtros">
            <label>
              Zona
              <select value={filtroZona} onChange={(e) => setFiltroZona(e.target.value)}>
                <option value="">Todas</option>
                {zonas.map((z) => (
                  <option key={z} value={z}>
                    {z}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Município
              <select value={filtroMun} onChange={(e) => setFiltroMun(e.target.value)}>
                <option value="">Todos</option>
                {municipios.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Busca
              <input
                type="search"
                value={filtroNome}
                onChange={(e) => setFiltroNome(e.target.value)}
                placeholder="Nome do prestador"
              />
            </label>
          </div>

          <p className="rede-selecao-contador-visiveis" aria-live="polite">
            {linhasVisiveis.length} de {linhas.length} prestador(es) visível(is)
          </p>

          <div className="rede-selecao-tabela-wrap">
            <table className="tabela-densa rede-selecao-tabela">
              <thead>
                <tr>
                  <th>Incl.</th>
                  <th>Prestador</th>
                  <th>Município</th>
                  <th>Zona</th>
                </tr>
              </thead>
              <tbody>
                {linhasVisiveis.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="muted">
                      Nenhum prestador corresponde aos filtros.
                    </td>
                  </tr>
                ) : null}
                {linhasVisiveis.map((ln, idx) => {
                  const incl = !excluidos.has(ln.linha_id);
                  return (
                    <tr key={`${ln.secao}|${ln.bloco}|${ln.linha_id}|${idx}`}>
                      <td>
                        <input
                          type="checkbox"
                          checked={incl}
                          onChange={() => toggle(ln.linha_id)}
                          aria-label="Incluir prestador"
                        />
                      </td>
                      <td>{ln.prestador}</td>
                      <td>{ln.municipio}</td>
                      <td>{ln.zona || "—"}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <p className="rede-selecao-contador">
        {linhas.length - excluidos.size} de {linhas.length} prestador(es) incluído(s)
      </p>
    </section>
  );
}
