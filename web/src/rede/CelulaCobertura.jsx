import { partesCelula } from "./codigosCelula.js";

/** Siglas padrão normais; código cru da base em cinza itálico (só na tela). */
export default function CelulaCobertura({ texto }) {
  const partes = partesCelula(texto);
  if (!partes.length) return null;
  return (
    <>
      {partes.map((p, i) => (
        <span key={`${p.codigo}-${i}`}>
          {i > 0 ? " " : ""}
          {p.cru ? (
            <span
              className="cod-cru"
              title="Código da base, sem sigla padrão (H, HD, M, PS)"
            >
              {p.codigo}
            </span>
          ) : (
            p.codigo
          )}
        </span>
      ))}
    </>
  );
}
