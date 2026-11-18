import { useState } from "react";
import { marcaOperadora } from "./operadoras";
import "./LogoOperadora.css";

const TAMANHOS = { sm: 20, md: 28, lg: 28 };

export default function LogoOperadora({ operadora, tamanho = "md" }) {
  const m = marcaOperadora(operadora);
  const [falhou, setFalhou] = useState(!m.logo);
  const px = TAMANHOS[tamanho] || TAMANHOS.md;
  const soSelo = falhou || !m.logo;
  const nome = m.nome || operadora;

  return (
    <span
      className={`nativa-logo-op nativa-logo-op--${tamanho}`}
      style={{ "--cor-op": m.cor, "--cor-op-suave": m.corSuave, "--logo-h": `${px}px` }}
      title={nome}
    >
      {soSelo ? (
        <span className="nativa-logo-op-selo">{nome}</span>
      ) : (
        <img src={m.logo} alt={nome} onError={() => setFalhou(true)} />
      )}
    </span>
  );
}
