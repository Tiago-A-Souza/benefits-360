import { passosVisiveis } from "../fluxo/passos";

function rotuloEtapaSugerida(rascunho, etapa) {
  if (!etapa) return null;
  const passo = passosVisiveis(rascunho).find((p) => p.ordem === etapa);
  return passo?.titulo || `Etapa ${etapa}`;
}

export default function BloqueiosComparativo({ consistencia, rascunho }) {
  const bloqueios = consistencia?.bloqueios || [];
  if (!bloqueios.length) return null;

  return (
    <div
      className="comparativo-consistencia comparativo-consistencia--erro cmp-bloqueios-painel"
      role="alert"
    >
      <p className="cmp-bloqueios-titulo">
        <strong>Cálculo bloqueado — corrija antes de avançar:</strong>
      </p>
      <ul className="cmp-bloqueios-lista">
        {bloqueios.map((b, i) => {
          const etapaTitulo = rotuloEtapaSugerida(rascunho, b.etapa_sugerida);
          return (
            <li key={`${b.codigo}-${b.alvo_ref || i}`} className="cmp-bloqueio-item">
              <div className="cmp-bloqueio-cabecalho">
                <span className="cmp-bloqueio-codigo">{b.codigo}</span>
                {b.alvo_rotulo && (
                  <span className="cmp-bloqueio-alvo"> · {b.alvo_rotulo}</span>
                )}
              </div>
              <p className="cmp-bloqueio-msg">{b.mensagem}</p>
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
      {consistencia.mensagem_contagem && (
        <p className="cmp-bloqueio-contagem muted">{consistencia.mensagem_contagem}</p>
      )}
    </div>
  );
}
