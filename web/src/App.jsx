import { useEffect, useState } from "react";
import { calcularEstudo, listarEstudos, obterEstudo } from "./api";

const ESTUDO_PADRAO = "demo-12";

function Pendencias({ items }) {
  if (!items.length) {
    return (
      <p className="ok">Nenhuma pendência bloqueante ou alerta relevante.</p>
    );
  }
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

function Auditoria({ items }) {
  if (!items.length) return <p className="muted">Sem registros.</p>;
  return (
    <table className="auditoria">
      <thead>
        <tr>
          <th>Código</th>
          <th>Nível</th>
          <th>Detalhe</th>
        </tr>
      </thead>
      <tbody>
        {items.map((a, i) => (
          <tr key={i}>
            <td>{a.codigo}</td>
            <td>{a.severidade}</td>
            <td>{a.mensagem}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function App() {
  const [estudoId, setEstudoId] = useState(ESTUDO_PADRAO);
  const [estudos, setEstudos] = useState([]);
  const [resumo, setResumo] = useState(null);
  const [resultado, setResultado] = useState(null);
  const [carregando, setCarregando] = useState(false);
  const [erro, setErro] = useState(null);
  const [auditoriaAberta, setAuditoriaAberta] = useState(false);

  useEffect(() => {
    listarEstudos()
      .then(setEstudos)
      .catch((e) => setErro(e.message));
  }, []);

  useEffect(() => {
    setErro(null);
    setResultado(null);
    obterEstudo(estudoId)
      .then(setResumo)
      .catch((e) => setErro(e.message));
  }, [estudoId]);

  async function handleCalcular() {
    setCarregando(true);
    setErro(null);
    try {
      const data = await calcularEstudo(estudoId);
      setResultado(data);
    } catch (e) {
      setErro(e.message);
    } finally {
      setCarregando(false);
    }
  }

  return (
    <div className="pagina">
      <header>
        <h1>Comparativo financeiro</h1>
        <p className="sub">Demonstração técnica — dados fictícios</p>
      </header>

      <section className="cartao">
        <label htmlFor="estudo">Estudo</label>
        <select
          id="estudo"
          value={estudoId}
          onChange={(e) => setEstudoId(e.target.value)}
        >
          {estudos.map((id) => (
            <option key={id} value={id}>
              {id}
            </option>
          ))}
        </select>
        {resumo && (
          <div className="resumo">
            <h2>{resumo.titulo}</h2>
            <p>{resumo.descricao}</p>
            <p className="muted">
              Tipo: {resumo.formato_exibicao} · {resumo.beneficiarios_rotulo}
            </p>
          </div>
        )}
        <button type="button" onClick={handleCalcular} disabled={carregando}>
          {carregando ? "Calculando…" : "Calcular comparativo"}
        </button>
      </section>

      {erro && <p className="erro">{erro}</p>}

      {resultado && (
        <>
          <section className="cartao">
            <h2>Resultado</h2>
            {!resultado.calculo_realizado ? (
              <p className="erro">
                O cálculo não pôde ser concluído. Veja as pendências abaixo.
              </p>
            ) : (
              <>
                <p className="muted">
                  Referência do valor atual:{" "}
                  {resultado.totais?.baseline_rotulo ?? "—"}
                </p>
                <p>
                  Beneficiários considerados no cálculo:{" "}
                  <strong>{resultado.beneficiarios_calculados}</strong>
                </p>
                <table className="comparativo">
                  <thead>
                    <tr>
                      <th></th>
                      <th>Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>Plano atual (mensal)</td>
                      <td>{resultado.totais?.atual_mensal_reais}</td>
                    </tr>
                    <tr>
                      <td>Proposta (mensal)</td>
                      <td>{resultado.totais?.proposta_mensal_reais}</td>
                    </tr>
                    <tr
                      className={`destaque destaque--${resultado.totais?.diferenca_semantica ?? "neutro"}`}
                    >
                      <td>
                        {resultado.totais?.rotulo_diferenca_mensal}
                        {resultado.totais?.diferenca_semantica === "aumento" &&
                          " — proposta mais cara"}
                        {resultado.totais?.diferenca_semantica === "economia" &&
                          " — proposta mais barata"}
                      </td>
                      <td>{resultado.totais?.diferenca_mensal_reais}</td>
                    </tr>
                    <tr
                      className={`destaque destaque--${resultado.totais?.diferenca_semantica ?? "neutro"}`}
                    >
                      <td>{resultado.totais?.rotulo_diferenca_anual}</td>
                      <td>{resultado.totais?.diferenca_anual_reais}</td>
                    </tr>
                  </tbody>
                </table>
              </>
            )}
          </section>

          <section className="cartao">
            <h2>Pendências</h2>
            <Pendencias items={resultado.pendencias} />
          </section>

          <section className="cartao cartao--auditoria">
            <button
              type="button"
              className="link"
              onClick={() => setAuditoriaAberta((v) => !v)}
            >
              {auditoriaAberta ? "Ocultar" : "Mostrar"} auditoria técnica
            </button>
            {auditoriaAberta && <Auditoria items={resultado.auditoria} />}
          </section>
        </>
      )}
    </div>
  );
}
