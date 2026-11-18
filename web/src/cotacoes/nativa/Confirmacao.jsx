import { useEffect, useRef, useState } from "react";

const ATRASO_MS = 500;

/**
 * Modal de confirmação humana (espelho de NP.confirmar).
 * Foco em Voltar; OK e alternativa só valem depois de 500 ms.
 * Enter repetido/segurado não confirma. Escape cancela.
 * resolve(true | false | "alternativa")
 */
export default function Confirmacao({
  titulo,
  texto = [],
  ok = "Confirmar",
  cancelar = "Voltar",
  principal = true,
  alternativa = null,
  extra = null,
  onFechar,
}) {
  const [pronto, setPronto] = useState(false);
  const voltarRef = useRef(null);
  const linhas = [].concat(texto).filter(Boolean);

  useEffect(() => {
    voltarRef.current?.focus();
    const t = setTimeout(() => setPronto(true), ATRASO_MS);
    const tecla = (ev) => {
      if (ev.key === "Escape") {
        ev.preventDefault();
        onFechar(false);
      }
      if (ev.repeat) {
        ev.preventDefault();
        ev.stopPropagation();
      }
    };
    document.addEventListener("keydown", tecla, true);
    return () => {
      clearTimeout(t);
      document.removeEventListener("keydown", tecla, true);
    };
  }, [onFechar]);

  return (
    <div className="nativa-modal" role="presentation">
      <div className="nativa-modal-caixa cartao" role="dialog" aria-modal="true" aria-labelledby="nativa-modal-titulo">
        <h2 id="nativa-modal-titulo">{titulo}</h2>
        {linhas.map((t, i) => (
          <p key={i}>{t}</p>
        ))}
        {extra}
        <div className="nativa-modal-acoes">
          <button type="button" className="secundario" ref={voltarRef} onClick={() => onFechar(false)}>
            {cancelar}
          </button>
          {alternativa ? (
            <button type="button" className="secundario" disabled={!pronto} onClick={() => onFechar("alternativa")}>
              {alternativa}
            </button>
          ) : null}
          <button
            type="button"
            className={principal ? "" : "secundario"}
            disabled={!pronto}
            onClick={() => onFechar(true)}
          >
            {ok}
          </button>
        </div>
      </div>
    </div>
  );
}

export function useConfirmacao() {
  const [pedido, setPedido] = useState(null);
  function confirmar(opts) {
    return new Promise((resolve) => {
      setPedido({ ...opts, resolve });
    });
  }
  const el = pedido ? (
    <Confirmacao
      {...pedido}
      onFechar={(v) => {
        pedido.resolve(v);
        setPedido(null);
      }}
    />
  ) : null;
  return [confirmar, el];
}
