import { useEffect, useState } from "react";
import { calcularEstudo, obterPendencias, obterRascunho } from "./api";
import ComparativoExperiencia from "./comparativo/ComparativoExperiencia";

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
      const rascunho = await obterRascunho(estudoId);
      if (rascunho.selecao_apresentacao?.ordem?.length) {
        data.propostas_apresentacao = rascunho.selecao_apresentacao.ordem;
      }
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

  return (
    <section className="cartao">
      <h2>Comparativo financeiro</h2>
      <p className="muted">
        Calcule todas as propostas, selecione as que irão à apresentação e revise a prévia do
        cliente antes do snapshot.
      </p>

      <h3>Antes de calcular</h3>
      <Pendencias items={pendencias} />

      <button type="button" onClick={handleCalcular} disabled={carregando}>
        {carregando ? "Calculando…" : "Calcular comparativo"}
      </button>
      {erro && <p className="erro">{erro}</p>}

      {resultado && !resultado.calculo_realizado && (
        <p className="erro">
          O comparativo não está completo — corrija a inconsistência antes de avançar.
        </p>
      )}

      {resultado?.calculo_realizado && (
        <>
          <p className="cmp-meta-resumo">
            Beneficiários: <strong>{resultado.beneficiarios_calculados}</strong>
            {resultado.validade_proposta && (
              <span className="muted"> · Validade: {resultado.validade_proposta}</span>
            )}
          </p>
          <ComparativoExperiencia estudoId={estudoId} resultado={resultado} />
        </>
      )}
    </section>
  );
}
