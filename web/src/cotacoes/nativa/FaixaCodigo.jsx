import { useEffect, useState } from "react";
import { chamarRpa } from "../rpaClient";

/**
 * Aviso de código (2FA). Espelho de NP.faixaCodigo / _conferirFaixaCodigo:
 * a faixa só some quando a operadora dela deixa de esperar o código.
 */
export default function FaixaCodigo({ conexao, operadoras, aviso }) {
  const pendentes = Object.entries(conexao || {})
    .filter(([, st]) => st === "aguardando_codigo")
    .map(([id]) => id);
  const [travado, setTravado] = useState(null);
  const [codigo, setCodigo] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [enviado, setEnviado] = useState(false);
  const mostrando = travado && pendentes.includes(travado) ? travado : pendentes[0] || null;

  useEffect(() => {
    if (mostrando && mostrando !== travado) {
      setTravado(mostrando);
      setCodigo("");
      setEnviado(false);
      setEnviando(false);
    }
    if (!mostrando && travado) {
      setTravado(null);
      setCodigo("");
      setEnviado(false);
    }
  }, [mostrando, travado]);

  if (!mostrando) return null;

  const op = (operadoras || []).find((o) => o.id === mostrando);
  const nome = op ? op.nome : mostrando;

  async function enviar(ev) {
    ev.preventDefault();
    setEnviando(true);
    try {
      await chamarRpa("POST", `/api/codigo/${mostrando}`, { codigo });
      setEnviado(true);
    } catch (e) {
      aviso?.(e.message || "Não deu para enviar o código.", "erro");
      setEnviando(false);
    }
  }

  return (
    <form className="nativa-faixa-codigo" onSubmit={enviar}>
      {enviado ? (
        <div>
          <strong>Código enviado.</strong>{" "}
          <span className="muted">O robô está entrando no portal com ele.</span>
        </div>
      ) : (
        <>
          <div>
            <label htmlFor="nativa-codigo">
              <strong>Digite o código que chegou no seu celular/e-mail</strong>
            </label>
            <span className="muted">
              O portal da {nome} pediu um código de verificação. O robô digita no portal para você.
            </span>
          </div>
          <div className="nativa-faixa-acoes">
            <input
              id="nativa-codigo"
              className="campo"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={12}
              spellCheck={false}
              value={codigo}
              onChange={(e) => setCodigo(e.target.value)}
              autoFocus
            />
            <button type="submit" disabled={enviando || !codigo.trim()}>
              Enviar código
            </button>
          </div>
        </>
      )}
    </form>
  );
}
