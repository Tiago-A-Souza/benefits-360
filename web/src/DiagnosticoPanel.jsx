import { useEffect, useState } from "react";
import { obterDiagnostico } from "./api";

function formatarEvento(ev) {
  const det = ev.detalhe ? JSON.stringify(ev.detalhe) : "";
  return `[${ev.ts}] ${ev.estudo_id || "—"} · ${ev.etapa} · ${ev.evento}${det ? ` · ${det}` : ""}`;
}

export default function DiagnosticoPanel() {
  const [aberto, setAberto] = useState(false);
  const [eventos, setEventos] = useState([]);
  const [erro, setErro] = useState(null);
  const [copiado, setCopiado] = useState(false);

  useEffect(() => {
    if (!aberto) return;
    obterDiagnostico()
      .then((r) => setEventos(r.eventos || []))
      .catch((e) => setErro(e.message));
  }, [aberto]);

  async function copiarTudo() {
    const texto = eventos.map(formatarEvento).join("\n");
    try {
      await navigator.clipboard.writeText(texto || "(sem eventos)");
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      setErro("Não foi possível copiar para a área de transferência.");
    }
  }

  return (
    <div className="diagnostico-rodape">
      <button type="button" className="link diagnostico-toggle" onClick={() => setAberto((v) => !v)}>
        Diagnóstico
      </button>
      {aberto && (
        <div className="diagnostico-painel cartao cartao--interno">
          <div className="diagnostico-cabecalho">
            <strong>Eventos recentes</strong>
            <div className="diagnostico-acoes">
              <button type="button" className="secundario btn-compacto" onClick={copiarTudo}>
                {copiado ? "Copiado!" : "Copiar tudo"}
              </button>
              <button type="button" className="link btn-compacto" onClick={() => setAberto(false)}>
                Fechar
              </button>
            </div>
          </div>
          {erro && <p className="erro">{erro}</p>}
          {!erro && eventos.length === 0 && (
            <p className="muted">Nenhum evento registrado ainda.</p>
          )}
          <ul className="diagnostico-lista">
            {eventos
              .slice()
              .reverse()
              .map((ev, i) => (
                <li key={`${ev.ts}-${i}`}>
                  <code>{formatarEvento(ev)}</code>
                </li>
              ))}
          </ul>
        </div>
      )}
    </div>
  );
}
