import { useState } from "react";
import { marcaOperadora } from "./operadoras";
import "./LogoOperadora.css";

const TAMANHOS = { sm: 20, md: 28, lg: 40 };

export default function LogoOperadora({ operadora, tamanho = "md", mostrarNome = false }) {
  const m = marcaOperadora(operadora);
  const [falhou, setFalhou] = useState(!m.logo);
  const px = TAMANHOS[tamanho] || TAMANHOS.md;
  const soSelo = falhou || !m.logo;

  return (
    <span
      className={`nativa-logo-op nativa-logo-op--${tamanho}`}
      style={{ "--cor-op": m.cor, "--cor-op-suave": m.corSuave, "--logo-h": `${px}px` }}
    >
      {soSelo ? (
        <span className="nativa-logo-op-selo">{m.nome || operadora}</span>
      ) : (
        <img
          src={m.logo}
          alt={m.nome}
          height={px}
          onError={() => setFalhou(true)}
        />
      )}
      {mostrarNome && !soSelo ? <span className="nativa-logo-op-nome">{m.nome}</span> : null}
    </span>
  );
}
