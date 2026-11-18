import { passosAjuda, perguntasAjuda } from "./regrasRestante";

export default function Ajuda({ operadoras, retencaoDias = 90, simulador = false }) {
  const passos = passosAjuda(operadoras);
  const perguntas = perguntasAjuda(operadoras, retencaoDias);

  return (
    <div>
      <h1>Ajuda</h1>
      <p className="muted">Como o robô trabalha e o que fazer quando algo sai do normal.</p>

      <section className="cartao">
        <h2>Do pedido ao PDF</h2>
        <ol className="nativa-passos-ajuda">
          {passos.map(([t, d]) => (
            <li key={t}>
              <strong>{t}</strong>
              <span className="muted"> {d}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="cartao">
        <h2>Perguntas frequentes</h2>
        <div className="nativa-perguntas">
          {perguntas.map(([p, r]) => (
            <details key={p}>
              <summary>{p}</summary>
              <p>{r}</p>
            </details>
          ))}
        </div>
      </section>

      {simulador ? (
        <section className="cartao">
          <h2>Simulador local</h2>
          <p className="muted">
            Esta tela está ligada a uma imitação do portal, para treino e testes. Nada é emitido de verdade. O login
            de treino (falso) já vem guardado, só na memória: o simulador não aceita o login de verdade.
          </p>
        </section>
      ) : null}
    </div>
  );
}
