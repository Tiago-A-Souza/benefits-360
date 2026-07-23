import { useEffect, useMemo, useState } from "react";
import { calcularEstudo, obterPendencias } from "./api";

function Pendencias({ items }) {
  if (!items?.length) return <p className="ok">Nenhuma pendência bloqueante nesta verificação.</p>;
  return (
    <ul className="pendencias">
      {items.map((p, i) => (
        <li key={i} className={`pendencia pendencia--${p.tipo}`}>
          <strong>{p.titulo}</strong>
          <p>{p.descricao}</p>
          {p.acao_sugerida && <p className="acao">{p.acao_sugerida}</p>}
        </li>
      ))}
    </ul>
  );
}

function TabelaResumoPropostas({ propostas, baselineRotulo }) {
  const grupos = useMemo(() => {
    const ordem = ["sem_copart", "com_copart"];
    const mapa = new Map();
    for (const p of propostas) {
      const chave = p.grupo_regime || (p.regime_tipo === "sem" ? "sem_copart" : "com_copart");
      if (!mapa.has(chave)) mapa.set(chave, []);
      mapa.get(chave).push(p);
    }
    return ordem.filter((g) => mapa.has(g)).map((g) => ({ id: g, propostas: mapa.get(g) }));
  }, [propostas]);

  const tituloGrupo = {
    sem_copart: "Sem coparticipação",
    com_copart: "Com coparticipação",
  };

  return (
    <div className="comparativo-multi-resumo">
      {grupos.map((grupo) => (
        <section
          key={grupo.id}
          className={`comparativo-grupo-regime comparativo-grupo-regime--${grupo.id}`}
        >
          <h3>{tituloGrupo[grupo.id] || grupo.id}</h3>
          <div className="comparativo-tabela-scroll">
            <table className="comparativo comparativo--multi">
              <thead>
                <tr>
                  <th>Proposta</th>
                  <th>Coparticipação</th>
                  <th>Plano atual ({baselineRotulo})</th>
                  <th>Total mensal</th>
                  <th>Diferença (R$)</th>
                  <th>Diferença (%)</th>
                  <th>Diferença anual</th>
                </tr>
              </thead>
              <tbody>
                {grupo.propostas.map((p) => (
                  <tr
                    key={p.opcao_id}
                    className={
                      p.totais?.diferenca_semantica
                        ? `destaque destaque--${p.totais.diferenca_semantica}`
                        : ""
                    }
                  >
                    <td>
                      <strong>{p.plano_nome}</strong>
                    </td>
                    <td>{p.regime_coparticipacao}</td>
                    <td>{p.totais?.atual_mensal_reais ?? "—"}</td>
                    <td>{p.totais?.proposta_mensal_reais ?? "—"}</td>
                    <td>{p.totais?.diferenca_mensal_reais ?? "—"}</td>
                    <td>{p.diferenca_percentual ?? "—"}</td>
                    <td>{p.totais?.diferenca_anual_reais ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ))}
    </div>
  );
}

function DetalheProposta({ proposta }) {
  const secao = proposta.secoes?.[0];
  return (
    <details className="comparativo-detalhe-proposta cartao cartao--interno">
      <summary>
        <span className="comparativo-detalhe-nome">{proposta.plano_nome}</span>
        <span className="muted comparativo-detalhe-meta">
          {proposta.regime_coparticipacao}
          {proposta.totais?.proposta_mensal_reais
            ? ` · ${proposta.totais.proposta_mensal_reais}/mês`
            : ""}
        </span>
      </summary>
      {proposta.pendencias?.length > 0 && (
        <div className="comparativo-detalhe-pendencias">
          <Pendencias items={proposta.pendencias} />
        </div>
      )}
      {secao?.vidas?.length > 0 && (
        <table className="conferencia">
          <thead>
            <tr>
              <th>Beneficiário</th>
              <th>Idade</th>
              <th>Faixa</th>
              <th>Parentesco</th>
              <th>Plano atual</th>
              <th>Atual</th>
              <th>Proposta</th>
              <th>Diferença</th>
            </tr>
          </thead>
          <tbody>
            {secao.vidas.map((v) => (
              <tr key={v.vida_id}>
                <td>{v.nome}</td>
                <td>{v.idade ?? "—"}</td>
                <td>{v.faixa ?? "—"}</td>
                <td>{v.parentesco ?? "—"}</td>
                <td>{v.plano_atual ?? "—"}</td>
                <td>{v.atual_reais ?? "—"}</td>
                <td>{v.proposta_reais ?? "—"}</td>
                <td>{v.diff_mes_reais ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </details>
  );
}

export default function ComparativoPanel({ estudoId }) {
  const [pendencias, setPendencias] = useState([]);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [auditoriaAberta, setAuditoriaAberta] = useState(false);

  useEffect(() => {
    if (!estudoId) return;
    obterPendencias(estudoId)
      .then(setPendencias)
      .catch(() => setPendencias([]));
  }, [estudoId]);

  async function handleCalcular() {
    setCarregando(true);
    setErro(null);
    setResultado(null);
    try {
      const p = await obterPendencias(estudoId);
      setPendencias(p);
      const bloqueios = p.filter((x) => x.tipo === "bloqueio");
      if (bloqueios.length) {
        setErro("Complete as pendências indicadas antes de calcular.");
        return;
      }
      const data = await calcularEstudo(estudoId);
      setResultado(data);
      if (data.consistencia && !data.consistencia.consistente) {
        setErro(data.consistencia.mensagem);
      }
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  const propostasOk = resultado?.propostas?.filter((p) => p.calculo_realizado) || [];
  const baselineRotulo = propostasOk[0]?.totais?.baseline_rotulo || "Contrato reajustado";

  const detalhesPorGrupo = useMemo(() => {
    if (!resultado?.propostas?.length) return [];
    const ordem = ["sem_copart", "com_copart"];
    const mapa = new Map();
    for (const p of resultado.propostas) {
      const chave = p.grupo_regime || (p.regime_tipo === "sem" ? "sem_copart" : "com_copart");
      if (!mapa.has(chave)) mapa.set(chave, []);
      mapa.get(chave).push(p);
    }
    return ordem.filter((g) => mapa.has(g)).map((g) => ({ id: g, propostas: mapa.get(g) }));
  }, [resultado]);

  return (
    <section className="cartao">
      <h2>Comparativo financeiro</h2>
      <p className="muted">
        Após confirmar vidas, configuração, propostas e associações, calcule o comparativo de todas
        as propostas selecionadas.
      </p>

      <h3>Antes de calcular</h3>
      <Pendencias items={pendencias} />

      <button type="button" onClick={handleCalcular} disabled={carregando}>
        {carregando ? "Calculando…" : "Calcular comparativo"}
      </button>
      {erro && <p className="erro">{erro}</p>}

      {resultado && (
        <>
          {resultado.consistencia && (
            <div
              className={
                resultado.consistencia.consistente
                  ? "comparativo-consistencia comparativo-consistencia--ok"
                  : "comparativo-consistencia comparativo-consistencia--erro"
              }
            >
              <strong>Consistência do comparativo</strong>
              <p>
                {resultado.consistencia.propostas_selecionadas} proposta(s) ·{" "}
                {resultado.consistencia.cenarios_configurados} cenário(s) ·{" "}
                {resultado.consistencia.resultados_apresentados} resultado(s)
              </p>
              {resultado.consistencia.mensagem && (
                <p className="erro">{resultado.consistencia.mensagem}</p>
              )}
            </div>
          )}

          {!resultado.calculo_realizado ? (
            <p className="erro">
              O comparativo não está completo — corrija a inconsistência antes de avançar para
              aprovação.
            </p>
          ) : (
            <>
              <p>
                Beneficiários considerados:{" "}
                <strong>{resultado.beneficiarios_calculados}</strong>
              </p>
              {resultado.validade_proposta && (
                <p className="muted">Validade da proposta: {resultado.validade_proposta}</p>
              )}

              {resultado.propostas?.length > 1 ? (
                <TabelaResumoPropostas
                  propostas={resultado.propostas}
                  baselineRotulo={baselineRotulo}
                />
              ) : (
                resultado.totais && (
                  <table className="comparativo">
                    <tbody>
                      <tr>
                        <td>Plano atual ({resultado.totais.baseline_rotulo})</td>
                        <td>{resultado.totais.atual_mensal_reais}</td>
                      </tr>
                      <tr>
                        <td>Proposta (mensal)</td>
                        <td>{resultado.totais.proposta_mensal_reais}</td>
                      </tr>
                      <tr className={`destaque destaque--${resultado.totais.diferenca_semantica}`}>
                        <td>{resultado.totais.rotulo_diferenca_mensal}</td>
                        <td>{resultado.totais.diferenca_mensal_reais}</td>
                      </tr>
                      <tr className={`destaque destaque--${resultado.totais.diferenca_semantica}`}>
                        <td>{resultado.totais.rotulo_diferenca_anual}</td>
                        <td>{resultado.totais.diferenca_anual_reais}</td>
                      </tr>
                    </tbody>
                  </table>
                )
              )}

              {resultado.propostas?.length > 0 && (
                <section className="comparativo-detalhes-secao">
                  <h3>Detalhamento por proposta</h3>
                  {detalhesPorGrupo.map((grupo) => (
                    <div
                      key={grupo.id}
                      className={`comparativo-grupo-regime comparativo-grupo-regime--${grupo.id}`}
                    >
                      <h4>
                        {grupo.id === "sem_copart"
                          ? "Sem coparticipação"
                          : "Com coparticipação"}
                      </h4>
                      {grupo.propostas.map((p) => (
                        <DetalheProposta key={p.opcao_id} proposta={p} />
                      ))}
                    </div>
                  ))}
                </section>
              )}
            </>
          )}

          <h3>Pendências e alertas</h3>
          <Pendencias items={resultado.pendencias} />

          <section className="cartao cartao--auditoria">
            <button
              type="button"
              className="link"
              onClick={() => setAuditoriaAberta((v) => !v)}
            >
              {auditoriaAberta ? "Ocultar" : "Mostrar"} auditoria técnica
            </button>
            {auditoriaAberta && (
              <table className="auditoria">
                <thead>
                  <tr>
                    <th>Código</th>
                    <th>Nível</th>
                    <th>Detalhe</th>
                  </tr>
                </thead>
                <tbody>
                  {resultado.auditoria.map((a, i) => (
                    <tr key={i}>
                      <td>{a.codigo}</td>
                      <td>{a.severidade}</td>
                      <td>{a.mensagem}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      )}
    </section>
  );
}
