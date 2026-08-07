import { passosVisiveis } from "../fluxo/passos";

function rotuloEtapaSugerida(rascunho, etapa) {
  if (!etapa) return null;
  const passo = passosVisiveis(rascunho).find((p) => p.ordem === etapa);
  return passo?.titulo || `Etapa ${etapa}`;
}

function ListaBloqueios({ bloqueios, rascunho }) {
  if (!bloqueios.length) return null;
  return (
    <ul className="cmp-bloqueios-lista">
      {bloqueios.map((b, i) => {
        const etapaTitulo = rotuloEtapaSugerida(rascunho, b.etapa_sugerida);
        const mostrarDetalhe = Boolean(b.detalhe_tecnico);
        return (
          <li key={`${b.origem}-${b.codigo}-${b.alvo_ref || i}`} className="cmp-bloqueio-item">
            <div className="cmp-bloqueio-cabecalho">
              <span className="cmp-bloqueio-codigo">{b.codigo}</span>
              {b.alvo_rotulo && (
                <span className="cmp-bloqueio-alvo"> · {b.alvo_rotulo}</span>
              )}
              {b.quantidade > 1 && (
                <span className="cmp-bloqueio-qtd muted"> · {b.quantidade}×</span>
              )}
            </div>
            <p className="cmp-bloqueio-msg">{b.mensagem}</p>
            {mostrarDetalhe && (
              <details className="cmp-bloqueio-detalhe">
                <summary className="cmp-bloqueio-detalhe-sum muted">Detalhe técnico</summary>
                <pre className="cmp-bloqueio-detalhe-corpo">{b.detalhe_tecnico}</pre>
              </details>
            )}
            {(etapaTitulo || b.acao_sugerida) && (
              <p className="cmp-bloqueio-acao muted">
                {etapaTitulo && <>Revise «{etapaTitulo}»</>}
                {etapaTitulo && b.acao_sugerida && " — "}
                {b.acao_sugerida}
              </p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

export default function BloqueiosComparativo({ consistencia, rascunho }) {
  const bloqueios = consistencia?.bloqueios || [];
  if (!bloqueios.length) return null;

  const compilacao = bloqueios.filter((b) => b.origem === "compilacao");
  const motor = bloqueios.filter((b) => b.origem !== "compilacao");
  const agrupado = compilacao.length > 0 && motor.length > 0;

  return (
    <div
      className="comparativo-consistencia comparativo-consistencia--erro cmp-bloqueios-painel"
      role="alert"
    >
      <p className="cmp-bloqueios-titulo">
        <strong>Cálculo bloqueado — corrija antes de avançar:</strong>
      </p>
      {agrupado ? (
        <>
          {compilacao.length > 0 && (
            <section className="cmp-bloqueios-grupo">
              <h4 className="cmp-bloqueios-grupo-titulo">Compilação do rascunho</h4>
              <ListaBloqueios bloqueios={compilacao} rascunho={rascunho} />
            </section>
          )}
          {motor.length > 0 && (
            <section className="cmp-bloqueios-grupo">
              <h4 className="cmp-bloqueios-grupo-titulo">Validação do motor</h4>
              <ListaBloqueios bloqueios={motor} rascunho={rascunho} />
            </section>
          )}
        </>
      ) : (
        <ListaBloqueios bloqueios={bloqueios} rascunho={rascunho} />
      )}
      {consistencia.mensagem_contagem && (
        <p className="cmp-bloqueio-contagem muted">{consistencia.mensagem_contagem}</p>
      )}
    </div>
  );
}
