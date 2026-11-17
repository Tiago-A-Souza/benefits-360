/**
 * Página provisória de prova (não está no menu).
 * Abra: http://127.0.0.1:5173/?prova-rpa=1
 * Descarta quando a aba nativa existir.
 */
import { useEffect, useState } from "react";
import { chamarRpa, ouvirEventosRpa, urlBaseRpa } from "./rpaClient";

export default function ProvaRpaDireto({ onFechar }) {
  const [estado, setEstado] = useState(null);
  const [erro, setErro] = useState(null);
  const [eventos, setEventos] = useState([]);
  const base = urlBaseRpa();

  useEffect(() => {
    let vivo = true;
    chamarRpa("GET", "/api/estado")
      .then((d) => vivo && setEstado(d))
      .catch((e) => vivo && setErro(e.message || "Falha"));
    return () => {
      vivo = false;
    };
  }, []);

  useEffect(() => {
    const { fechar } = ouvirEventosRpa(
      (ev) => setEventos((lista) => [...lista.slice(-40), ev]),
      (e) => setErro((prev) => prev || e.message),
    );
    return () => fechar();
  }, []);

  return (
    <main className="lista-main" style={{ padding: "1.5rem", maxWidth: 720 }}>
      <header className="lista-head">
        <div>
          <h1>Prova RPA direto</h1>
          <p>
            Chamadas do navegador ({typeof window !== "undefined" ? window.location.origin : "?"}) →{" "}
            <code>{base}</code>. Não use em produção — só para validar CORS/SSE.
          </p>
        </div>
        {onFechar && (
          <button type="button" className="botao" onClick={onFechar}>
            Fechar
          </button>
        )}
      </header>

      {erro && (
        <p className="erro" role="alert">
          {erro}
        </p>
      )}

      <section>
        <h2>GET /api/estado</h2>
        {!estado && !erro && <p className="lista-carregando">Carregando…</p>}
        {estado && (
          <pre className="cotacoes-rpa-cmd">
            <code>{JSON.stringify(estado, null, 2)}</code>
          </pre>
        )}
      </section>

      <section>
        <h2>SSE /api/eventos</h2>
        <ul>
          {eventos.length === 0 && <li className="discreto">Aguardando eventos…</li>}
          {eventos.map((ev, i) => (
            <li key={i}>
              <code>{JSON.stringify(ev)}</code>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}
