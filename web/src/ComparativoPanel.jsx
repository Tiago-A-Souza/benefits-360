import { useEffect, useState } from "react";
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
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  return (
    <section className="cartao">
      <h2>Comparativo financeiro</h2>
      <p className="muted">
        Após confirmar vidas, configuração, propostas e associações, calcule o comparativo.
      </p>

      <h3>Antes de calcular</h3>
      <Pendencias items={pendencias} />

      <button type="button" onClick={handleCalcular} disabled={carregando}>
        {carregando ? "Calculando…" : "Calcular comparativo"}
      </button>
      {erro && <p className="erro">{erro}</p>}

      {resultado && (
        <>
          {!resultado.calculo_realizado ? (
            <p className="erro">O cálculo não pôde ser concluído.</p>
          ) : (
            <>
              <p>
                Beneficiários considerados:{" "}
                <strong>{resultado.beneficiarios_calculados}</strong>
              </p>
              {resultado.validade_proposta && (
                <p className="muted">Validade da proposta: {resultado.validade_proposta}</p>
              )}
              {resultado.totais && (
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
              )}

              {resultado.secoes?.map((secao) => (
                <div key={secao.regime_tipo} className="cartao cartao--interno">
                  <h3>{secao.rotulo}</h3>
                  {secao.diferenca_mensal_reais && (
                    <p>
                      {secao.rotulo_diferenca_mensal}: {secao.diferenca_mensal_reais} / mês
                    </p>
                  )}
                  {secao.vidas?.length > 0 && (
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
                </div>
              ))}
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
